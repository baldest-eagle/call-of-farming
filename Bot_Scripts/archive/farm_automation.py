"""
farm_automation.py — ORIGINAL v1 script (kept for reference only).
This was the initial monolithic version. The current codebase uses
farm_cycle.py + window_bot.py + process_manager.py + config.py instead.

DO NOT USE THIS FOR SCHEDULING — use farm_cycle.py instead.
"""

# ── ARCHIVED — For historical reference only ────────────────────
# This file combines process management, screen clicking, and ADB
# game automation into a single script. It was superseded by the
# modular architecture in farm_cycle.py.
#
# Known issues in this version:
# 1. Uses subprocess.Popen for GnBots — fails with elevation error
# 2. No retry logic on process launch
# 3. pyautogui.screenshot() captures full desktop, not just window
# 4. ADB GameBot class is defined but never fully utilized
# 5. No graceful error handling or diagnostic captures
# ────────────────────────────────────────────────────────────────
