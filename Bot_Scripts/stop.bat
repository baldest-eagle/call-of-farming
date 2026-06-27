@echo off
:: stop.bat — Double-click to stop the bot and clean up.
:: Kills GnBots, LDPlayer, and any running farm_cycle processes.

setlocal
cd /d "%~dp0"

echo Stopping Farm Bot...

:: Kill farm cycle Python processes (best effort)
taskkill /F /FI "WINDOWTITLE eq *farm_cycle*" /T 2>nul

:: Kill GnBots
taskkill /F /IM "GnBots.exe" /T 2>nul

:: Kill LDPlayer
taskkill /F /IM "dnplayer.exe" /T 2>nul
taskkill /F /IM "Ld9BoxHeadless.exe" /T 2>nul
taskkill /F /IM "Ld9BoxSVC.exe" /T 2>nul

echo.
echo All bot processes stopped.
timeout /t 3 >nul
