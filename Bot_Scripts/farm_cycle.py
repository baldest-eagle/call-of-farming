"""
farm_cycle.py — Main automation orchestrator.
Triggered by Task Scheduler every ~3 hours.

Run:  python farm_cycle.py
Or:   pythonw farm_cycle.py  (no console window, for Task Scheduler)

Workflow (6 steps):
  1. Ensure clean slate — kill GnBots + LDPlayer if still running
     (bypasses trial-end pop-up cascade entirely)
  2. Launch GnBots
  3. Find the GnBots window
  4. Move to second monitor
  5. Click Start (GnBots auto-launches LDPlayer)
  6. Click First (GnBots starts farming)

That's it — exit. GnBots handles the 2-hour farming run on its own.
Task Scheduler triggers the next cycle, which kills everything and starts fresh.

Features:
  - Self-elevation: auto-relaunches as admin if needed (required for UIPI)
  - Log rotation: keeps 3x5MB rotating log files
  - Config validation: pre-flight checks before starting
  - Screenshot differencing: before/after every click (via window_bot)
  - Webhook notifications: Discord/Slack alerts while you're away
"""

import sys
import time
import logging
import logging.handlers
import traceback
from pathlib import Path
from datetime import datetime
import ctypes

# ──────────────────────────────────────────────────────────────
#  DPI Awareness Initialization
# ──────────────────────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # 2 = PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import win32gui
import win32con
import win32process
import win32ui
import psutil

# Ensure project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    GNBOTS_TITLE,
    TEMPLATE_DIR,
    TEMPLATE_START,
    TEMPLATE_FIRST,
    TEMPLATE_CONTINUE,
    SCREENSHOT_DIR,
    LOG_FILE,
    MONITOR2_X,
    MONITOR2_Y,
    MAX_RETRIES,
    RETRY_DELAY,
    CLICK_DELAY,
    DIALOG_WAIT,
    LDPLAYER_BOOT_WAIT,
    NOTIFICATIONS,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    HEADLESS,
    VERIFY_CLICK,
)
from process_manager import (
    kill_all_targets,
    launch_gnbots,
    is_admin,
    relaunch_as_admin,
)
from window_bot import WindowBot
from notifier import send as notify
from validators import validate_all


# ──────────────────────────────────────────────────────────────
#  Window Movement Helper
# ──────────────────────────────────────────────────────────────

def move_all_project_windows(x: int, y: int) -> None:
    """Find and move all project windows (GnBots, LDPlayer, and the game) to target coordinates.
    
    Only moves main application windows (avoids tooltips, shadows, or background net broadcast windows
    which can cause parent WinForms windows to reset or snap back to (0, 0)).
    """
    logger = logging.getLogger("FarmBot")
    target_processes = ["gnbots.exe", "dnplayer.exe", "callofdragons.exe"]
    target_titles = ["goodnight bots", "ldplayer", "call of dragons"]

    def move_window_to_coords(hwnd, tx, ty):
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            win32gui.MoveWindow(hwnd, tx, ty, w, h, True)
            logger.info(f"  Moved window '{win32gui.GetWindowText(hwnd)}' (HWND: {hwnd}) to ({tx}, {ty})")
            time.sleep(0.2)
            return True
        except Exception as e:
            logger.warning(f"  Could not move window '{win32gui.GetWindowText(hwnd)}' (HWND: {hwnd}): {e}")
            return False

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            classname = win32gui.GetClassName(hwnd)
            
            should_move = False
            pname = ""
            
            # Fast path check: Class names that map directly to our target windows
            if classname == "LDPlayerMainFrame":
                should_move = True
            elif classname == "UnityWndClass":
                should_move = True
            elif "WindowsForms10.Window" in classname and title:
                should_move = True
            
            # Slow path check: If title looks related, confirm with process name
            if not should_move and title:
                title_lower = title.lower()
                if any(t in title_lower for t in target_titles):
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        proc = psutil.Process(pid)
                        pname = proc.name().lower()
                        if pname in target_processes:
                            if not any(cls in classname.lower() for cls in ["tooltip", "shadow", "broadcast"]):
                                should_move = True
                    except Exception:
                        pass

            if should_move:
                rect = win32gui.GetWindowRect(hwnd)
                # Check if it's already near target x, y
                if abs(rect[0] - x) > 10 or abs(rect[1] - y) > 10:
                    # Retrieve pname if not already fetched, for logging
                    if not pname:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            proc = psutil.Process(pid)
                            pname = proc.name().lower()
                        except Exception:
                            pname = "unknown"
                    logger.info(f"  Found matching window to move: '{title}' (Class: {classname}, Proc: {pname})")
                    move_window_to_coords(hwnd, x, y)

    try:
        win32gui.EnumWindows(enum_callback, None)
    except Exception as e:
        logger.error(f"Error enumerating windows: {e}")


# ──────────────────────────────────────────────────────────────
#  Logging Setup (with rotation)
# ──────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """Configure dual-output logging with rotation: file (DEBUG) + console (INFO)."""
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("FarmBot")
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on re-import
    if logger.handlers:
        return logger

    # Rotating file handler — 5MB per file, keep 3 backups
    fh = logging.handlers.RotatingFileHandler(
        log_path,
        mode='a',
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))

    # Console handler — info and above
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S',
    ))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ──────────────────────────────────────────────────────────────
#  Self-Elevation
# ──────────────────────────────────────────────────────────────

def ensure_admin(logger: logging.Logger) -> None:
    """Always ensure the script is running with admin privileges.

    If not already elevated, re-launches itself via UAC (ShellExecuteW runas)
    and exits the non-elevated process. This is required so that pyautogui
    can send input to elevated windows like GnBots (UIPI restriction).
    """
    if is_admin():
        logger.info("Running with admin privileges.")
        return

    logger.info("Not running as admin — requesting elevation via UAC...")
    relaunch_as_admin()
    # The original (non-elevated) process exits here.
    # The new elevated process restarts from scratch.
    sys.exit(0)


# ──────────────────────────────────────────────────────────────
#  Main Cycle
# ──────────────────────────────────────────────────────────────

def run_cycle() -> bool:
    """
    Execute one complete farm cycle.
    Returns True on success, False on failure.
    """
    logger = setup_logging()
    cycle_start = time.time()

    # ── Self-elevation ──
    ensure_admin(logger)

    # ── Pre-flight validation ──
    issues = validate_all()
    critical_issues = [i for i in issues if "Required" in i or "GnBots not found" in i]
    if critical_issues:
        logger.critical("Pre-flight validation failed — cannot proceed:")
        for issue in critical_issues:
            logger.critical(f"  - {issue}")
        notify("error", f"Validation failed: {critical_issues[0]}")
        return False

    # ── Banner ──
    logger.info("=" * 60)
    logger.info("  FARM CYCLE STARTING")
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Admin: {is_admin()}")
    logger.info(f"  Headless: {HEADLESS} ({'no mouse movement' if HEADLESS else 'mouse will move'})")
    logger.info(f"  Verify clicks: {VERIFY_CLICK}")
    logger.info("=" * 60)

    notify("cycle_start", "Farm cycle starting")

    try:
        # ── STEP 1: Ensure clean slate ────────────────────────────
        # Kill any leftover GnBots/LDPlayer from the previous cycle.
        # This bypasses the trial-end pop-up cascade entirely — no need
        # to dismiss any dialogs. GnBots will re-launch LDPlayer fresh
        # when we click Start.
        logger.info("[STEP 1/6] Ensuring GnBots + LDPlayer are stopped...")
        kill_all_targets()

        # ── STEP 2: Launch GnBots ───────────────────────────────
        logger.info("[STEP 2/6] Launching GnBots...")
        launched = False
        for attempt in range(1, MAX_RETRIES + 1):
            if launch_gnbots():
                launched = True
                break
            logger.warning(f"  Launch attempt {attempt}/{MAX_RETRIES} failed.")
            if attempt < MAX_RETRIES:
                kill_all_targets()
                time.sleep(RETRY_DELAY)

        if not launched:
            raise RuntimeError("Failed to launch GnBots after all retries.")

        # ── STEP 3: Find the GnBots window ──────────────────────
        logger.info("[STEP 3/6] Finding GnBots window...")
        bot = WindowBot(
            window_title=GNBOTS_TITLE,
            template_dir=TEMPLATE_DIR,
        )
        if not bot.find_window(timeout=30):
            raise RuntimeError(f"Could not find window: '{GNBOTS_TITLE}'")

        time.sleep(1)

        # Capture initial state
        screenshot_dir = Path(SCREENSHOT_DIR)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bot.save_capture(f"{ts}_01_main_screen.png", str(screenshot_dir))

        # ── STEP 4: Click Start ─────────────────────────────────
        # Click on the primary monitor where SendInput works reliably.
        logger.info("[STEP 4/6] Clicking Start button (also launches LDPlayer)...")

        # First, try to dismiss any "Continue" dialog if present
        continue_template_path = Path(TEMPLATE_DIR) / TEMPLATE_CONTINUE
        if continue_template_path.exists():
            continue_clicked = bot.find_and_click(
                TEMPLATE_CONTINUE,
                click_delay=CLICK_DELAY,
                retries=2,
                retry_delay=2,
                verify_click=False,
            )
            if continue_clicked:
                logger.info("Dismissed 'Continue' dialog.")
                time.sleep(DIALOG_WAIT)
            else:
                logger.info("No 'Continue' dialog found, proceeding.")
        else:
            logger.info("Optional 'Continue' template not found on disk, skipping check.")

        if not bot.find_and_click(
            TEMPLATE_START,
            click_delay=CLICK_DELAY,
            retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY,
            verify_click=VERIFY_CLICK,
        ):
            bot.save_capture(f"{ts}_ERROR_start_not_found.png", str(screenshot_dir))
            report = bot.get_template_confidence_report(TEMPLATE_START)
            logger.error(f"Start button diagnostic: {report}")
            raise RuntimeError("Failed to find and click the Start button!")

        bot.save_capture(f"{ts}_02_after_start.png", str(screenshot_dir))

        # ── STEP 5 & 6: Wait 1s then press Enter ────────────────
        # The popup "Start with first or continue" opens automatically and
        # defaults to "First" highlighted. Since GnBots is already on the
        # secondary monitor, the popup inherits focus naturally.
        # No steering, no detection — just wait and press Enter.
        logger.info("[STEP 5/6] Waiting 3s for popup to open...")
        time.sleep(3.0)

        logger.info("[STEP 6/6] Pressing Enter to confirm 'First'...")
        VK_RETURN = 0x0D
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)       # key down
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0x0002, 0)  # key up
        logger.info("  Enter sent. 'First' confirmed.")

        # Move everything to secondary monitor AFTER Enter — focus is no longer needed
        logger.info("[STEP 6b] Moving all windows to secondary monitor...")
        move_all_project_windows(MONITOR2_X, MONITOR2_Y)

        logger.info("GnBots is now farming on its own.")
        bot.save_capture(f"{ts}_03_running.png", str(screenshot_dir))

        # ── Done ──
        elapsed = int(time.time() - cycle_start)
        logger.info("=" * 60)
        logger.info("  FARM CYCLE COMPLETE")
        logger.info(f"  Setup time: {elapsed}s")
        logger.info("  GnBots is farming. Next cycle will clean up and restart.")
        logger.info("=" * 60)

        notify("cycle_complete", f"Setup done in {elapsed}s — GnBots is farming")
        return True

    except Exception as e:
        logger.critical(f"CYCLE FAILED: {e}")
        logger.critical(traceback.format_exc())
        notify("error", str(e))
        try:
            kill_all_targets()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    success = run_cycle()
    sys.exit(0 if success else 1)

