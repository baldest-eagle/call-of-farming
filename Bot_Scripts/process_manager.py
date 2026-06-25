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
    LDMULTIPLAYER_PATH,
    KILL_TARGETS,
    LDPLAYER_TARGETS,
    KILL_EMULATOR_TOO,
    KILL_WAIT,
    GNBOTS_LAUNCH_WAIT,
    LDPLAYER_BOOT_WAIT,
    LDPLAYER_INSTANCE,
)

logger = logging.getLogger("FarmBot.ProcessManager")


# ──────────────────────────────────────────────
#  Shortcut Resolution
# ──────────────────────────────────────────────

def resolve_shortcut(path: Path) -> Path:
    """Resolve a .lnk shortcut to its target executable path.

    If the path is not a .lnk file, returns it unchanged.
    If resolution fails, returns the original path and logs a warning.

    Uses the WScript.Shell COM object (available via pywin32) to read
    the shortcut's TargetPath. This handles both regular shortcuts
    and shortcuts with "Run as administrator" flags.
    """
    if path.suffix.lower() != '.lnk':
        return path

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(path))
        target = shortcut.Targetpath
        if target:
            resolved = Path(target)
            if resolved.exists():
                logger.info(f"Resolved shortcut: {path} -> {resolved}")
                return resolved
            else:
                logger.warning(
                    f"Shortcut target does not exist: {path} -> {resolved}. "
                    f"Falling back to original path."
                )
        else:
            logger.warning(
                f"Shortcut has no target: {path}. "
                f"Falling back to original path."
            )
    except ImportError:
        logger.warning(
            f"win32com not available — cannot resolve shortcut: {path}. "
            f"Install pywin32 or change config to use .exe paths directly."
        )
    except Exception as e:
        logger.warning(f"Failed to resolve shortcut {path}: {e}. Falling back to original path.")

    return path


# Cache resolved paths so we only resolve once per session
_resolved_cache: dict = {}


def resolve_path(path: Path) -> Path:
    """Resolve a shortcut path (with caching). Returns the real .exe path."""
    if str(path) not in _resolved_cache:
        _resolved_cache[str(path)] = resolve_shortcut(path)
    return _resolved_cache[str(path)]


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
    """Launch GnBots with admin elevation via ShellExecuteW. Returns True if confirmed running.

    If GNBOTS_PATH is a .lnk shortcut, resolves it to the real .exe first.
    This ensures ShellExecuteW("runas") directly elevates the executable
    (which is reliable) rather than trying to elevate through a shortcut
    (which is unreliable across Windows versions).

    The working directory is set to the resolved .exe's parent directory,
    so GnBots can find its own resource files correctly.
    """
    if not GNBOTS_PATH.exists():
        logger.error(f"GnBots not found at: {GNBOTS_PATH}")
        return False

    # Resolve .lnk -> .exe so we launch the real executable directly
    exe_path = resolve_path(GNBOTS_PATH)
    work_dir = str(exe_path.parent)

    logger.info(f"Launching (as admin): {exe_path}  [original: {GNBOTS_PATH}]")
    logger.info(f"Working directory: {work_dir}")
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", str(exe_path), None,
            work_dir, 1
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
    """Launch LDPlayer emulator. Returns True if confirmed running.

    If LDPLAYER_PATH is a .lnk shortcut, resolves it to the real .exe first.
    This ensures ShellExecuteW gets the actual executable with its correct
    working directory, and command-line arguments (like index=) are passed
    to the real .exe rather than silently ignored by the shortcut.
    """
    if not LDPLAYER_PATH.exists():
        logger.error(f"LDPlayer not found at: {LDPLAYER_PATH}")
        return False

    # Resolve .lnk -> .exe so arguments reach the real executable
    exe_path = resolve_path(LDPLAYER_PATH)
    work_dir = str(exe_path.parent)

    logger.info(f"Launching LDPlayer (instance {LDPLAYER_INSTANCE}): {exe_path}  [original: {LDPLAYER_PATH}]")
    logger.info(f"Working directory: {work_dir}")
    try:
        # Launch with instance number via command line
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", str(exe_path),
            f"index={LDPLAYER_INSTANCE}",
            work_dir, 1,
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
