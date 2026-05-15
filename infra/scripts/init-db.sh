#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX: DB 初期化
# - alembic upgrade head でスキーマ適用
# - 開発環境のみ seed.sql を流す
#
# 利用方法:
#   docker compose -f infra/docker/docker-compose.yml exec backend \
#     bash /app/infra/scripts/init-db.sh
#
# CI で実行する場合: APP_ENV=test を渡す
# ============================================================
set -euo pipefail

# TZ を Asia/Tokyo に固定
export TZ="${TZ:-Asia/Tokyo}"

log() { printf '[init-db %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

APP_ENV="${APP_ENV:-development}"
DB_URL="${DB_URL:-postgresql+asyncpg://legalops:legalops_dev@postgres:5432/legalops}"

log "APP_ENV=${APP_ENV}"
log "DB_URL=$(printf '%s' "${DB_URL}" | sed -E 's#(://[^:]+):[^@]+@#\1:***@#')"

# backend のリポジトリ root を推定 (Dockerfile は /app に配置想定)
BACKEND_DIR="${BACKEND_DIR:-/app}"
if [[ ! -f "${BACKEND_DIR}/alembic.ini" ]]; then
  # ホスト実行ケース (リポジトリ root から起動)
  REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  BACKEND_DIR="${REPO_ROOT}/backend"
fi

if [[ ! -f "${BACKEND_DIR}/alembic.ini" ]]; then
  log "ERROR: alembic.ini が見つかりません (BACKEND_DIR=${BACKEND_DIR})"
  exit 1
fi

cd "${BACKEND_DIR}"

# --- 1) DB 接続待ち ---
log "Waiting for database..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until python -c "
import os, sys
from urllib.parse import urlparse
import socket
u = urlparse(os.environ.get('DB_URL', '${DB_URL}').replace('postgresql+asyncpg', 'postgresql'))
s = socket.socket(); s.settimeout(2)
s.connect((u.hostname, u.port or 5432)); s.close()
" >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS+1))
  if (( ATTEMPTS >= MAX_ATTEMPTS )); then
    log "ERROR: database not reachable after ${MAX_ATTEMPTS} attempts"
    exit 2
  fi
  sleep 2
done
log "Database reachable."

# --- 2) Alembic migration ---
log "Running: alembic upgrade head"
alembic upgrade head
log "Alembic migration completed."

# --- 3) 開発 / staging のみ seed ---
SEED_FILE="${BACKEND_DIR}/app/db/seed.sql"
case "${APP_ENV}" in
  development|staging|test)
    if [[ -f "${SEED_FILE}" ]]; then
      log "Seeding initial data from ${SEED_FILE}"
      # psycopg2 経由で実行 (asyncpg 接続文字列を psycopg2 形式に変換)
      python - <<'PY'
import os, psycopg2
url = os.environ["DB_URL"].replace("postgresql+asyncpg", "postgresql")
with open(os.environ.get("SEED_FILE", "/app/app/db/seed.sql"), "r", encoding="utf-8") as f:
    sql = f.read()
conn = psycopg2.connect(url)
conn.autocommit = True
with conn.cursor() as cur:
    cur.execute(sql)
conn.close()
print("seed applied")
PY
    else
      log "No seed.sql found at ${SEED_FILE} — skipping seed."
    fi
    ;;
  production)
    log "APP_ENV=production: skipping seed."
    ;;
  *)
    log "Unknown APP_ENV=${APP_ENV}: skipping seed."
    ;;
esac

log "init-db completed successfully."
