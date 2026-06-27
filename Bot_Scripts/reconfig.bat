@echo off
:: reconfig.bat — Re-run just the configuration step.
:: Use this to change your GnBots path, LDPlayer path, or webhook URL
:: without redoing the full setup.

setlocal
cd /d "%~dp0"

set "PYTHON=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

echo Re-running configuration...
"%PYTHON%" setup_farm_bot.py --reconfig
pause
