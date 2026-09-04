#!/usr/bin/env bash
# One-time helper: derive /etc/legalops/{prod,mvp}-{backend,frontend}.env from the RUNNING
# compose containers, rewriting only the Docker-internal endpoints to the native layout:
#   postgres:5432/legalops -> 127.0.0.1:5432/legalops_{prod,mvp} (role legalops_{prod,mvp}, same password)
#   redis:6379/N           -> 127.0.0.1:6390/N (prod) / 6390/(N+4) (mvp), password from /etc/redis/legalops.conf
#   nginx / backend:8000   -> 127.0.0.1:8410 (prod nginx) / 127.0.0.1:8013 (mvp backend)
#   PORT / HOSTNAME        -> native ports on 127.0.0.1
# Secrets are copied verbatim into root-only files; nothing is printed. Run with sudo.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
OUT=/etc/legalops; install -d -m 750 -o root -g root "$OUT"
RP="$(grep -oP '^requirepass \K.*' /etc/redis/legalops.conf)"
dump() { docker inspect "$1" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -vE '^(PATH|HOME|LANG|PYTHON[A-Z_]*|PIP_[A-Z_]*|GPG_KEY|NODE_VERSION|YARN_VERSION|HOSTNAME|LC_[A-Z_]*|UV_[A-Z_]*|APP_HOME|VIRTUAL_ENV)=' | grep -v '^$'; }
gen() { # gen <container> <env> <backend|frontend> <port>
  local c=$1 env=$2 tier=$3 port=$4 dbn=legalops_$2 f="$OUT/$2-$3.env" off=0; [ "$env" = mvp ] && off=4
  { echo "# Generated $(date -Is) by infra/native/migrate-env-from-docker.sh from container $c. Root-only. Do not commit."
    dump "$c" \
    | sed -E "s#^(DB_URL=postgresql\+asyncpg://)legalops:([^@]*)@postgres:5432/legalops#\1$dbn:\2@127.0.0.1:5432/$dbn#" \
    | sed -E "s#^(REDIS_URL|CELERY_BROKER_URL|CELERY_RESULT_BACKEND)=redis://(:[^@]*@)?redis:6379/([0-9]+)#\1=redis://:$RP@127.0.0.1:6390/\$((\3+$off))#" \
    | sed -E "s#^BACKEND_INTERNAL_URL=http://nginx\$#BACKEND_INTERNAL_URL=http://127.0.0.1:8410#" \
    | sed -E "s#^API_INTERNAL_URL=http://backend:8000/api/v1\$#API_INTERNAL_URL=http://127.0.0.1:8013/api/v1#" \
    | sed -E "s#^PORT=.*#PORT=$port#; s#^HOSTNAME=.*#HOSTNAME=127.0.0.1#" \
    | sed -E 's#^(POSTGRES_HOST)=.*#\1=127.0.0.1#; s#^(POSTGRES_PORT)=.*#\1=5432#; s#^(REDIS_PORT)=.*#\1=6390#'
    grep -q '^HOSTNAME=' <(dump "$c") || echo "HOSTNAME=127.0.0.1"
  } > "$f.tmp"
  # the $((N+off)) arithmetic above is literal text; evaluate it now
  perl -pe 's/\$\(\((\d+)\+(\d+)\)\)/$1+$2/ge' -i "$f.tmp"
  install -m 600 -o root -g root "$f.tmp" "$f"; rm -f "$f.tmp"
  echo "wrote $f ($(wc -l < "$f") lines)"
}
gen construction-legalops-dx-backend-1  prod backend  8011
gen construction-legalops-dx-frontend-1 prod frontend 3011
gen construction-legalops-mvp-backend-1  mvp backend  8013
gen construction-legalops-mvp-frontend-1 mvp frontend 3013
grep -hoE '^(DB_URL|REDIS_URL|CELERY_BROKER_URL|CELERY_RESULT_BACKEND|BACKEND_INTERNAL_URL|API_INTERNAL_URL|PORT|HOSTNAME)=.*' "$OUT"/*.env | sed -E 's#(://[^:/@]*):[^@]*@#\1:***@#' | sort -u
