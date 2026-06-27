@echo off
:: setup.bat — Double-click to set up the Farm Bot.
:: Self-elevates to admin and runs the Python setup script.
:: Place this in Bot_Scripts/ alongside setup_farm_bot.py

setlocal
cd /d "%~dp0"

:: Self-elevate to admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run the setup script
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

python setup_farm_bot.py
pause
