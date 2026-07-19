#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — Alembic migration roundtrip verifier
#
# Verifies the release rollback contract against PostgreSQL:
#   upgrade head -> downgrade base -> upgrade head -> idempotent upgrade
#
# Safe defaults:
#   - Uses a disposable PostgreSQL container unless --use-existing-db is set.
#   - Never connects to production unless the caller explicitly provides DB_URL.
#   - Masks connection strings in logs.
#
# Usage:
#   ./scripts/verify_migrations_roundtrip.sh
#   DB_URL=postgresql+asyncpg://... ./scripts/verify_migrations_roundtrip.sh --use-existing-db
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"

MODE="docker"
KEEP_CONTAINER="${KEEP_MIGRATION_TEST_DB:-0}"
CONTAINER_NAME="${MIGRATION_TEST_CONTAINER:-legalops-migration-roundtrip}"
POSTGRES_IMAGE="${POSTGRES_IMAGE:-postgres:16-alpine}"
POSTGRES_USER="${POSTGRES_USER:-legalops}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-legalops_dev}"
POSTGRES_DB="${POSTGRES_DB:-legalops_migration_roundtrip}"
POSTGRES_PORT="${POSTGRES_PORT:-55432}"

log() {
  printf '[migration-roundtrip %s] %s\n' "$(date -u +%FT%TZ)" "$*"
}

mask_url() {
  sed -E 's#(://[^:/@]+):[^@]+@#\1:***@#'
}

usage() {
  cat <<'USAGE'
Usage:
  scripts/verify_migrations_roundtrip.sh [--use-existing-db]

Options:
  --use-existing-db  Use DB_URL / ALEMBIC_DATABASE_URL supplied by the caller.
                     Intended for CI PostgreSQL service or a disposable staging DB.

Environment:
  KEEP_MIGRATION_TEST_DB=1      Keep disposable container after the run.
  MIGRATION_TEST_CONTAINER=...  Container name for disposable PostgreSQL.
  POSTGRES_PORT=55432           Host port for disposable PostgreSQL.
USAGE
}

while (($# > 0)); do
  case "$1" in
    --use-existing-db)
      MODE="existing"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if [[ ! -f "${BACKEND_DIR}/alembic.ini" ]]; then
  echo "alembic.ini not found at ${BACKEND_DIR}" >&2
  exit 66
fi

cleanup() {
  if [[ "${MODE}" == "docker" && "${KEEP_CONTAINER}" != "1" ]]; then
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "${MODE}" == "docker" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required unless --use-existing-db is supplied." >&2
    exit 69
  fi

  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  log "Starting disposable PostgreSQL ${POSTGRES_IMAGE} on 127.0.0.1:${POSTGRES_PORT}"
  docker run -d \
    --name "${CONTAINER_NAME}" \
    -e POSTGRES_USER="${POSTGRES_USER}" \
    -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
    -e POSTGRES_DB="${POSTGRES_DB}" \
    -p "127.0.0.1:${POSTGRES_PORT}:5432" \
    "${POSTGRES_IMAGE}" >/dev/null

  export DB_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
else
  export DB_URL="${ALEMBIC_DATABASE_URL:-${DB_URL:-}}"
  if [[ -z "${DB_URL}" ]]; then
    echo "DB_URL or ALEMBIC_DATABASE_URL is required with --use-existing-db." >&2
    exit 64
  fi
fi

export APP_ENV="${APP_ENV:-test}"
export JWT_SECRET="${JWT_SECRET:-migration-roundtrip-test-secret-not-for-production}"
export PYTHONPATH="${BACKEND_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

log "DB_URL=$(printf '%s' "${DB_URL}" | mask_url)"

log "Waiting for database readiness"
python - <<'PY'
import asyncio
import os
import sys
import time

import asyncpg


async def probe() -> bool:
    url = os.environ["DB_URL"].replace("postgresql+asyncpg", "postgresql")
    try:
        conn = await asyncpg.connect(url, timeout=2)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
        return True
    except Exception:
        return False


deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    if asyncio.run(probe()):
        sys.exit(0)
    time.sleep(1)
print("database not ready within 90s", file=sys.stderr)
sys.exit(1)
PY

cd "${BACKEND_DIR}"

run_alembic() {
  log "alembic $*"
  alembic "$@"
}

run_alembic upgrade head
alembic current | grep "(head)"

run_alembic downgrade base
if alembic current | grep -q "(head)"; then
  echo "unexpected head revision after downgrade base" >&2
  exit 1
fi

run_alembic upgrade head
alembic current | grep "(head)"

run_alembic upgrade head
alembic current | grep "(head)"

log "Migration roundtrip verification passed"
