#!/usr/bin/env bash
# Install the native (Docker-free) LegalOps stack on this host. Idempotent. Run with sudo.
#   sudo bash infra/native/install.sh            # install/refresh units, nginx, cloudflared configs; (re)start app tiers
#   sudo bash infra/native/install.sh --build    # also rebuild backend venv (uv) and frontend (Next standalone) first
# Prerequisites: /etc/legalops/*.env (see migrate-env-from-docker.sh), host PostgreSQL 16 with
# legalops_prod / legalops_mvp, /etc/redis/legalops.conf (legalops-redis.service).
# nginx and cloudflared are installed but only (re)started when --with-ingress is given (cutover does that).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OWNER="${SUDO_USER:-kensan}"
NODE=/home/$OWNER/.nvm/versions/node/v20.20.2/bin
BUILD=0; INGRESS=0
for a in "$@"; do case "$a" in --build) BUILD=1;; --with-ingress) INGRESS=1;; *) echo "unknown arg $a" >&2; exit 2;; esac; done

if [ "$BUILD" = 1 ]; then
  echo "[build] backend venv"; sudo -u "$OWNER" -H bash -c "cd '$REPO/backend' && ~/.local/bin/uv venv .venv --python 3.12 -q && ~/.local/bin/uv pip install -q -p .venv/bin/python -e ."
  echo "[build] frontend standalone"; sudo -u "$OWNER" -H bash -c "cd '$REPO/frontend' && export PATH=$NODE:\$PATH NEXT_TELEMETRY_DISABLED=1 && npm ci --legacy-peer-deps --no-audit --no-fund && NODE_ENV=production NEXT_BUILD_CPUS=2 npm run build"
fi
[ -x "$REPO/backend/.venv/bin/uvicorn" ] || { echo "backend venv missing (run with --build)" >&2; exit 1; }
[ -f "$REPO/frontend/.next/standalone/server.js" ] || { echo "frontend standalone build missing (run with --build)" >&2; exit 1; }
for f in prod-backend prod-frontend mvp-backend mvp-frontend; do [ -f /etc/legalops/$f.env ] || { echo "/etc/legalops/$f.env missing" >&2; exit 1; }; done

# Next standalone needs public/ and .next/static next to server.js (same as `npm run start:standalone`).
sudo -u "$OWNER" -H bash -c "cd '$REPO/frontend' && rm -rf .next/standalone/public .next/standalone/.next/static && cp -r public .next/standalone/public && cp -r .next/static .next/standalone/.next/static"

# redis (instance config keeps the existing password if already installed)
if [ ! -f /etc/redis/legalops.conf ]; then
  RP="$(openssl rand -base64 24 | tr -d '/+=')"; sed "s/__REDIS_PASSWORD__/$RP/" "$REPO/infra/native/redis/legalops.conf.template" > /etc/redis/legalops.conf
  chown redis:redis /etc/redis/legalops.conf; chmod 640 /etc/redis/legalops.conf; install -d -o redis -g redis -m 750 /var/lib/redis/legalops /var/log/redis
fi
install -m 644 "$REPO/infra/native/systemd/legalops-redis.service" /etc/systemd/system/

# nginx (dedicated master, same pattern as civil-it-ops-webui)
install -m 644 "$REPO/infra/nginx/security-headers.conf" /etc/nginx/legalops-security-headers.conf
install -m 644 "$REPO/infra/native/nginx/legalops-main.conf" /etc/nginx/legalops-main.conf
nginx -t -c /etc/nginx/legalops-main.conf

# cloudflared host configs
for e in prod mvp; do install -o "$OWNER" -g "$OWNER" -m 644 "$REPO/infra/native/cloudflared/legalops-$e-native-config.yml" "/home/$OWNER/.cloudflared/legalops-$e-native-config.yml"; done

# units
for u in legalops-prod-backend legalops-prod-celery-worker legalops-prod-celery-beat legalops-prod-frontend legalops-mvp-backend legalops-mvp-frontend legalops-nginx legalops-prod-cloudflared legalops-mvp-cloudflared; do
  install -m 644 "$REPO/infra/native/systemd/$u.service" /etc/systemd/system/$u.service
done
systemctl daemon-reload
systemctl enable --now legalops-redis.service >/dev/null
APP_UNITS="legalops-prod-backend legalops-prod-celery-worker legalops-prod-celery-beat legalops-prod-frontend legalops-mvp-backend legalops-mvp-frontend"
systemctl enable $APP_UNITS >/dev/null 2>&1; systemctl restart $APP_UNITS
for i in $(seq 1 30); do ok=1; for p in 8011/healthz 8013/healthz 3011/api/health 3013/api/health; do curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$p" 2>/dev/null || ok=0; done; [ $ok = 1 ] && break; sleep 2; done
[ "$ok" = 1 ] || { echo "app tier health FAILED"; systemctl --no-pager status $APP_UNITS | grep -E 'Active|●' ; exit 1; }
echo "[install] app tiers healthy: prod backend 8011 / frontend 3011, mvp backend 8013 / frontend 3013"
if [ "$INGRESS" = 1 ]; then
  systemctl enable --now legalops-nginx.service legalops-prod-cloudflared.service legalops-mvp-cloudflared.service; systemctl restart legalops-nginx.service
  curl -fsS --max-time 3 http://127.0.0.1:8410/healthz >/dev/null && curl -fsS --max-time 3 http://127.0.0.1:8412/healthz >/dev/null && echo "[install] nginx healthy: prod 8410 / mvp 8412"
else
  systemctl enable legalops-nginx.service legalops-prod-cloudflared.service legalops-mvp-cloudflared.service >/dev/null 2>&1
  echo "[install] ingress units installed but not started (use --with-ingress or cutover-from-docker.sh)"
fi
