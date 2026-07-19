#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — unhealthy service watchdog drill
#
# Default mode is report-only. Use --restart only after human approval.
#
# Usage:
#   ./scripts/check_unhealthy_services.sh
#   ./scripts/check_unhealthy_services.sh --compose-file infra/docker/docker-compose.yml
#   ./scripts/check_unhealthy_services.sh --restart backend
#   ./scripts/check_unhealthy_services.sh --restart-all
# ============================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="infra/docker/docker-compose.yml"
MODE="report"
TARGET_SERVICE=""

usage() {
  sed -n '1,18p' "$0"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --compose-file)
      COMPOSE_FILE="${2:?--compose-file requires a path}"
      shift 2
      ;;
    --restart)
      MODE="restart-one"
      TARGET_SERVICE="${2:?--restart requires a service name}"
      shift 2
      ;;
    --restart-all)
      MODE="restart-all"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

COMPOSE=(docker compose -f "$COMPOSE_FILE")

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker command not found" >&2
  exit 127
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
  exit 2
fi

collect_unhealthy() {
  local ps_json
  ps_json="$(mktemp)"
  "${COMPOSE[@]}" ps --format json > "$ps_json"
  python3 - "$ps_json" <<'PY'
import json
import sys

raw = open(sys.argv[1], encoding="utf-8").read().strip()
if not raw:
    sys.exit(0)

try:
    parsed = json.loads(raw)
except json.JSONDecodeError:
    parsed = [json.loads(line) for line in raw.splitlines() if line.strip()]

if isinstance(parsed, dict):
    parsed = [parsed]

for item in parsed:
    service = item.get("Service") or item.get("Name") or ""
    health = (item.get("Health") or item.get("State") or item.get("Status") or "").lower()
    if "unhealthy" in health:
        print(service)
PY
  rm -f "$ps_json"
}

mapfile -t UNHEALTHY < <(collect_unhealthy)

if [ "${#UNHEALTHY[@]}" -eq 0 ]; then
  echo "OK: no unhealthy services detected"
  exit 0
fi

echo "UNHEALTHY services detected:"
printf ' - %s\n' "${UNHEALTHY[@]}"

case "$MODE" in
  report)
    echo "Report-only mode. Human approval is required before restart."
    exit 1
    ;;
  restart-one)
    found="false"
    for service in "${UNHEALTHY[@]}"; do
      if [ "$service" = "$TARGET_SERVICE" ]; then
        found="true"
      fi
    done
    if [ "$found" != "true" ]; then
      echo "ERROR: requested service is not currently unhealthy: $TARGET_SERVICE" >&2
      exit 2
    fi
    echo "Restarting approved unhealthy service: $TARGET_SERVICE"
    "${COMPOSE[@]}" restart "$TARGET_SERVICE"
    ;;
  restart-all)
    echo "Restarting all unhealthy services after approval:"
    printf ' - %s\n' "${UNHEALTHY[@]}"
    "${COMPOSE[@]}" restart "${UNHEALTHY[@]}"
    ;;
esac
