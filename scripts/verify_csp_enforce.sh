#!/usr/bin/env bash
# ============================================================
# CSP enforce 適用状態の検証 (#24)
# - security-headers.conf に enforce ヘッダがあり Report-Only が無いこと
# - enforce.conf と security-headers.conf の CSP 行が一致すること
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="${REPO_ROOT}/infra/nginx/security-headers.conf"
ENFORCE="${REPO_ROOT}/infra/nginx/security-headers.enforce.conf"

pass=0
fail=0

check() {
  local desc="$1" result="$2"
  if [ "$result" = "0" ]; then
    pass=$((pass + 1))
    printf '✅ %s\n' "$desc"
  else
    fail=$((fail + 1))
    printf '❌ %s\n' "$desc"
  fi
}

grep -q 'Content-Security-Policy "' "$CONF"; check "security-headers.conf に enforce CSP あり" "$?"
if grep -q 'Content-Security-Policy-Report-Only' "$CONF"; then
  check "Report-Only が残っていない" "1"
else
  check "Report-Only が残っていない" "0"
fi

enforce_line=$(grep -o 'Content-Security-Policy "[^"]*"' "$ENFORCE" | head -1)
active_line=$(grep -o 'Content-Security-Policy "[^"]*"' "$CONF" | head -1)
if [ -n "$enforce_line" ] && [ "$enforce_line" = "$active_line" ]; then
  check "enforce.conf と security-headers.conf の CSP が一致" "0"
else
  check "enforce.conf と security-headers.conf の CSP が一致" "1"
fi

printf '\n📊 CSP enforce verify: Passed %d Failed %d\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
