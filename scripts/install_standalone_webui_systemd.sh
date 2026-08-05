#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-construction-legalops-standalone-webui}"
MODE="user"
ACTION="install"
ENABLE_LINGER=0
PRINT_UNIT=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/install_standalone_webui_systemd.sh [--user|--system] [--linger] [--print-unit] [install|start|stop|restart|status|health|uninstall]

Examples:
  scripts/install_standalone_webui_systemd.sh --user install
  scripts/install_standalone_webui_systemd.sh --user --linger install
  scripts/install_standalone_webui_systemd.sh --user start
  scripts/install_standalone_webui_systemd.sh --user status
  scripts/install_standalone_webui_systemd.sh --user health

Environment:
  SERVICE_NAME  Override the unit name. Default: construction-legalops-standalone-webui
  STANDALONE_WEBUI_HOST  Optional bind host override (e.g. 0.0.0.0 or a fixed LAN IP).
                         If unset, the server auto-selects the current route-source IP.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      MODE="user"
      shift
      ;;
    --system)
      MODE="system"
      shift
      ;;
    --linger)
      ENABLE_LINGER=1
      shift
      ;;
    --print-unit)
      PRINT_UNIT=1
      shift
      ;;
    install|start|stop|restart|status|health|uninstall)
      ACTION="$1"
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

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
UNIT_NAME="${SERVICE_NAME}.service"

if [[ "${MODE}" == "user" ]]; then
  UNIT_DIR="${HOME}/.config/systemd/user"
  SYSTEMCTL=(systemctl --user)
  ENABLE_ARGS=(enable "${UNIT_NAME}")
  STOP_COMMAND="systemctl --user stop ${UNIT_NAME}"
else
  UNIT_DIR="/etc/systemd/system"
  SYSTEMCTL=(sudo systemctl)
  ENABLE_ARGS=(enable "${UNIT_NAME}")
  STOP_COMMAND="sudo systemctl stop ${UNIT_NAME}"
fi

UNIT_PATH="${UNIT_DIR}/${UNIT_NAME}"

HOST_ENV_LINE=""
if [[ -n "${STANDALONE_WEBUI_HOST:-}" ]]; then
  HOST_ENV_LINE="Environment=\"STANDALONE_WEBUI_HOST=${STANDALONE_WEBUI_HOST}\""
fi

render_unit() {
  cat <<UNIT
[Unit]
Description=Construction-LegalOps-DX Standalone WebUI
Documentation=file://${REPO_ROOT}/README.md
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${REPO_ROOT}
Environment="STANDALONE_WEBUI_STOP_COMMAND=${STOP_COMMAND}"
${HOST_ENV_LINE}
ExecStart=${PYTHON_BIN} ${REPO_ROOT}/scripts/serve_standalone_webui.py
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
UNIT
}

write_unit() {
  local unit_tmp
  unit_tmp="$(mktemp)"
  render_unit > "${unit_tmp}"
  if [[ "${MODE}" == "system" ]]; then
    sudo install -d -m 0755 "${UNIT_DIR}"
    sudo install -m 0644 "${unit_tmp}" "${UNIT_PATH}"
  else
    mkdir -p "${UNIT_DIR}"
    install -m 0644 "${unit_tmp}" "${UNIT_PATH}"
  fi
  rm -f "${unit_tmp}"
}

daemon_reload() {
  "${SYSTEMCTL[@]}" daemon-reload
}

health() {
  local status_file="${REPO_ROOT}/reports/webui/standalone-webui.json"
  if [[ ! -f "${status_file}" ]]; then
    echo "Standalone WebUI status file not found: ${status_file}" >&2
    return 1
  fi
  python3 - <<'PY'
import json
import sys
from pathlib import Path
from urllib.request import urlopen

status_path = Path("reports/webui/standalone-webui.json")
status = json.loads(status_path.read_text(encoding="utf-8"))
try:
    body = urlopen(status["health_url"], timeout=10).read().decode("utf-8").strip()
except Exception as exc:
    print(json.dumps({"healthy": False, "health_url": status.get("health_url"), "error": str(exc)}, ensure_ascii=False))
    sys.exit(1)

result = {
    "healthy": body == "ok",
    "url": status.get("url"),
    "health_url": status.get("health_url"),
    "body": body,
    "pid": status.get("pid"),
    "stop_command": status.get("stop_command"),
}
print(json.dumps(result, ensure_ascii=False))
sys.exit(0 if result["healthy"] else 1)
PY
}

wait_health() {
  local attempts="${1:-20}"
  local delay="${2:-0.5}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if health; then
      return 0
    fi
    sleep "${delay}"
  done
  echo "Standalone WebUI did not become healthy after ${attempts} attempts." >&2
  return 1
}

case "${ACTION}" in
  install)
    if [[ "${PRINT_UNIT}" -eq 1 ]]; then
      render_unit
      exit 0
    fi
    write_unit
    if [[ "${MODE}" == "user" && "${ENABLE_LINGER}" -eq 1 ]]; then
      loginctl enable-linger "${USER}"
    fi
    daemon_reload
    "${SYSTEMCTL[@]}" "${ENABLE_ARGS[@]}"
    "${SYSTEMCTL[@]}" restart "${UNIT_NAME}"
    wait_health
    ;;
  start)
    "${SYSTEMCTL[@]}" start "${UNIT_NAME}"
    wait_health
    ;;
  stop)
    "${SYSTEMCTL[@]}" stop "${UNIT_NAME}"
    ;;
  restart)
    "${SYSTEMCTL[@]}" restart "${UNIT_NAME}"
    wait_health
    ;;
  status)
    "${SYSTEMCTL[@]}" status "${UNIT_NAME}" --no-pager
    ;;
  health)
    health
    ;;
  uninstall)
    "${SYSTEMCTL[@]}" disable --now "${UNIT_NAME}" 2>/dev/null || true
    rm -f "${UNIT_PATH}"
    daemon_reload
    ;;
esac

if [[ -f "${REPO_ROOT}/reports/webui/standalone-webui.json" ]]; then
  cat "${REPO_ROOT}/reports/webui/standalone-webui.json"
fi
