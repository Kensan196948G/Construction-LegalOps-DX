#!/usr/bin/env bash
# One-time cutover: Docker compose stacks (construction-legalops-dx / construction-legalops-mvp)
# -> native systemd units installed by infra/native/install.sh. Run with sudo AFTER install.sh
# reported the app tiers healthy. Order keeps public downtime to the DB resync window (~1 min):
#   1. stop container app tiers (backend/worker/beat/frontend) so no more writes hit the container DBs
#   2. final pg_dump from the container DBs -> drop/recreate legalops_prod / legalops_mvp on the host cluster
#   3. restart native app units, wait for /readyz
#   4. swap ingress: container nginx -> legalops-nginx (8410/8412), then native cloudflared up, container cloudflared down
#   5. stop the container postgres/redis (NOT removed; volumes kept for rollback)
#   6. alembic upgrade head on both host DBs (no-op when already at head)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; OWNER="${SUDO_USER:-kensan}"
BK="/home/$OWNER/backups/docker-exit/$(date +%F)"; install -d -o "$OWNER" -g "$OWNER" "$BK"
APP_UNITS="legalops-prod-backend legalops-prod-celery-worker legalops-prod-celery-beat legalops-prod-frontend legalops-mvp-backend legalops-mvp-frontend"
say() { echo "[cutover $(date +%T)] $*"; }
pw_of() { docker inspect "$1" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -oP '^POSTGRES_PASSWORD=\K.*'; }
counts() { PGPASSWORD="$1" psql -h 127.0.0.1 -U "$2" -d "$3" -Atc "select string_agg(t, ',') from (select table_name||'='||(xpath('/row/c/text()', query_to_xml('select count(*) as c from public.'||quote_ident(table_name), false, true, '')))[1]::text as t from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1) s"; }
ccounts() { docker exec "$1" psql -U legalops -d legalops -Atc "select string_agg(t, ',') from (select table_name||'='||(xpath('/row/c/text()', query_to_xml('select count(*) as c from public.'||quote_ident(table_name), false, true, '')))[1]::text as t from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1) s"; }
resync() { # resync <container> <hostdb/role>
  local c=$1 db=$2 pw; pw="$(pw_of "$c")"
  docker exec "$c" pg_dump -U legalops --no-owner --no-privileges -d legalops | grep -vE '^SET transaction_timeout' > "$BK/$c.final.sql"
  sudo -u postgres psql -Atqc "select pg_terminate_backend(pid) from pg_stat_activity where datname='$db' and pid<>pg_backend_pid()" >/dev/null
  sudo -u postgres psql -Atqc "drop database if exists \"$db\"" >/dev/null
  sudo -u postgres psql -Atqc "create database \"$db\" owner \"$db\" encoding 'UTF8' template template0" >/dev/null
  PGPASSWORD="$pw" psql -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -U "$db" -d "$db" -f "$BK/$c.final.sql" >/dev/null
  [ "$(ccounts "$c")" = "$(counts "$pw" "$db" "$db")" ] && say "$db resynced, row counts match" || { say "ROW COUNT MISMATCH for $db"; exit 1; }
}

say "1. stop container app tiers"
docker stop construction-legalops-dx-backend-1 construction-legalops-dx-backend-2 construction-legalops-dx-celery-worker-1 construction-legalops-dx-celery-worker-2 legalops-celery-beat construction-legalops-dx-frontend-1 construction-legalops-dx-frontend-2 construction-legalops-mvp-backend-1 construction-legalops-mvp-frontend-1 >/dev/null
say "2. final DB resync"
systemctl stop $APP_UNITS
resync legalops-postgres legalops_prod
resync construction-legalops-mvp-postgres-1 legalops_mvp
say "3. start native app tiers"
systemctl start $APP_UNITS
for i in $(seq 1 30); do ok=1; for p in 8011/readyz 8013/readyz 3011/api/health 3013/api/health; do curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$p" 2>/dev/null || ok=0; done; [ $ok = 1 ] && break; sleep 2; done
[ "$ok" = 1 ] || { say "native app tier NOT healthy — aborting before ingress swap (containers stopped; docker start them to roll back)"; exit 1; }
say "4. swap ingress"
docker stop legalops-nginx construction-legalops-mvp-nginx-1 >/dev/null
systemctl restart legalops-nginx.service
curl -fsS --max-time 3 http://127.0.0.1:8410/healthz >/dev/null && curl -fsS --max-time 3 http://127.0.0.1:8412/healthz >/dev/null && curl -fsS --max-time 5 http://127.0.0.1:8412/readyz >/dev/null && say "nginx 8410/8412 healthy"
systemctl start legalops-prod-cloudflared.service legalops-mvp-cloudflared.service; sleep 8
docker stop legalops-cloudflared construction-legalops-mvp-cloudflared-1 >/dev/null; sleep 5
say "public prod: HTTP $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://legalops.mirai-dx-platform.com/healthz)  (302/401 = behind Cloudflare Access, expected)"
say "public mvp : HTTP $(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://legalops-mvp.mirai-dx-platform.com/healthz)"
say "5. stop container postgres/redis (kept for rollback)"
docker stop legalops-postgres legalops-redis construction-legalops-mvp-postgres-1 construction-legalops-mvp-redis-1 >/dev/null
say "6. alembic upgrade head"
for e in prod mvp; do url="$(grep -oP '^DB_URL=\K.*' /etc/legalops/$e-backend.env)"; sudo -u "$OWNER" -H env DB_URL="$url" PYTHONPATH="$REPO/backend" bash -c "cd '$REPO/backend' && .venv/bin/alembic upgrade head 2>&1 | tail -1"; sudo -u "$OWNER" -H env DB_URL="$url" PYTHONPATH="$REPO/backend" bash -c "cd '$REPO/backend' && .venv/bin/alembic current 2>/dev/null | tail -1" | sed "s/^/$e alembic: /"; done
say "done. running containers now: $(docker ps -q | wc -l)"
