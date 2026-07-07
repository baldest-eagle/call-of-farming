"""
user_config.example.py — Template for user_config.py.

Copy this file to user_config.py and fill in your paths:
    copy user_config.example.py user_config.py

Or just run: python setup_farm_bot.py
    (it generates user_config.py automatically and can install the apps)

user_config.py is .gitignored — your settings stay private.
"""

from pathlib import Path

# ── Application Paths ─────────────────────────────────────
GNBOTS_PATH = Path(r"C:\Path\To\GnBots.exe")        # TODO: Set your path
LDPLAYER_PATH = Path(r"C:\Path\To\dnplayer.exe")     # TODO: Set your path
LDMULTIPLAYER_PATH = Path(r"C:\Path\To\dnmultiplayer.exe")  # TODO: Set your path

# ── Notifications ─────────────────────────────────────────
NOTIFICATIONS = {
    "webhook_url": None,          # e.g. "https://discord.com/api/webhooks/..."
    "webhook_enabled": False,
    "desktop_enabled": False,
    "on_cycle_start": True,
    "on_cycle_complete": True,
    "on_error": True,
    "on_health_fail": True,
    "on_completion_detected": True,
    "sound_file": None,
}

# ── Optional overrides (uncomment to change) ──────────────
# MONITOR2_X = 1920
# MONITOR2_Y = 0
# HEADLESS = False
# GHOST_MODE = False
# GHOST_ALPHA = 0
# VDD_PREFER = True
# COORD_FALLBACK_ENABLED = True
# COORD_FALLBACKS = {
#     "start_btn": None,
#     "first_btn": None,
#     "continue_btn": None,
# }
