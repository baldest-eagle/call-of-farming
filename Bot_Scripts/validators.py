"""
validators.py — Pre-flight config validation.
Runs before a farm cycle starts to catch problems early.
"""

import logging
from pathlib import Path

from config import (
    GNBOTS_PATH,
    LDPLAYER_PATH,
    SCREENSHOT_DIR,
    LOG_DIR,
    LOG_FILE,
    KILL_TARGETS,
    LDPLAYER_TARGETS,
    KILL_EMULATOR_TOO,
    NOTIFICATIONS,
    RUN_DURATION,
)
from process_manager import resolve_path

logger = logging.getLogger("FarmBot.Validators")


def validate_all() -> list:
    """
    Run all pre-flight checks. Returns a list of issues found.
    Empty list = all clear.
    """
    issues = []

    # ── Application paths ──
    # Check that the .lnk (or .exe) file exists
    if not GNBOTS_PATH.exists():
        issues.append(f"GnBots not found at: {GNBOTS_PATH}")
        logger.error(f"VALIDATION: GnBots not found at: {GNBOTS_PATH}")
    else:
        # Also check that the resolved target exists (e.g. .lnk -> .exe)
        resolved_gnbots = resolve_path(GNBOTS_PATH)
        if not resolved_gnbots.exists():
            issues.append(f"GnBots shortcut target does not exist: {GNBOTS_PATH} -> {resolved_gnbots}")
            logger.error(f"VALIDATION: GnBots shortcut target missing: {resolved_gnbots}")
        else:
            logger.debug(f"VALIDATION: GnBots found at: {GNBOTS_PATH} -> {resolved_gnbots}")

    # LDPlayer is checked but only critical if KILL_EMULATOR_TOO is True
    # (since we need to restart it if we killed it)
    if not LDPLAYER_PATH.exists():
        if KILL_EMULATOR_TOO:
            issues.append(f"LDPlayer not found at: {LDPLAYER_PATH} (required because KILL_EMULATOR_TOO=True)")
            logger.error(f"VALIDATION: LDPlayer not found at: {LDPLAYER_PATH}")
        else:
            issues.append(f"LDPlayer not found at: {LDPLAYER_PATH} (needed for auto-launch if not running)")
            logger.warning(f"VALIDATION: LDPlayer not found at: {LDPLAYER_PATH} — make sure it's running manually")
    else:
        # Also check that the resolved target exists
        resolved_ldplayer = resolve_path(LDPLAYER_PATH)
        if not resolved_ldplayer.exists():
            if KILL_EMULATOR_TOO:
                issues.append(f"LDPlayer shortcut target does not exist: {LDPLAYER_PATH} -> {resolved_ldplayer}")
                logger.error(f"VALIDATION: LDPlayer shortcut target missing: {resolved_ldplayer}")
            else:
                logger.warning(f"VALIDATION: LDPlayer shortcut target missing: {resolved_ldplayer} — make sure it's running manually")
        else:
            logger.debug(f"VALIDATION: LDPlayer found at: {LDPLAYER_PATH} -> {resolved_ldplayer}")



    # ── Directory writability ──
    for dir_path, label in [
        (SCREENSHOT_DIR, "screenshots"),
        (LOG_DIR, "logs"),
    ]:
        dp = Path(dir_path)
        try:
            dp.mkdir(parents=True, exist_ok=True)
            # Test write
            test_file = dp / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            logger.debug(f"VALIDATION: {label} dir writable: {dp}")
        except Exception as e:
            issues.append(f"Cannot write to {label} directory: {dp} ({e})")
            logger.error(f"VALIDATION: {label} dir not writable: {dp} — {e}")

    # ── Log file ──
    try:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"VALIDATION: Log file path OK: {log_path}")
    except Exception as e:
        issues.append(f"Cannot create log file: {LOG_FILE} ({e})")

    # ── Config sanity ──
    if RUN_DURATION <= 0:
        issues.append(f"RUN_DURATION must be positive, got: {RUN_DURATION}")

    if NOTIFICATIONS.get("webhook_enabled") and not NOTIFICATIONS.get("webhook_url"):
        issues.append("Webhook enabled but no URL configured")

    # ── Summary ──
    if issues:
        logger.warning(f"VALIDATION: {len(issues)} issue(s) found:")
        for i, issue in enumerate(issues, 1):
            logger.warning(f"  {i}. {issue}")
    else:
        logger.info("VALIDATION: All pre-flight checks passed.")

    return issues
