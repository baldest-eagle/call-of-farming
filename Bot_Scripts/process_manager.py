"""
process_manager.py — Handles killing, launching, verifying processes,
and self-elevation for admin privileges.
"""

import time
import ctypes
import subprocess
import logging
from pathlib import Path

import psutil

from config import (
    GNBOTS_PATH,
    LDPLAYER_PATH,
    KILL_TARGETS,
    LDPLAYER_TARGETS,
    KILL_EMULATOR_TOO,
    KILL_WAIT,
    GNBOTS_LAUNCH_WAIT,
    LDPLAYER_BOOT_WAIT,
    LDPLAYER_INSTANCE,
)

logger = logging.getLogger("FarmBot.ProcessManager")


def kill_all_targets() -> int:
    """Kill all processes in KILL_TARGETS. If KILL_EMULATOR_TOO, also kill LDPlayer. Returns count killed."""
    logger.info("Killing target processes...")
    killed = 0

    targets = list(KILL_TARGETS)
    if KILL_EMULATOR_TOO:
        targets.extend(LDPLAYER_TARGETS)
        logger.info("  (KILL_EMULATOR_TOO is True — will also kill LDPlayer)")
    else:
        logger.info("  (Leaving LDPlayer running — only killing GnBots)")

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and name.lower() in [t.lower() for t in targets]:
                proc.kill()
                logger.info(f"  Killed: {name} (PID {proc.info['pid']})")
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if killed == 0:
        logger.info("  No target processes were running.")
    else:
        logger.info(f"  Killed {killed} process(es). Waiting {KILL_WAIT}s...")
        time.sleep(KILL_WAIT)

    # Verify — force-kill any stragglers with taskkill /F
    for target in targets:
        if _is_process_running(target):
            logger.warning(f"  {target} still alive — using taskkill /F...")
            _force_kill(target)
            time.sleep(2)

    logger.info("Process cleanup complete.")
    return killed


def _is_process_running(name: str) -> bool:
    """Check if a process with the given name is currently running."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def _force_kill(name: str) -> bool:
    """Use taskkill /F to force-kill a stubborn process."""
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", name],
            capture_output=True,
            timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"  taskkill failed for {name}: {e}")
        return False


def launch_gnbots() -> bool:
    """Launch GnBots with admin elevation via ShellExecuteW. Returns True if confirmed running."""
    if not GNBOTS_PATH.exists():
        logger.error(f"GnBots not found at: {GNBOTS_PATH}")
        return False

    logger.info(f"Launching (as admin): {GNBOTS_PATH}")
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", str(GNBOTS_PATH), None,
            str(GNBOTS_PATH.parent), 1
        )
        if result <= 32:
            logger.error(f"ShellExecuteW failed with code: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to launch GnBots: {e}")
        return False

    logger.info(f"Waiting up to {GNBOTS_LAUNCH_WAIT}s for GnBots to start...")
    start_time = time.time()
    while time.time() - start_time < GNBOTS_LAUNCH_WAIT:
        if _is_process_running("GnBots.exe"):
            # Give it a tiny bit of extra time to initialize its main window
            time.sleep(2)
            logger.info("GnBots confirmed running.")
            return True
        time.sleep(1)

    logger.error("GnBots not found after launch!")
    return False


def is_admin() -> bool:
    """Check if the current process is running with admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """Re-launch the current script with admin privileges (UAC prompt)."""
    import sys
    logger.info("Requesting admin elevation...")
    # Resolve argv[0] to absolute path so the elevated process can find the script
    # regardless of its working directory. Also pass the script's parent directory
    # as lpDirectory so relative imports and file paths work correctly.
    script_path = Path(sys.argv[0]).resolve()
    args = [f'"{script_path}"'] + [f'"{a}"' for a in sys.argv[1:]]
    work_dir = str(script_path.parent)
    logger.info(f"  Elevated args: {' '.join(args)}")
    logger.info(f"  Working dir: {work_dir}")
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(args),
        work_dir, 1,
    )


def check_gnbots_alive() -> bool:
    """Quick check: is GnBots.exe still running? Used for health checks."""
    return _is_process_running("GnBots.exe")


def check_ldplayer_alive() -> bool:
    """Check if any LDPlayer process is running."""
    for target in LDPLAYER_TARGETS:
        if _is_process_running(target):
            return True
    return False


def launch_ldplayer() -> bool:
    """Launch LDPlayer emulator. Returns True if confirmed running."""
    if not LDPLAYER_PATH.exists():
        logger.error(f"LDPlayer not found at: {LDPLAYER_PATH}")
        return False

    logger.info(f"Launching LDPlayer (instance {LDPLAYER_INSTANCE}): {LDPLAYER_PATH}")
    try:
        # Launch with instance number via command line
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", str(LDPLAYER_PATH),
            f"index={LDPLAYER_INSTANCE}",
            str(LDPLAYER_PATH.parent), 1,
        )
        if result <= 32:
            logger.error(f"ShellExecuteW failed for LDPlayer with code: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to launch LDPlayer: {e}")
        return False

    logger.info(f"Waiting {LDPLAYER_BOOT_WAIT}s for LDPlayer to boot...")
    time.sleep(LDPLAYER_BOOT_WAIT)

    if check_ldplayer_alive():
        logger.info("LDPlayer confirmed running.")
        return True

    logger.error("LDPlayer not found after launch!")
    return False


def ensure_ldplayer_running() -> bool:
    """Make sure LDPlayer is running. Launch it if it's not. Returns True if running.

    NOTE: This is typically NOT needed in the normal farm cycle. GnBots
    auto-launches LDPlayer when you click Start, so we kill both at the
    start of each cycle and let GnBots handle emulator startup. This
    function is kept as a utility for manual use or alternative workflows.
    """
    if check_ldplayer_alive():
        logger.info("LDPlayer is already running.")
        return True

    logger.warning("LDPlayer is not running — launching it now...")
    return launch_ldplayer()
