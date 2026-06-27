@echo off
:: start.bat — Double-click to run one farm cycle.
:: Uses the venv Python if available, otherwise system Python.

setlocal
cd /d "%~dp0"

:: Find Python
set "PYTHON=python"
if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHON=.venv\Scripts\pythonw.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

:: Run a single farm cycle
echo Starting Farm Bot...
"%PYTHON%" farm_cycle.py

if %errorLevel% neq 0 (
    echo.
    echo ============================================
    echo   Farm cycle FAILED — check logs\FarmLog.txt
    echo ============================================
    pause
)
