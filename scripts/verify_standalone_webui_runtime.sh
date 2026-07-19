#!/usr/bin/env bash
# verify_standalone_webui_runtime.sh — read-only runtime checks for the
# standalone WebUI served by systemd.
#
# This script does not start, stop, restart, install, or mutate the service.
# It only verifies that the already-running validation WebUI is reachable and
# serving the exact standalone HTML source expected by release approvers.

set -euo pipefail

WEBUI_URL="${STANDALONE_WEBUI_URL:-http://192.168.0.185:38100/}"
WEBUI_HEALTH_URL="${STANDALONE_WEBUI_HEALTH_URL:-${WEBUI_URL%/}/healthz}"
WEBUI_SOURCE_URL="${STANDALONE_WEBUI_SOURCE_URL:-${WEBUI_URL%/}/standalone-source}"
WEBUI_SERVICE="${STANDALONE_WEBUI_SERVICE:-construction-legalops-standalone-webui.service}"
EXPECTED_SOURCE="${STANDALONE_WEBUI_SOURCE_PATH:-$(pwd)/docs/Construction-LegalOps-DX (Standalone).html}"
STATUS_PATH="${STANDALONE_WEBUI_STATUS_PATH:-$(pwd)/reports/webui/standalone-webui.json}"
EXPECTED_UNIT_START="${STANDALONE_WEBUI_EXPECTED_UNIT_START:-$(pwd)/scripts/serve_standalone_webui.py}"
EXPECTED_WORKDIR="${STANDALONE_WEBUI_EXPECTED_WORKDIR:-$(pwd)}"
PORT_RANGE_START="${STANDALONE_WEBUI_PORT_RANGE_START:-38100}"
PORT_RANGE_END="${STANDALONE_WEBUI_PORT_RANGE_END:-38999}"

PASS=0
FAIL=0

pass() {
  echo "✅ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ $1"
  FAIL=$((FAIL + 1))
}

contains() {
  local haystack="$1"
  local needle="$2"
  grep -Fq "$needle" <<<"${haystack}"
}

json_value() {
  local key="$1"
  python3 - "${STATUS_PATH}" "${key}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)
value = payload.get(key, "")
print(value)
PY
}

echo "================================================"
echo "🖥️ Standalone WebUI Runtime Preflight"
echo "================================================"

if [ -s "${STATUS_PATH}" ]; then
  pass "Standalone WebUI status JSON exists"
else
  fail "Standalone WebUI status JSON missing or empty: ${STATUS_PATH}"
fi

python3 -m json.tool "${STATUS_PATH}" >/dev/null 2>&1 && pass "Standalone WebUI status JSON is valid" || fail "Standalone WebUI status JSON is invalid"

STATUS_HOST="$(json_value host)"
STATUS_PORT="$(json_value port)"
STATUS_URL="$(json_value url)"
STATUS_HEALTH_URL="$(json_value health_url)"
STATUS_HTML_PATH="$(json_value html_path)"
STATUS_STOP_COMMAND="$(json_value stop_command)"
STATUS_PID="$(json_value pid)"

if [ "${STATUS_URL}" = "${WEBUI_URL}" ]; then
  pass "Standalone WebUI status URL matches expected reachable URL"
else
  fail "Standalone WebUI status URL is ${STATUS_URL:-empty}; expected ${WEBUI_URL}"
fi

if [ "${STATUS_HEALTH_URL}" = "${WEBUI_HEALTH_URL}" ]; then
  pass "Standalone WebUI status health URL matches expected health URL"
else
  fail "Standalone WebUI status health URL is ${STATUS_HEALTH_URL:-empty}; expected ${WEBUI_HEALTH_URL}"
fi

if [ "${STATUS_HTML_PATH}" = "${EXPECTED_SOURCE}" ]; then
  pass "Standalone WebUI status HTML path matches expected source"
else
  fail "Standalone WebUI status HTML path is ${STATUS_HTML_PATH:-empty}; expected ${EXPECTED_SOURCE}"
fi

if [ "${STATUS_STOP_COMMAND}" = "systemctl --user stop ${WEBUI_SERVICE}" ]; then
  pass "Standalone WebUI status stop command is systemd user stop"
else
  fail "Standalone WebUI status stop command is ${STATUS_STOP_COMMAND:-empty}; expected systemd user stop"
fi

if [ -n "${STATUS_PORT}" ] && [ "${STATUS_PORT}" -ge "${PORT_RANGE_START}" ] && [ "${STATUS_PORT}" -le "${PORT_RANGE_END}" ]; then
  pass "Standalone WebUI status port is within auto allocation range (${STATUS_PORT})"
else
  fail "Standalone WebUI status port ${STATUS_PORT:-empty} is outside ${PORT_RANGE_START}-${PORT_RANGE_END}"
fi

if hostname -I | tr ' ' '\n' | grep -Fxq "${STATUS_HOST}"; then
  pass "Standalone WebUI status host is assigned to this Linux host (${STATUS_HOST})"
else
  fail "Standalone WebUI status host ${STATUS_HOST:-empty} is not assigned to this Linux host"
fi

if [ -s "${EXPECTED_SOURCE}" ]; then
  pass "Standalone source HTML exists"
else
  fail "Standalone source HTML missing or empty: ${EXPECTED_SOURCE}"
fi

EXPECTED_SIZE="$(stat -c %s "${EXPECTED_SOURCE}" 2>/dev/null || echo 0)"
if [ "${EXPECTED_SIZE}" -gt 1000000 ]; then
  pass "Standalone source HTML size is substantial (${EXPECTED_SIZE} bytes)"
else
  fail "Standalone source HTML size is unexpectedly small (${EXPECTED_SIZE} bytes)"
fi

SERVICE_STATE="$(systemctl --user is-active "${WEBUI_SERVICE}" 2>/dev/null || true)"
if [ "${SERVICE_STATE}" = "active" ]; then
  pass "Standalone WebUI systemd service is active"
else
  fail "Standalone WebUI systemd service state is ${SERVICE_STATE:-unknown}; expected active"
fi

SERVICE_ENABLED="$(systemctl --user is-enabled "${WEBUI_SERVICE}" 2>/dev/null || true)"
if [ "${SERVICE_ENABLED}" = "enabled" ]; then
  pass "Standalone WebUI systemd service is enabled"
else
  fail "Standalone WebUI systemd service enabled state is ${SERVICE_ENABLED:-unknown}; expected enabled"
fi

UNIT_TEXT="$(systemctl --user cat "${WEBUI_SERVICE}" 2>/dev/null || true)"
contains "${UNIT_TEXT}" "WorkingDirectory=${EXPECTED_WORKDIR}" && pass "Standalone WebUI systemd unit uses repository working directory" || fail "Standalone WebUI systemd unit missing repository working directory"
contains "${UNIT_TEXT}" "ExecStart=" && contains "${UNIT_TEXT}" "${EXPECTED_UNIT_START}" && pass "Standalone WebUI systemd unit starts serve_standalone_webui.py" || fail "Standalone WebUI systemd unit missing serve_standalone_webui.py ExecStart"
contains "${UNIT_TEXT}" "Restart=always" && pass "Standalone WebUI systemd unit restarts on failure" || fail "Standalone WebUI systemd unit missing Restart=always"
contains "${UNIT_TEXT}" "NoNewPrivileges=true" && pass "Standalone WebUI systemd unit has NoNewPrivileges" || fail "Standalone WebUI systemd unit missing NoNewPrivileges=true"
contains "${UNIT_TEXT}" "STANDALONE_WEBUI_STOP_COMMAND=systemctl --user stop ${WEBUI_SERVICE}" && pass "Standalone WebUI systemd unit exports stop command" || fail "Standalone WebUI systemd unit missing stop command environment"

if ss -ltnp 2>/dev/null | grep -F "${STATUS_HOST}:${STATUS_PORT}" | grep -Fq "${STATUS_PID}"; then
  pass "Standalone WebUI process is listening on status host and port"
else
  fail "Standalone WebUI process is not listening on ${STATUS_HOST}:${STATUS_PORT} with pid ${STATUS_PID:-empty}"
fi

HEALTH_BODY="$(curl -fsS "${WEBUI_HEALTH_URL}" 2>/dev/null || true)"
if [ "${HEALTH_BODY}" = "ok" ]; then
  pass "Standalone WebUI health endpoint returns ok"
else
  fail "Standalone WebUI health endpoint returned ${HEALTH_BODY:-no response}"
fi

HEADERS="$(curl -fsSI "${WEBUI_URL}" 2>/dev/null || true)"
contains "${HEADERS}" "200 OK" && pass "Standalone WebUI HEAD returns 200 OK" || fail "Standalone WebUI HEAD missing 200 OK"
contains "${HEADERS}" "Content-Type: text/html; charset=utf-8" && pass "Standalone WebUI Content-Type is HTML" || fail "Standalone WebUI Content-Type is not expected HTML"
contains "${HEADERS}" "Content-Length: ${EXPECTED_SIZE}" && pass "Standalone WebUI Content-Length matches source HTML" || fail "Standalone WebUI Content-Length does not match source HTML"
contains "${HEADERS}" "Cache-Control: no-store" && pass "Standalone WebUI no-store cache header is present" || fail "Standalone WebUI no-store cache header missing"
contains "${HEADERS}" "X-Content-Type-Options: nosniff" && pass "Standalone WebUI nosniff header is present" || fail "Standalone WebUI nosniff header missing"
contains "${HEADERS}" "X-Frame-Options: SAMEORIGIN" && pass "Standalone WebUI frame guard header is present" || fail "Standalone WebUI frame guard header missing"
contains "${HEADERS}" "Content-Security-Policy:" && pass "Standalone WebUI CSP header is present" || fail "Standalone WebUI CSP header missing"

SOURCE_BODY="$(curl -fsS "${WEBUI_SOURCE_URL}" 2>/dev/null || true)"
if [ "${SOURCE_BODY}" = "${EXPECTED_SOURCE}" ]; then
  pass "Standalone WebUI source endpoint matches expected HTML path"
else
  fail "Standalone WebUI source endpoint returned ${SOURCE_BODY:-no response}; expected ${EXPECTED_SOURCE}"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Standalone WebUI runtime preflight failed"
  exit 1
fi

echo "✅ Standalone WebUI runtime preflight passed"
exit 0
