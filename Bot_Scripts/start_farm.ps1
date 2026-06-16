# start_farm.ps1
# Boots the farm bot and schedules it to run every 3 hours.
# Paths are auto-detected relative to this script's location.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path (Split-Path -Parent $([System.Diagnostics.Process]::GetCurrentProcess().StartInfo.FileName)) "pythonw.exe"

# Fallback: try to find pythonw.exe via the PATH
if (-not (Test-Path $pythonExe)) {
    $pythonExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $pythonExe) {
    # Last resort: use python.exe
    $pythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}

$scriptPath = Join-Path $ScriptDir "farm_cycle.py"
$taskName = "FarmCycle"

# 1. Kill any existing instances to avoid conflicts
Write-Host "Cleaning up any existing bot processes..."
# Using taskkill for more reliability across permissions
taskkill /F /FI "IMAGENAME eq pythonw.exe" /FI "WINDOWTITLE eq *farm_cycle.py*" /T 2>$null
taskkill /F /IM "GnBots.exe" /T 2>$null
taskkill /F /IM "dnplayer.exe" /T 2>$null
taskkill /F /IM "Ld9BoxHeadless.exe" /T 2>$null
taskkill /F /IM "Ld9BoxSVC.exe" /T 2>$null

# 2. Schedule the task for every 3 hours starting from now
$startTime = (Get-Date).AddMinutes(1).ToString("HH:mm")
Write-Host "Scheduling $taskName to run every 3 hours starting at $startTime..."
Write-Host "  Python:  $pythonExe"
Write-Host "  Script:  $scriptPath"
Write-Host "  WorkDir: $ScriptDir"
schtasks /Delete /TN $taskName /F 2>$null
# /RI 180 = 3 hours. /DU 24:00 = duration 24 hours (repeats daily)
schtasks /Create /TN $taskName /TR "$pythonExe $scriptPath" /SC DAILY /ST $startTime /RI 180 /DU 24:00 /RL HIGHEST /F

# 3. Launch immediately
Write-Host "Booting Farm Bot project..."
Start-Process -FilePath $pythonExe -ArgumentList $scriptPath -WorkingDirectory $ScriptDir

Write-Host "Routine started and scheduled."
