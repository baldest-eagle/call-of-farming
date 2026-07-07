@echo off
:: setup.bat — Double-click to set up the Farm Bot.
:: Self-elevates to admin and runs the Python setup script.
:: Place this in Bot_Scripts/ alongside setup_farm_bot.py

setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ════════════════════════════════════════════════════════════
::  Self-elevate to admin
:: ════════════════════════════════════════════════════════════
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: ════════════════════════════════════════════════════════════
::  Find a working Python (not just a stub like py.exe)
:: ════════════════════════════════════════════════════════════
set "PYTHON="

:: Try common Python commands and verify they actually work
for %%c in (python py) do (
    if not defined PYTHON (
        :: Run --version and capture output. Real Python prints "Python 3.x.x"
        for /f "tokens=*" %%v in ('%%c --version 2^>^&1') do (
            echo %%v | findstr /r /c:"^Python 3\." >nul 2>&1
            if !errorLevel! equ 0 (
                set "PYTHON=%%c"
            )
        )
        :: Also check exit code — py.exe with no runtimes returns non-zero
        if not defined PYTHON (
            %%c --version >nul 2>&1
        )
    )
)

:: Also try venv Python if it exists (created by a previous setup)
if not defined PYTHON (
    if exist ".venv\Scripts\python.exe" (
        set "PYTHON=.venv\Scripts\python.exe"
    )
)

:: ════════════════════════════════════════════════════════════
::  Handle missing/broken Python
:: ════════════════════════════════════════════════════════════
if not defined PYTHON (
    echo.
    echo ============================================================
    echo   Python is not installed or not working properly
    echo ============================================================
    echo.
    echo   The Farm Bot requires Python 3.8 or newer.
    echo.
    echo   If you saw an error like:
    echo     "internal error: no installs error: no runtimes are installed"
    echo   that means you have the Python launcher ^(py.exe^) but no
    echo   actual Python installed.
    echo.
    echo   TO FIX:
    echo.
    echo   1. Go to: https://www.python.org/downloads/
    echo   2. Download the latest Python 3.x installer
    echo   3. Run the installer
    echo   4. IMPORTANT: Check the box that says
    echo      "Add Python to PATH" at the bottom of the installer
    echo   5. Click "Install Now"
    echo   6. Close this window and double-click setup.bat again
    echo.
    echo ============================================================
    pause
    exit /b 1
)

:: Show which Python we're using
echo Using Python: %PYTHON%
%PYTHON% --version
echo.

:: ════════════════════════════════════════════════════════════
::  Run the setup script
:: ════════════════════════════════════════════════════════════
%PYTHON% setup_farm_bot.py
pause
