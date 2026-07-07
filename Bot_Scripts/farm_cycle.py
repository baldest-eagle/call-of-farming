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
  4. Click Start
     - Send Tab then Enter keystrokes to start farming.
     - Optionally run in HEADLESS mode using PostMessage keystrokes.
  5. Sleep for configured RUN_DURATION (default 2 hours).
  6. Wake up, kill LDPlayer (optional) and GnBots, and loop back to step 1.

Features:
  - Self-elevation: auto-relaunches as admin if needed (required for UIPI)
  - Log rotation: keeps 3x5MB rotating log files
  - Config validation: pre-flight checks before starting
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

# Note: DPI awareness is initialized in config.py at import time.
# No need to call SetProcessDpiAwareness again here.

import win32gui
import win32con
import win32process
import win32ui
import psutil
import json

# Ensure project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    GNBOTS_PATH,
    GNBOTS_TITLE,

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
    GHOST_MODE,
    GHOST_ALPHA,
    GHOST_WHEN,
    DETECT_COMPLETION,
    COMPLETION_CHECK_INTERVAL,
    RUN_DURATION,
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


def ghost_all_project_windows(alpha: int = 0) -> None:
    """Make all project windows (GnBots, LDPlayer, game) transparent.
    
    Uses SetLayeredWindowAttributes via Win32 API. The windows still
    exist and render normally — they're just not visible on screen.
    PrintWindow captures still work at alpha=0.
    """
    logger = logging.getLogger("FarmBot")
    target_processes = ["gnbots.exe", "dnplayer.exe", "callofdragons.exe"]
    import ctypes

    def ghost_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                pname = proc.name().lower()
                if pname in target_processes:
                    # Add WS_EX_LAYERED and set alpha
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    new_style = style | 0x80000  # WS_EX_LAYERED
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, new_style)
                    result = ctypes.windll.user32.SetLayeredWindowAttributes(
                        hwnd, 0, alpha, 0x02
                    )
                    title = win32gui.GetWindowText(hwnd)
                    if result:
                        logger.info(f"Ghost Mode: '{title}' (Proc: {pname}) set to alpha={alpha}")
                    else:
                        logger.warning(f"Ghost Mode: Failed for '{title}' (Proc: {pname})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    try:
        win32gui.EnumWindows(ghost_callback, None)
    except Exception as e:
        logger.error(f"Error applying Ghost Mode: {e}")


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
    logger.info(f"  Ghost Mode: {GHOST_MODE} (alpha={GHOST_ALPHA}, when={GHOST_WHEN})")
    logger.info(f"  Target monitor: ({MONITOR2_X}, {MONITOR2_Y})")
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

        # Ghost Mode check: warn if enabled without headless
        if GHOST_MODE and not HEADLESS:
            logger.warning(
                "Ghost Mode requires HEADLESS=True for PostMessage clicks and "
                "PrintWindow captures. Disabling Ghost Mode."
            )
        # First, ensure GnBots is in the foreground
        if not HEADLESS:
            if not bot.bring_to_front():
                logger.warning("Failed to force GnBots to foreground! Keys may not register.")
            time.sleep(1.0)
        else:
            logger.info("Running Headless — sending PostMessage keystrokes directly to window.")
        
        VK_TAB = 0x09
        VK_RETURN = 0x0D

        # Send Tab
        bot.send_key(VK_TAB)
        logger.info("  Tab sent.")
        
        time.sleep(1.0)
        
        # Send Enter
        bot.send_key(VK_RETURN)
        logger.info("  Enter sent. Start triggered.")

        bot.save_capture(f"{ts}_02_after_start.png", str(screenshot_dir))

        # Ghost Mode: apply after Start click (before popup)
        if GHOST_MODE and HEADLESS and GHOST_WHEN == "after_start":
            logger.info("[GHOST] Making GnBots invisible (after_start)...")
            bot.make_transparent(GHOST_ALPHA)

        # ── STEP 5: Wait for popup then press Enter ────────────
        # The popup "Start with first or continue" opens automatically and
        # defaults to "First" highlighted. Since GnBots is already on the
        # secondary monitor, the popup inherits focus naturally.
        # No steering, no detection — just wait and press Enter.
        logger.info("[STEP 5/6] Waiting 3s for popup to open...")
        time.sleep(3.0)

        logger.info("[STEP 5/6] Pressing Enter to confirm 'First'...")
        VK_RETURN = 0x0D
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0, 0)       # key down
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(VK_RETURN, 0, 0x0002, 0)  # key up
        logger.info("  Enter sent. 'First' confirmed.")

        # Ghost Mode: apply after Enter (most common — all clicks done)
        if GHOST_MODE and HEADLESS and GHOST_WHEN == "after_enter":
            logger.info("[GHOST] Making all project windows invisible (after_enter)...")
            ghost_all_project_windows(GHOST_ALPHA)

        # ── STEP 6: Move everything to secondary monitor ─────────
        # Move AFTER Enter — focus is no longer needed
        logger.info("[STEP 6/6] Moving all windows to secondary monitor...")
        move_all_project_windows(MONITOR2_X, MONITOR2_Y)

        # Ghost Mode: apply after moving (if configured)
        if GHOST_MODE and HEADLESS and GHOST_WHEN == "after_move":
            logger.info("[GHOST] Making all project windows invisible (after_move)...")
            ghost_all_project_windows(GHOST_ALPHA)

        logger.info("GnBots is now farming on its own.")
        bot.save_capture(f"{ts}_03_running.png", str(screenshot_dir))

        # ── Done ──
        elapsed = int(time.time() - cycle_start)
        logger.info("=" * 60)
        logger.info("  FARM CYCLE COMPLETE")
        logger.info(f"  Setup time: {elapsed}s")
        logger.info("=" * 60)

        notify("cycle_complete", f"Setup done in {elapsed}s — GnBots is farming")

        # ── Monitoring ──
        monitor_run(logger, cycle_start)
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


def monitor_run(logger, cycle_start: float) -> None:
    """
    Monitor the GnBots log file to detect when one full round of all active accounts
    is complete. Once completed, kills GnBots + emulator and exits.
    """
    if not DETECT_COMPLETION:
        logger.info("Completion detection is disabled. Leaving GnBots to run.")
        return

    logger.info("Completion detection is enabled. Monitoring GnBots log for round completion...")
    
    # 1. Get active accounts from settings.json
    active_accounts = []
    settings_path = Path(GNBOTS_PATH).parent / "profiles" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
            for p in profiles:
                if p.get("Active", False) and p.get("Name") and not p.get("Name").startswith("NewAccount"):
                    active_accounts.append(p.get("Name"))
        except Exception as e:
            logger.error(f"Error loading active accounts: {e}")
            
    if not active_accounts:
        logger.warning("No active accounts found in settings.json. Completion detection disabled.")
        return
        
    logger.info(f"Active accounts to monitor: {active_accounts}")
    completed_accounts = set()
    
    # 2. Find the active log file
    log_dir = Path(GNBOTS_PATH).parent / "logs"
    current_log = None
    
    # Try to find the log file created or modified recently
    for attempt in range(10):
        script_logs = list(log_dir.glob("script*.txt"))
        if script_logs:
            newest_log = max(script_logs, key=lambda p: p.stat().st_mtime)
            # If modified in the last 120 seconds, it's our active log
            if time.time() - newest_log.stat().st_mtime < 120:
                current_log = newest_log
                break
        time.sleep(2)
        
    if not current_log:
        logger.warning("Could not identify the active GnBots script log file. Exiting monitor.")
        return
        
    logger.info(f"Found active script log: {current_log.name}")
    last_position = 0
    
    while True:
        # Check timeout
        elapsed = time.time() - cycle_start
        if elapsed > RUN_DURATION:
            logger.warning(f"Run duration threshold exceeded ({RUN_DURATION}s). Terminating run...")
            kill_all_targets()
            notify("error", f"Farm run timed out after {RUN_DURATION}s.")
            break
            
        # Read new log lines
        if current_log.exists():
            try:
                with open(current_log, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_position)
                    lines = f.readlines()
                    last_position = f.tell()
                    
                for line in lines:
                    # Logs match "Account [name] Done" or similar patterns
                    if "Account Done" in line or ("Account " in line and " Done" in line):
                        for acc in active_accounts:
                            if f"Account {acc} Done" in line or f"Account {acc} finished" in line or (f"Account" in line and acc in line and "Done" in line):
                                if acc not in completed_accounts:
                                    completed_accounts.add(acc)
                                    logger.info(f"Detected completion for account: {acc} ({len(completed_accounts)}/{len(active_accounts)})")
            except Exception as e:
                logger.error(f"Error reading GnBots log: {e}")
                
        # Check if all active accounts completed
        if len(completed_accounts) >= len(active_accounts):
            logger.info("All active accounts completed one full round. Stopping GnBots and LDPlayer...")
            time.sleep(5)  # allow brief settle time
            kill_all_targets()
            notify("on_completion_detected", "All active accounts completed one full round. Farm cycle stopped.")
            break
            
        time.sleep(COMPLETION_CHECK_INTERVAL)


if __name__ == "__main__":
    success = run_cycle()
    sys.exit(0 if success else 1)

