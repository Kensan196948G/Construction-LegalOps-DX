param(
    [string]$HostAddress = "auto",
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StatusPath = Join-Path $RepoRoot "reports\webui\standalone-webui.json"
$OutLog = Join-Path $RepoRoot "reports\webui\standalone-webui.out.log"
$ErrLog = Join-Path $RepoRoot "reports\webui\standalone-webui.err.log"

New-Item -ItemType Directory -Force -Path (Split-Path $StatusPath) | Out-Null

if (Test-Path $StatusPath) {
    try {
        $status = Get-Content $StatusPath -Raw | ConvertFrom-Json
        $process = Get-Process -Id $status.pid -ErrorAction SilentlyContinue
        if ($process) {
            try {
                $health = Invoke-WebRequest -UseBasicParsing -Uri $status.health_url -TimeoutSec 5
                if ($health.StatusCode -eq 200) {
                    $status | ConvertTo-Json -Depth 4
                    exit 0
                }
            } catch {
                # Process exists but health is not ready; continue and restart.
            }
            Stop-Process -Id $status.pid -Force -ErrorAction SilentlyContinue
        }
    } catch {
        # Stale or broken status file; overwrite below.
    }
}

$argsList = @("scripts/serve_standalone_webui.py", "--host", $HostAddress, "--status", $StatusPath)
if ($Port -gt 0) {
    $argsList += @("--port", [string]$Port)
}

$process = Start-Process `
    -WindowStyle Hidden `
    -FilePath "python" `
    -ArgumentList $argsList `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    if (Test-Path $StatusPath) {
        $status = Get-Content $StatusPath -Raw | ConvertFrom-Json
        try {
            $health = Invoke-WebRequest -UseBasicParsing -Uri $status.health_url -TimeoutSec 3
            if ($health.StatusCode -eq 200) {
                $status | ConvertTo-Json -Depth 4
                exit 0
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } else {
        Start-Sleep -Milliseconds 500
    }
}

throw "Standalone WebUI did not become healthy. Launcher PID: $($process.Id). See $ErrLog"
