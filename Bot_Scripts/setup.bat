@echo off
:: setup.bat — Install dependencies and create project structure
:: Run this once after copying the project to your PC.
:: RIGHT-CLICK → Run as Administrator for best results.

echo ============================================
echo   Farm Bot Project Setup
echo ============================================
echo.

:: Create directories
echo Creating project directories...
if not exist "templates" mkdir templates
if not exist "screenshots" mkdir screenshots
if not exist "screenshots\diffs" mkdir screenshots\diffs
if not exist "logs" mkdir logs

:: Install Python dependencies
echo.
echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ============================================
echo   Setup complete!
echo.
echo   QUICK START GUIDE:
echo.
echo   1. Place template images in templates\
echo      - start_btn.png  (the Start button)
echo      - first_btn.png  (the First/OK button in dialog)
echo      - continue_btn.png (optional, if a Continue dialog appears)
echo.
echo   2. Review config.py:
echo      - Check GNBOTS_PATH points to your GnBots.exe
echo      - Check LDPLAYER_PATH points to your dnplayer.exe
echo      - Set MONITOR2_X and MONITOR2_Y for your monitor layout
echo      - Set COORD_FALLBACKS with known button positions
echo.
echo   3. Test your setup (IN ORDER):
echo      a) python capture_test.py
echo         - Verifies window capture is working
echo      b) python template_diagnostic.py
echo         - Checks if your template images match
echo      c) python click_test.py
echo         - Tests clicking on the GnBots window
echo      d) python click_test.py --all-methods start_btn
echo         - Finds which click method actually works
echo.
echo   4. Set coordinate fallbacks in config.py:
echo      - Use click_test.py --coords X Y to test positions
echo      - Enter working coords in COORD_FALLBACKS dict
echo.
echo   5. Run a full cycle:
echo      python farm_cycle.py
echo.
echo   6. Set up Task Scheduler (runs every 3 hours):
echo      Program:    pythonw.exe
echo      Arguments:  "C:\Your\Path\BotProject\farm_cycle.py"
echo      Start in:   "C:\Your\Path\BotProject"
echo      Run with highest privileges: YES
echo ============================================
pause
