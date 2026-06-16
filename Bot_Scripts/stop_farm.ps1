# stop_farm.ps1
# Stops the 3-hour routine and kills active bot processes.

$taskName = "FarmCycle"

# 1. Remove the scheduled task
Write-Host "Removing scheduled task $taskName..."
schtasks /Delete /TN $taskName /F 2>$null

# 2. Kill active processes
Write-Host "Stopping active bot processes..."
taskkill /F /FI "IMAGENAME eq pythonw.exe" /FI "WINDOWTITLE eq *farm_cycle.py*" /T 2>$null
taskkill /F /IM "GnBots.exe" /T 2>$null
taskkill /F /IM "dnplayer.exe" /T 2>$null
taskkill /F /IM "Ld9BoxHeadless.exe" /T 2>$null
taskkill /F /IM "Ld9BoxSVC.exe" /T 2>$null

Write-Host "Routine stopped."
