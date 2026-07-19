$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StatusPath = Join-Path $RepoRoot "reports\webui\standalone-webui.json"

if (-not (Test-Path $StatusPath)) {
    Write-Output "Standalone WebUI status file not found."
    exit 0
}

$status = Get-Content $StatusPath -Raw | ConvertFrom-Json
$process = Get-Process -Id $status.pid -ErrorAction SilentlyContinue

if ($process) {
    Stop-Process -Id $status.pid -Force
    Write-Output "Stopped Standalone WebUI PID $($status.pid)."
} else {
    Write-Output "Standalone WebUI PID $($status.pid) is not running."
}
