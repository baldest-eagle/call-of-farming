@echo off
:: test.bat — Double-click to run all diagnostic tests.
:: Runs capture_test, template_diagnostic, and click_test in sequence,
:: then prints a summary report.

setlocal
cd /d "%~dp0"

:: Find Python
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

echo ============================================
echo   Farm Bot — Diagnostic Tests
echo ============================================
echo.

"%PYTHON%" test_setup.py

echo.
pause
