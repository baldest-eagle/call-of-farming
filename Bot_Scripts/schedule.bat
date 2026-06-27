@echo off
:: schedule.bat — Set up Windows Task Scheduler for auto-cycling.
:: Self-elevates to admin (required for /RL HIGHEST).

setlocal
cd /d "%~dp0"

:: Self-elevate to admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set "PYTHON=python"
if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHON=.venv\Scripts\pythonw.exe"
)

echo Setting up Task Scheduler for auto-cycling...
"%PYTHON%" schedule_tasks.py
pause
