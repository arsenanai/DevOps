# setup_task.ps1
# Registers a Windows Task Scheduler task that runs the PR reviewer:
#   - immediately on every user logon
#   - then every 15 minutes while logged in
# Run once from PowerShell (no Administrator needed for current-user tasks).
#
# Usage:
#   .\setup_task.ps1
#
# To update the task after editing config.json or review_prs.py:
#   .\setup_task.ps1   (re-run, it will update in place)
#
# To remove the task:
#   Unregister-ScheduledTask -TaskName "RoqedPRReviewer" -Confirm:$false

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "review_prs.py"
$PythonExe  = (Get-Command python -ErrorAction Stop).Source
$TaskName   = "RoqedPRReviewer"
$LogFile    = Join-Path $ScriptDir "reviewer.log"

# Use pythonw.exe (windowless) so no CMD window flashes when the task runs.
# pythonw.exe lives next to python.exe in the same Python installation directory.
$PythonWExe = Join-Path (Split-Path $PythonExe -Parent) "pythonw.exe"
if (-not (Test-Path $PythonWExe)) {
    Write-Warning "pythonw.exe not found at $PythonWExe -- falling back to python.exe (window will briefly appear)."
    $PythonWExe = $PythonExe
}
Write-Host "Using interpreter: $PythonWExe"

# Build scheduled task components
$Action = New-ScheduledTaskAction `
    -Execute $PythonWExe `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ScriptDir

# Trigger 1: run at every logon (catches the first run after system boot)
$TriggerLogon = New-ScheduledTaskTrigger `
    -AtLogOn `
    -User $env:USERNAME

# Trigger 2: repeat every 15 minutes while logged in
$TriggerRepeat = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)

$Triggers = @($TriggerLogon, $TriggerRepeat)

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Minutes 10) `
    -RestartCount        2 `
    -RestartInterval     (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -RunOnlyIfNetworkAvailable

$Principal = New-ScheduledTaskPrincipal `
    -UserId    $env:USERNAME `
    -LogonType Interactive `
    -RunLevel  Limited

# Register or update
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    Set-ScheduledTask -TaskName $TaskName `
        -Action $Action -Trigger $Triggers -Settings $Settings -Principal $Principal
    Write-Host "Task '$TaskName' updated."
} else {
    Register-ScheduledTask -TaskName $TaskName `
        -Action $Action -Trigger $Triggers -Settings $Settings -Principal $Principal `
        -Description "AI PR reviewer: posts Claude review on PRs that request review from arsenanai"
    Write-Host "Task '$TaskName' registered."
}

Write-Host ""
Write-Host "All done. The reviewer runs on logon + every 15 minutes."
Write-Host "  Logs  : $LogFile"
Write-Host "  State : $(Join-Path $ScriptDir 'reviewed_prs.json')"
Write-Host "  Config: $(Join-Path $ScriptDir 'config.json')"
Write-Host ""
Write-Host "Run immediately  : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Check last run   : Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "Remove task      : Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
