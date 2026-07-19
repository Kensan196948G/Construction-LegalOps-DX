param(
    [Parameter(Mandatory = $true)]
    [string]$HostName,

    [Parameter(Mandatory = $true)]
    [string]$RemoteRepo,

    [ValidateSet("install", "start", "stop", "restart", "status", "health", "uninstall")]
    [string]$Action = "status",

    [ValidateSet("user", "system")]
    [string]$Mode = "user",

    [switch]$Linger,
    [switch]$DryRun,
    [switch]$JsonStatus,
    [switch]$PrintUnit,
    [string]$Ssh = "ssh"
)

$ErrorActionPreference = "Stop"

function Quote-Bash([string]$Value) {
    return "'" + ($Value -replace "'", "'\''") + "'"
}

$modeArg = if ($Mode -eq "system") { "--system" } else { "--user" }
$lingerArg = if ($Linger) { " --linger" } else { "" }
$printUnitArg = if ($PrintUnit) { " --print-unit" } else { "" }
$remoteRepoQuoted = Quote-Bash $RemoteRepo

$remoteCommand = @"
set -euo pipefail
cd $remoteRepoQuoted
bash scripts/install_standalone_webui_systemd.sh $modeArg$lingerArg$printUnitArg $Action
if [ -f reports/webui/standalone-webui.json ]; then
  printf '\n--- standalone-webui.json ---\n'
  cat reports/webui/standalone-webui.json
  if [ '$Action' != 'health' ]; then
  printf '\n--- health ---\n'
  python3 - <<'PY'
import json
import sys
from pathlib import Path
from urllib.request import urlopen

status = json.loads(Path("reports/webui/standalone-webui.json").read_text(encoding="utf-8"))
try:
    body = urlopen(status["health_url"], timeout=10).read().decode("utf-8").strip()
    print(json.dumps({"healthy": body == "ok", "health_url": status["health_url"], "body": body}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"healthy": False, "health_url": status.get("health_url"), "error": str(exc)}, ensure_ascii=False))
    sys.exit(1)
PY
  fi
fi
"@

if ($DryRun) {
    [pscustomobject]@{
        host = $HostName
        remote_repo = $RemoteRepo
        mode = $Mode
        action = $Action
        linger = [bool]$Linger
        print_unit = [bool]$PrintUnit
        ssh_command = "$Ssh $HostName bash -lc <remote-command>"
        remote_command = $remoteCommand
    } | ConvertTo-Json -Depth 5
    exit 0
}

$output = & $Ssh $HostName "bash -lc $(Quote-Bash $remoteCommand)"

if ($JsonStatus) {
    $jsonLines = @($output | Where-Object { $_ -match '^\s*\{' })
    if ($jsonLines.Count -gt 0) {
        $jsonLines[-1]
        exit 0
    }
}

$output
