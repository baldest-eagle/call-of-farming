@echo off
:: create_task.bat — Create the FarmCycle scheduled task.
:: Run this once to set up the 3-hour cycle.
:: RIGHT-CLICK → Run as Administrator for best results.
::
:: Paths are auto-detected relative to this script's location.

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%..\..\pythonw.exe"

:: Fallback: try to find pythonw.exe in PATH
where pythonw.exe >nul 2>&1
if %ERRORLEVEL%==0 (
    for /f "tokens=*" %%i in ('where pythonw.exe') do set "PYTHON_EXE=%%i"
)

set "FARM_CYCLE=%SCRIPT_DIR%farm_cycle.py"

echo Creating scheduled task...
echo   Python:  %PYTHON_EXE%
echo   Script:  %FARM_CYCLE%
echo.

schtasks /Delete /TN "FarmCycle" /F
schtasks /Create /TN "FarmCycle" /TR "%PYTHON_EXE% %FARM_CYCLE%" /SC DAILY /ST 17:21 /RI 180 /DU 24:00 /RL HIGHEST /F

echo.
if %ERRORLEVEL%==0 (
    echo Task created successfully.
) else (
    echo Task creation failed. Trying fallback with /DU 23:59...
    schtasks /Create /TN "FarmCycle" /TR "%PYTHON_EXE% %FARM_CYCLE%" /SC DAILY /ST 17:21 /RI 150 /DU 23:59 /RL HIGHEST /F
)
pause
