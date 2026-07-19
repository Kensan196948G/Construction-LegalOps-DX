#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX: 全サービス疎通確認
# 利用方法:
#   bash infra/scripts/healthcheck.sh          # localhost に対して実行
#   BASE=https://legalops.mirai-dx-platform.com bash infra/scripts/healthcheck.sh
# ============================================================
set -euo pipefail

export TZ="${TZ:-Asia/Tokyo}"

BASE="${BASE:-http://localhost}"
BACKEND_BASE="${BACKEND_BASE:-http://localhost:8000}"
FRONTEND_BASE="${FRONTEND_BASE:-http://localhost:3000}"
TIMEOUT="${TIMEOUT:-5}"

PASS=0
FAIL=0
RESULTS=()

now() { date '+%Y-%m-%dT%H:%M:%S%z'; }

check_http() {
  local name="$1" url="$2" expect="${3:-200}"
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${TIMEOUT}" "${url}" || echo "000")
  if [[ "${code}" == "${expect}" ]]; then
    RESULTS+=("[OK] ${name} ${url} (${code})")
    PASS=$((PASS+1))
  else
    RESULTS+=("[NG] ${name} ${url} (got=${code}, expect=${expect})")
    FAIL=$((FAIL+1))
  fi
}

check_tcp() {
  local name="$1" host="$2" port="$3"
  if timeout "${TIMEOUT}" bash -c ">/dev/tcp/${host}/${port}" 2>/dev/null; then
    RESULTS+=("[OK] ${name} tcp://${host}:${port}")
    PASS=$((PASS+1))
  else
    RESULTS+=("[NG] ${name} tcp://${host}:${port}")
    FAIL=$((FAIL+1))
  fi
}

echo "=== Construction-LegalOps-DX healthcheck @ $(now) ==="
echo "BASE=${BASE}"
echo

check_http "nginx /healthz"        "${BASE}/healthz"               200
check_http "backend /healthz"      "${BACKEND_BASE}/healthz"       200
check_http "backend /api/v1/ping"  "${BACKEND_BASE}/api/v1/ping"   200 || true
check_http "frontend /"            "${FRONTEND_BASE}/"             200
check_tcp  "postgres"              "${POSTGRES_HOST:-localhost}"   "${POSTGRES_PORT:-5432}"
check_tcp  "redis"                 "${REDIS_HOST:-localhost}"      "${REDIS_PORT:-6379}"

printf '\n'
for line in "${RESULTS[@]}"; do
  printf '%s\n' "${line}"
done

printf '\nPASS=%d FAIL=%d\n' "${PASS}" "${FAIL}"

if (( FAIL > 0 )); then
  exit 1
fi
exit 0
