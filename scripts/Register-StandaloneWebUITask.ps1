param(
    [switch]$Register,
    [switch]$Unregister,
    [switch]$RunNow,
    [string]$TaskName = "Construction-LegalOps-DX-Standalone-WebUI"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Get-Item (Join-Path $PSScriptRoot "..")).FullName
$StartScript = Join-Path $RepoRoot "scripts\Start-StandaloneWebUI.ps1"
$TaskPath = "\Construction-LegalOps-DX\"

function Get-WebUITask {
    Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue
}

function Get-WebUITaskStatusObject {
    $task = Get-WebUITask
    if (-not $task) {
        return [pscustomobject]@{
            registered = $false
            task_name = $TaskName
            task_path = $TaskPath
            start_script = $StartScript
        }
    }

    $info = Get-ScheduledTaskInfo -TaskPath $TaskPath -TaskName $TaskName
    return [pscustomobject]@{
        registered = $true
        task_name = $TaskName
        task_path = $TaskPath
        state = $task.State
        last_run_time = $info.LastRunTime
        last_task_result = $info.LastTaskResult
        next_run_time = $info.NextRunTime
        start_script = $StartScript
    }
}

if ($Register -and $Unregister) {
    throw "Use only one of -Register or -Unregister."
}

if ($Register) {
    if (-not (Test-Path $StartScript)) {
        throw "Start script not found: $StartScript"
    }

    $action = New-ScheduledTaskAction `
        -Execute "pwsh.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`"" `
        -WorkingDirectory $RepoRoot

    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Limited

    $settings = New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0)

    $task = New-ScheduledTask `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Keeps the Construction-LegalOps-DX standalone WebUI available on logon."

    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -InputObject $task `
        -Force | Out-Null
}

if ($Unregister) {
    $task = Get-WebUITask
    if ($task) {
        Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false
    }
}

if ($RunNow) {
    $task = Get-WebUITask
    if (-not $task) {
        throw "Task is not registered. Run with -Register first."
    }
    Start-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName
}

Get-WebUITaskStatusObject | ConvertTo-Json -Depth 4
