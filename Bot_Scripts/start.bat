@echo off
:: start.bat — Double-click to run one farm cycle.
:: Uses the venv Python if available, otherwise system Python.

setlocal enabledelayedexpansion
cd /d "%~dp0"

:: ════════════════════════════════════════════════════════════
::  Find a working Python
:: ════════════════════════════════════════════════════════════
set "PYTHON="

:: Prefer venv Python if it exists (created by setup)
if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHON=.venv\Scripts\pythonw.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

:: Fall back to system Python if no venv
if not defined PYTHON (
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
    echo   If you saw "internal error: no runtimes are installed",
    echo   you have the Python launcher but no actual Python.
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

echo Starting Farm Bot...
"%PYTHON%" farm_cycle.py

if %errorLevel% neq 0 (
    echo.
    echo ============================================================
    echo   Farm cycle FAILED — check logs\FarmLog.txt
    echo ============================================================
    pause
)
