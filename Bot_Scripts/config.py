"""
config.py — Centralized configuration for the Farm Bot automation.
All paths, timings, and tunables live here. Change once, apply everywhere.
"""

from pathlib import Path
import ctypes

# Initialize DPI Awareness immediately so all coordinate queries (including monitor positions)
# return correct physical screen pixel coordinates.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # 2 = PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ──────────────────────────────────────────────
#  Paths
# ──────────────────────────────────────────────
# Base project directory (wherever this script lives)
PROJECT_DIR = Path(__file__).resolve().parent

# External application paths
GNBOTS_PATH = Path(r"C:\Program Files\GnBots\GnBots.exe")
LDPLAYER_PATH = Path(r"C:\LDPlayer\LDPlayer9\dnplayer.exe")

# Project subdirectories
TEMPLATE_DIR = PROJECT_DIR / "templates"
SCREENSHOT_DIR = PROJECT_DIR / "screenshots"
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "FarmLog.txt"

# ──────────────────────────────────────────────
#  GnBots Window
# ──────────────────────────────────────────────
GNBOTS_TITLE = "Goodnight Bots"

# ──────────────────────────────────────────────
#  Process Kill List
# ──────────────────────────────────────────────
# Kill BOTH GnBots and LDPlayer at the start of every cycle.
# Why: At the end of the 2-hour free trial window, GnBots spawns
# a cascade of pop-ups that eventually closes the emulator anyway.
# By killing everything upfront, we bypass having to dismiss those
# pop-ups entirely. GnBots re-launches LDPlayer when you click Start,
# so we don't need to manage the emulator separately.
KILL_TARGETS = [
    "GnBots.exe",
]

# LDPlayer processes — killed at the START of every cycle
# so GnBots starts the emulator fresh (no pop-up cascade to fight).
LDPLAYER_TARGETS = [
    "dnplayer.exe",
    "Ld9BoxHeadless.exe",
    "Ld9BoxSVC.exe",
]

# Must be True — GnBots free trial ends with pop-up cascade that
# closes the emulator. Killing LDPlayer at cycle start avoids this.
# GnBots automatically re-launches LDPlayer when Start is clicked.
KILL_EMULATOR_TOO = True

# ──────────────────────────────────────────────
#  Template Filenames
# ──────────────────────────────────────────────
TEMPLATE_START = "start_btn.png"
TEMPLATE_FIRST = "first_btn.png"
TEMPLATE_CONTINUE = "continue_btn.png"
TEMPLATE_STOP = "stop_btn.png"           # Visible when bot is running (diagnostic use)
TEMPLATE_COMPLETED = "completed.png"     # Visible when bot has finished its run (diagnostic use)

# ──────────────────────────────────────────────
#  Second Monitor Position
# ──────────────────────────────────────────────
# Where to move the GnBots window. Non-fatal if it fails.
# Set to 0,0 to leave it on the primary monitor, or set to your
# second monitor's top-left corner (e.g. 1920, 0 for a 1080p
# secondary on the right). Template matching works regardless of
# where the window is — this is purely cosmetic.
# If you rearrange monitors often, just leave it at 0,0.
import win32api
import win32con

def get_opposite_monitor_coords():
    """Detect and return the top-left coordinates of the opposite (secondary) monitor.
    
    If VDD_PREFER is True, prefer virtual displays over physical ones.
    Defaults to (0, 0) if only one monitor is present.
    """
    try:
        monitors = win32api.EnumDisplayMonitors()
        if len(monitors) > 1:
            virtual_coords = None
            physical_coords = None
            
            for hMonitor, _, rect in monitors:
                info = win32api.GetMonitorInfo(hMonitor)
                is_primary = info.get("Flags", 0) & win32con.MONITORINFOF_PRIMARY
                if not is_primary:
                    # Check if this might be a virtual display
                    # Virtual displays from IddSampleDriver/VDD typically report
                    # "\\Device\\0000XXXX" style device names or "IddSampleDriver" in the string
                    device_name = info.get("Device", "")
                    is_virtual = any(keyword in device_name.lower() for keyword in 
                                     ["idd", "virtual", "rooted", "mirage"])
                    
                    if is_virtual:
                        virtual_coords = (rect[0], rect[1])
                    else:
                        physical_coords = (rect[0], rect[1])
            
            # Prefer virtual display if VDD_PREFER is True and one was found
            if VDD_PREFER and virtual_coords is not None:
                return virtual_coords
            elif physical_coords is not None:
                return physical_coords
            elif virtual_coords is not None:
                return virtual_coords
    except Exception:
        pass
    return 0, 0

MONITOR2_X, MONITOR2_Y = get_opposite_monitor_coords()

# ──────────────────────────────────────────────
#  Timing (seconds)
# ──────────────────────────────────────────────
KILL_WAIT = 2            # Wait after killing processes
GNBOTS_LAUNCH_WAIT = 10  # Wait for GnBots to fully load
CLICK_DELAY = 0.5          # Delay before clicking a found template
DIALOG_WAIT = 5          # Wait for dialog to appear after Start
LDPLAYER_BOOT_WAIT = 45  # Wait for LDPlayer emulator to boot after clicking Start
LDPLAYER_INSTANCE = 0     # LDPlayer instance number (0 = default)

# ──────────────────────────────────────────────
#  Template Matching
# ──────────────────────────────────────────────
TEMPLATE_MATCH_THRESHOLD = 0.75   # Minimum confidence (0-1)
TEMPLATE_FALLBACK_THRESHOLD = 0.60  # Second-chance lower threshold
TEMPLATE_MULTI_SCALE = True       # Try matching at multiple scales
TEMPLATE_SCALES = [0.75, 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3]  # Scale factors

# ──────────────────────────────────────────────
#  Retry Settings
# ──────────────────────────────────────────────
MAX_RETRIES = 5          # How many times to retry finding/clicking
RETRY_DELAY = 3          # Seconds between retries

# ──────────────────────────────────────────────
#  Screenshot Differencing
# ──────────────────────────────────────────────
# Before every click, we capture "before" and "after" screenshots.
# If the difference is below this threshold, the click likely missed.
DIFF_THRESHOLD = 5.0     # Mean pixel difference (0-255) to count as "changed"
DIFF_SAVE_ALL = True     # Always save before/after pairs (not just failures)
DIFF_DIR = SCREENSHOT_DIR / "diffs"

# ──────────────────────────────────────────────
#  Click Verification
# ──────────────────────────────────────────────
# After clicking, the bot can verify the click landed by comparing
# before/after screenshots. If the screen didn't change, it retries.
#
# PROBLEM: GnBots' UI doesn't always change fast enough after a click.
# Clicking Start launches LDPlayer (the GnBots window itself barely changes).
# Clicking First transitions to farming mode (the button changes, but slowly).
# Screenshot verification sees "no change" and thinks the click failed,
# then kills everything as error handling — even though the click actually
# worked fine.
#
# SOLUTION: Set VERIFY_CLICK=False to trust clicks without screenshot
# verification. We know pyautogui works as admin. Set to True only if
# you want the extra safety net (and are willing to deal with false negatives).
VERIFY_CLICK = False

# ──────────────────────────────────────────────
#  Monitoring (not used in the current cycle)
# ──────────────────────────────────────────────
# The farm cycle exits after clicking First — GnBots farms on its own.
# Task Scheduler triggers the next cycle. No monitoring needed.
# These settings are kept for potential future use or manual scripting.
HEALTH_CHECK_INTERVAL = 300   # Check every 5 minutes
HEALTH_CHECK_METHOD = "process"  # "process" or "template"
HEALTH_CHECK_ON_FAIL = "kill_and_report"
DETECT_COMPLETION = False
COMPLETION_CHECK_INTERVAL = 120
COMPLETION_TEMPLATE = TEMPLATE_COMPLETED
COMPLETION_WINDOW_TITLE = None
RUN_DURATION = 7200      # 120 minutes — GnBots free trial max run time

# ──────────────────────────────────────────────
#  Self-Elevation
# ──────────────────────────────────────────────
AUTO_ELEVATE = True       # If not running as admin, auto-relaunch with UAC prompt

# ──────────────────────────────────────────────
#  Headless Mode
# ──────────────────────────────────────────────
# When True, the bot won't move your mouse or steal window focus.
# Uses PostMessage for clicks (sends directly to the window) and
# PrintWindow for screenshots (captures even if window is behind others).
# This lets you use your PC while the bot runs.
# Requires admin (AUTO_ELEVATE must be True) for UIPI — PostMessage clicks
# to elevated windows (like GnBots) are silently blocked otherwise.
#
# NOTE: PostMessage clicks may not work on all apps — some UI frameworks
# (Electron, Chromium, custom controls) ignore WM_LBUTTONDOWN/UP messages.
# If clicks aren't registering (diff=0.0 in logs), set this to False.
# The mouse will move for ~5 seconds per cycle, but clicks will work.
HEADLESS = False

# ──────────────────────────────────────────────
#  Ghost Mode (Window Transparency)
# ──────────────────────────────────────────────
# When enabled, makes GnBots and LDPlayer windows fully transparent
# (invisible) after the initial setup clicks are done. The windows
# still exist and render normally — they're just not visible.
#
# REQUIRES: HEADLESS must be True for Ghost Mode to work properly,
# since only PrintWindow can capture an invisible window, and only
# PostMessage can click an invisible window.
#
# If HEADLESS is False, Ghost Mode is ignored with a warning.
#
# Transparency levels:
#   0   = fully invisible (use this for "stealth" mode)
#   1   = nearly invisible (just a faint outline, for debugging)
#   255 = fully opaque (disables Ghost Mode)
#
# NOTE: PrintWindow with PW_RENDERFULLCONTENT captures the FULL
# window content regardless of transparency. This has been verified
# to work with GnBots' WinForms UI. If your capture_test.py shows
# blank screenshots while Ghost Mode is on, set GHOST_ALPHA=1 instead
# of 0 to keep a barely-visible window for debugging.
GHOST_MODE = False
GHOST_ALPHA = 0       # 0=invisible, 1=trace, 255=off. Ignored if GHOST_MODE=False

# When to apply Ghost Mode:
#   "after_start"  = Make invisible right after clicking Start (before popup)
#   "after_enter"  = Make invisible after pressing Enter (final step)
#   "after_move"   = Make invisible after moving to secondary monitor
GHOST_WHEN = "after_enter"

# ──────────────────────────────────────────────
#  Virtual Display Detection
# ──────────────────────────────────────────────
# If you've installed a Virtual Display Driver (VDD) like
# https://github.com/VirtualDrivers/Virtual-Display-Driver, the bot
# can auto-detect the virtual monitor and move windows there instead
# of a physical secondary monitor.
#
# Set VDD_PREFER=True to prefer a virtual display over a physical one.
# Set VDD_PREFER=False to use physical monitors as before.
#
# If no virtual display is found, falls back to get_opposite_monitor_coords().
VDD_PREFER = True

# ──────────────────────────────────────────────
#  Log Rotation
# ──────────────────────────────────────────────
LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per log file
LOG_BACKUP_COUNT = 3               # Keep 3 rotated copies

# ──────────────────────────────────────────────
#  Notifications
# ──────────────────────────────────────────────
NOTIFICATIONS = {
    # Webhook (Discord/Slack/custom) — ideal for when you're away from the PC
    "webhook_url": None,        # e.g. "https://discord.com/api/webhooks/..."
    "webhook_enabled": False,

    # Desktop toast (only useful if you're at the PC)
    "desktop_enabled": False,
    "on_cycle_start": True,
    "on_cycle_complete": True,
    "on_error": True,
    "on_health_fail": True,     # Not triggered in current cycle (no monitoring)
    "on_completion_detected": True,  # Not triggered in current cycle (no monitoring)

    # Sound fallback
    "sound_file": None,         # Path to .wav, or None for default beep
}

# ──────────────────────────────────────────────
#  Coordinate Fallback
# ──────────────────────────────────────────────
# If template matching fails, fall back to clicking known screen coordinates.
# Set to None to disable. These are ABSOLUTE screen coordinates.
# Use click_test.py --coords to find the right values for your setup.
# Example: if GnBots window is at (1920, -831) and the Start button is
# at local (475, 500), the screen coordinate would be (2395, -331).
COORD_FALLBACK_ENABLED = True

COORD_FALLBACKS = {
    "start_btn": None,       # e.g. (2395, -331) — set after testing with click_test.py
    "first_btn": None,       # e.g. (2395, -280) — set after testing with click_test.py
    "continue_btn": None,    # e.g. (2395, -200)
}

# ──────────────────────────────────────────────
#  ADB Settings (for direct game interaction — future use)
# ──────────────────────────────────────────────
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037
