$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StatusPath = Join-Path $RepoRoot "reports\webui\standalone-webui.json"

if (-not (Test-Path $StatusPath)) {
    [pscustomobject]@{
        running = $false
        reason = "status file not found"
        status_path = $StatusPath
    } | ConvertTo-Json -Depth 4
    exit 1
}

$status = Get-Content $StatusPath -Raw | ConvertFrom-Json
$process = Get-Process -Id $status.pid -ErrorAction SilentlyContinue
$healthy = $false
$healthStatus = $null

if ($process) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $status.health_url -TimeoutSec 5
        $healthStatus = $response.StatusCode
        $healthy = $response.StatusCode -eq 200
    } catch {
        $healthStatus = $_.Exception.Message
    }
}

[pscustomobject]@{
    running = [bool]$process
    healthy = $healthy
    health_status = $healthStatus
    pid = $status.pid
    url = $status.url
    health_url = $status.health_url
    html_path = $status.html_path
    started_at = $status.started_at
    stop_command = $status.stop_command
} | ConvertTo-Json -Depth 4

if (-not $process -or -not $healthy) {
    exit 1
}
