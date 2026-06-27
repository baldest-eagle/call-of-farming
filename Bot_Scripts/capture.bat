@echo off
:: capture.bat — Double-click to capture template images.
:: Opens a GUI tool that lets you drag-select button regions
:: from a GnBots screenshot and saves them as template PNGs.

setlocal
cd /d "%~dp0"

:: Find Python
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

"%PYTHON%" capture_templates.py

if %errorLevel% neq 0 (
    pause
)
