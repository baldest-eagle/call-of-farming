@echo off
:: notifications.bat — Double-click to set up Discord/Slack notifications.
:: Opens an interactive menu for enabling, disabling, testing, and
:: configuring webhook notifications.

setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ════════════════════════════════════════════════════════════
::  Find a working Python
:: ════════════════════════════════════════════════════════════
set "PYTHON="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    for %%c in (python py) do (
        if not defined PYTHON (
            for /f "tokens=*" %%v in ('%%c --version 2^>^&1') do (
                echo %%v | findstr /r /c:"^Python 3\." >nul 2>&1
                if !errorLevel! equ 0 (
                    set "PYTHON=%%c"
                )
            )
            if not defined PYTHON (
                %%c --version >nul 2>&1
                if !errorLevel! neq 0 goto :try_next_%%c
            )
        )
        :try_next_%%c
    )
)

if not defined PYTHON (
    echo.
    echo ============================================================
    echo   Python is not installed or not working properly
    echo ============================================================
    echo.
    echo   The Farm Bot requires Python 3.8 or newer.
    echo.
    echo   If you haven't run setup yet, double-click setup.bat first.
    echo.
    echo   TO FIX:
    echo     1. Go to: https://www.python.org/downloads/
    echo     2. Download Python 3.x
    echo     3. Run installer — check "Add Python to PATH"
    echo     4. Click "Install Now"
    echo     5. Double-click setup.bat to set up the bot
    echo.
    echo ============================================================
    pause
    exit /b 1
)

"%PYTHON%" notifications.py

if %errorLevel% neq 0 (
    pause
)
