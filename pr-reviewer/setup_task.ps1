# setup_task.ps1
# Registers a Windows Task Scheduler task that runs the PR reviewer:
#   - schedule is configurable in config.json under the "schedule" section
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
$ConfigPath = Join-Path $ScriptDir "config.json"
$PythonExe  = (Get-Command python -ErrorAction Stop).Source
$TaskName   = "RoqedPRReviewer"
$LogFile    = Join-Path $ScriptDir "reviewer.log"

# Read configuration from config.json
if (-not (Test-Path $ConfigPath)) {
    Write-Error "Config file not found: $ConfigPath"
    Write-Error "Please copy config.json.example to config.json and configure it."
    exit 1
}

try {
    $Config = Get-Content $ConfigPath | ConvertFrom-Json
    $Schedule = $Config.schedule
    
    # Default values if schedule section is missing
    if (-not $Schedule) {
        $Schedule = @{
            enabled_days = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
            start_time = "00:00"
            end_time = "24:00"
            frequency_hours = 1
        }
    }
    
    $EnabledDays = $Schedule.enabled_days
    $StartTime = $Schedule.start_time
    $EndTime = $Schedule.end_time
    $FrequencyHours = $Schedule.frequency_hours
    
    Write-Host "Schedule configuration:"
    Write-Host "  Days: $($EnabledDays -join ', ')"
    Write-Host "  Time: $StartTime - $EndTime"
    Write-Host "  Frequency: every $FrequencyHours hour(s)"
} catch {
    Write-Error "Failed to read config.json: $_"
    exit 1
}

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

# Create a weekly trigger using configuration from config.json
$Triggers = @()
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -At $StartTime `
    -DaysOfWeek $EnabledDays

# Calculate duration between start and end times
$StartDateTime = [DateTime]::Parse($StartTime)
$EndDateTime = [DateTime]::Parse($EndTime)
$DurationHours = ($EndDateTime - $StartDateTime).TotalHours

# Handle case where end time is next day (e.g., 22:00 to 06:00)
if ($DurationHours -lt 0) {
    $DurationHours += 24
}

# Manually build the repetition pattern using config values
$tempTrigger = New-ScheduledTaskTrigger -Once -At $StartTime `
    -RepetitionInterval (New-TimeSpan -Hours $FrequencyHours) `
    -RepetitionDuration (New-TimeSpan -Hours $DurationHours)
$trigger.Repetition = $tempTrigger.Repetition
$trigger.Repetition.StopAtDurationEnd = $false
$Triggers += $trigger

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Minutes 60) `
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
Write-Host "All done. The reviewer will run every $FrequencyHours hour(s) on $($EnabledDays -join ', ') from $StartTime to $EndTime."
Write-Host "  Logs  : $LogFile"
Write-Host "  State : $(Join-Path $ScriptDir 'reviewed_prs.json')"
Write-Host "  Config: $(Join-Path $ScriptDir 'config.json')"
Write-Host ""
Write-Host "Run immediately  : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Check last run   : Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "Remove task      : Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
