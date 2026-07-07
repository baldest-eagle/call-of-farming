#!/usr/bin/env python3
"""
setup_farm_bot.py — One-shot setup script for the Farm Bot automation.

Features:
  - Self-elevation: auto-relaunches as admin via UAC if needed
  - Color output: green/red/yellow status indicators
  - Setup log: writes everything to setup.log
  - Welcome screen: explains what setup will do
  - Software installation: downloads + installs LDPlayer 9, opens GnBots download page
  - Auto-detection: scans common paths, Program Files, desktop shortcuts
  - Webhook test: sends a test message to verify Discord/Slack config
  - Task Scheduler: offers presets (every 2h/3h/1h) or custom schedule
  - Status screen: clear ✓/✗ summary at the end
  - --reconfig: regenerate just user_config.py without full setup
  - --check: validation only, no changes
  - --non-interactive: use defaults, skip prompts

Usage:
    python setup_farm_bot.py              # Interactive setup
    python setup_farm_bot.py --reconfig   # Just regenerate user_config.py
    python setup_farm_bot.py --check      # Validation only
    python setup_farm_bot.py --non-interactive  # Use defaults
"""

import os
import sys
import re
import json
import ctypes
import shutil
import logging
import subprocess
import platform
import urllib.request
import urllib.error
import tempfile
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
USER_CONFIG_FILE = PROJECT_DIR / "user_config.py"
USER_CONFIG_TEMPLATE = PROJECT_DIR / "user_config.example.py"
SETUP_LOG_FILE = PROJECT_DIR / "setup.log"

DIRS_TO_CREATE = [
    "templates",
    "screenshots",
    "screenshots\\diffs",
    "logs",
]

MIN_PYTHON = (3, 8)

# ── Download URLs ────────────────────────────────────────────
LDPLAYER_DOWNLOAD_URL = (
    "https://res.ldrescdn.com/download/LDPlayer9.exe"
    "?n=LDPlayer9_ens_1379_ld.exe"
)
GNBOTS_DOWNLOAD_PAGE = "https://www.gnbots.com/shop/download"

# ── Common install paths to auto-detect ──────────────────────
GNBOTS_SEARCH_PATHS = [
    r"C:\Program Files\GnBots\GnBots.exe",
    r"C:\Program Files (x86)\GnBots\GnBots.exe",
    r"C:\GnBots\GnBots.exe",
    r"D:\GnBots\GnBots.exe",
    r"C:\Users\Public\Desktop\GnBots.lnk",
    r"C:\Users\Public\Desktop\Goodnight Bots.lnk",
]

LDPLAYER_SEARCH_PATHS = [
    r"C:\LDPlayer\LDPlayer9\dnplayer.exe",
    r"C:\LDPlayer\dnplayer.exe",
    r"D:\LDPlayer\LDPlayer9\dnplayer.exe",
    r"D:\leidian\LDPlayer9\dnplayer.exe",
    r"C:\leidian\LDPlayer9\dnplayer.exe",
    r"C:\Program Files\LDPlayer\LDPlayer9\dnplayer.exe",
    r"C:\Program Files (x86)\LDPlayer\LDPlayer9\dnplayer.exe",
    r"C:\XuanZhi\LDPlayer9\dnplayer.exe",
    r"C:\LDPlayer9\dnplayer.exe",
]

# ──────────────────────────────────────────────────────────────
#  Color Output
# ──────────────────────────────────────────────────────────────

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def enable_ansi_colors():
    """Enable ANSI escape sequences on Windows 10+."""
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def cprint(text: str = "", color: str = "", end: str = "\n"):
    """Print with color."""
    print(f"{color}{text}{Colors.RESET}", end=end)


def ok(text: str = ""):
    cprint(f"  [OK] {text}" if text else "  [OK]", Colors.GREEN)


def warn(text: str = ""):
    cprint(f"  [!!] {text}" if text else "  [!!]", Colors.YELLOW)


def err(text: str = ""):
    cprint(f"  [XX] {text}" if text else "  [XX]", Colors.RED)


def info(text: str = ""):
    cprint(f"  {text}", Colors.BLUE)


# ──────────────────────────────────────────────────────────────
#  Setup Logging
# ──────────────────────────────────────────────────────────────

class TeeWriter:
    """Write to both console and log file."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_file = None
        self._open()

    def _open(self):
        try:
            self.log_file = open(self.log_path, 'a', encoding='utf-8')
            self.log_file.write(f"\n{'=' * 60}\n")
            self.log_file.write(f"Setup log — {datetime.now().isoformat()}\n")
            self.log_file.write(f"{'=' * 60}\n")
        except Exception as e:
            print(f"WARNING: Could not open setup log: {e}")

    def write(self, text: str):
        # Strip ANSI color codes for log file
        clean = re.sub(r'\033\[[0-9;]*m', '', text)
        if self.log_file:
            try:
                self.log_file.write(clean)
                self.log_file.flush()
            except Exception:
                pass
        sys.__stdout__.write(text)

    def flush(self):
        if self.log_file:
            try:
                self.log_file.flush()
            except Exception:
                pass
        sys.__stdout__.flush()

    def close(self):
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass


def setup_logging():
    """Redirect stdout/stderr through the tee writer so everything is logged."""
    tee = TeeWriter(SETUP_LOG_FILE)
    sys.stdout = tee
    sys.stderr = tee


# ──────────────────────────────────────────────────────────────
#  Self-Elevation
# ──────────────────────────────────────────────────────────────

def is_admin() -> bool:
    """Check if running with admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def self_elevate() -> bool:
    """If not running as admin, relaunch self with UAC prompt. Returns False if user declined."""
    if is_admin():
        return True

    info("This script needs admin privileges.")
    info("Requesting elevation via UAC...")
    info("(Click 'Yes' on the UAC prompt to continue.)")
    print()

    try:
        # Build the command to relaunch self
        script_path = Path(sys.argv[0]).resolve()
        params = " ".join([f'"{a}"' for a in sys.argv[1:]])
        if params:
            params = " " + params

        # ShellExecuteW with "runas" verb triggers UAC
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{script_path}"{params}',
            str(script_path.parent), 1,
        )
        if result <= 32:
            err(f"UAC elevation failed (error code: {result})")
            return False
        # The elevated process is starting — exit this one
        return True
    except Exception as e:
        err(f"Could not self-elevate: {e}")
        return False


# ──────────────────────────────────────────────────────────────
#  UI Helpers
# ──────────────────────────────────────────────────────────────

def banner(title: str) -> None:
    print()
    print("=" * 60)
    cprint(f"  {title}", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print()


def step(num: int, total: int, text: str) -> None:
    print()
    cprint(f"[{num}/{total}] {text}", Colors.BOLD + Colors.BLUE)
    print("-" * 60)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer if answer else default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"  {prompt} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def find_pythonw(venv_dir: Path) -> Path:
    """Find pythonw.exe in the virtual environment."""
    pythonw = venv_dir / "Scripts" / "pythonw.exe"
    if pythonw.exists():
        return pythonw
    sys_pythonw = Path(sys.executable).parent / "pythonw.exe"
    if sys_pythonw.exists():
        return sys_pythonw
    return Path(sys.executable)


def download_progress(block_num: int, block_size: int, total_size: int) -> None:
    """Callback for urllib to show download progress."""
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 // total_size)
        mb_done = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        sys.stdout.write(
            f"\r  Downloading: {mb_done:.1f}/{mb_total:.1f} MB ({pct}%)"
        )
        sys.stdout.flush()
        if pct >= 100:
            print()
    else:
        mb_done = downloaded / (1024 * 1024)
        sys.stdout.write(f"\r  Downloaded: {mb_done:.1f} MB")
        sys.stdout.flush()


# ──────────────────────────────────────────────────────────────
#  Welcome Screen
# ──────────────────────────────────────────────────────────────

def show_welcome() -> None:
    """Brief intro explaining what the bot does and what setup will do."""
    banner("Farm Bot Setup")

    print("  This setup script will get your system ready to run the")
    print("  Farm Bot — an automation tool that controls GnBots + LDPlayer")
    print("  to farm mobile games automatically.")
    print()
    cprint("  What this script will do:", Colors.BOLD)
    print("    1. Check your Python version and OS")
    print("    2. Create a Python virtual environment")
    print("    3. Install Python dependencies")
    print("    4. Download and install LDPlayer 9 (if missing)")
    print("    5. Help you install GnBots (if missing)")
    print("    6. Create required directories")
    print("    7. Generate user_config.py with your settings")
    print("    8. Validate everything is working")
    print("    9. Optionally set up Task Scheduler for auto-cycling")
    print()
    cprint("  Estimated time: 5-15 minutes (depending on downloads).", Colors.YELLOW)
    print()
    cprint("  A log file will be saved to: setup.log", Colors.BLUE)
    print("  If anything fails, share that log when asking for help.")
    print()


# ──────────────────────────────────────────────────────────────
#  Step 1: Environment Check
# ──────────────────────────────────────────────────────────────

def check_python_version() -> bool:
    version = sys.version_info
    if version < MIN_PYTHON:
        err(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.")
        print(f"  You have Python {version.major}.{version.minor}.{version.micro}")
        return False
    ok(f"Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_os() -> bool:
    if platform.system() != "Windows":
        warn("This bot requires Windows (uses pywin32, win32gui, etc.).")
        print("  It will NOT run on macOS or Linux.")
        return False
    ok(f"OS: {platform.system()} {platform.release()}")
    return True


def check_admin_status() -> None:
    if is_admin():
        ok("Running as admin")
    else:
        warn("Not running as admin — some features will be unavailable:")
        print("    - Sending clicks to elevated windows")
        print("    - Creating scheduled tasks with highest privileges")


# ──────────────────────────────────────────────────────────────
#  Step 2: Virtual Environment
# ──────────────────────────────────────────────────────────────

def create_venv() -> bool:
    if VENV_DIR.exists():
        info(f"Virtual environment already exists at: {VENV_DIR}")
        return True

    info(f"Creating virtual environment at: {VENV_DIR}")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
        )
        ok("Virtual environment created.")
        return True
    except subprocess.CalledProcessError as e:
        err(f"Failed to create virtual environment: {e}")
        return False


def install_requirements() -> bool:
    pip_exe = VENV_DIR / "Scripts" / "pip.exe"
    if not pip_exe.exists():
        pip_exe = VENV_DIR / "Scripts" / "python.exe"
        pip_cmd = [str(pip_exe), "-m", "pip"]
    else:
        pip_cmd = [str(pip_exe)]

    if not REQUIREMENTS_FILE.exists():
        err(f"requirements.txt not found at: {REQUIREMENTS_FILE}")
        return False

    info(f"Installing dependencies from: {REQUIREMENTS_FILE}")
    try:
        subprocess.run(
            pip_cmd + ["install", "-r", str(REQUIREMENTS_FILE)],
            check=True,
        )
        ok("Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        err(f"Failed to install dependencies: {e}")
        print("  Try manually: .venv\\Scripts\\pip.exe install -r requirements.txt")
        return False


# ──────────────────────────────────────────────────────────────
#  Step 3: Software Installation (GnBots + LDPlayer)
# ──────────────────────────────────────────────────────────────

def find_existing_install(search_paths: list) -> str:
    """Search common install paths for an existing executable."""
    for path_str in search_paths:
        p = Path(path_str)
        if p.exists():
            return str(p)
    return ""


def search_program_files(name_pattern: str) -> str:
    """Search Program Files directories for an executable."""
    search_dirs = [
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path(r"D:\Program Files"),
        Path(r"D:\Program Files (x86)"),
    ]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        try:
            for item in search_dir.rglob(name_pattern):
                return str(item)
        except (PermissionError, OSError):
            continue
    return ""


def search_desktop_shortcuts(pattern: str) -> str:
    """Search for desktop shortcuts matching the pattern."""
    desktop_dirs = [
        Path.home() / "Desktop",
        Path(r"C:\Users\Public\Desktop"),
    ]
    for desktop in desktop_dirs:
        if not desktop.exists():
            continue
        try:
            for shortcut in desktop.glob(f"*{pattern}*"):
                return str(shortcut)
        except (PermissionError, OSError):
            continue
    return ""


def search_start_menu(pattern: str) -> str:
    """Search Start Menu for shortcuts."""
    start_menu_dirs = [
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for start_dir in start_menu_dirs:
        if not start_dir.exists():
            continue
        try:
            for shortcut in start_dir.rglob(f"*{pattern}*"):
                return str(shortcut)
        except (PermissionError, OSError):
            continue
    return ""


def auto_detect_gnbots() -> str:
    """Try to find GnBots on the system."""
    # 1. Common install paths
    result = find_existing_install(GNBOTS_SEARCH_PATHS)
    if result:
        return result

    # 2. Program Files
    result = search_program_files("GnBots.exe")
    if result:
        return result

    # 3. Desktop shortcuts
    result = search_desktop_shortcuts("GnBot")
    if result:
        return result

    # 4. Start Menu
    result = search_start_menu("GnBot")
    if result:
        return result

    return ""


def auto_detect_ldplayer() -> tuple:
    """Try to find LDPlayer on the system."""
    # 1. Common install paths
    dnplayer = find_existing_install(LDPLAYER_SEARCH_PATHS)
    if dnplayer:
        parent = Path(dnplayer).parent
        ldmulti = parent / "dnmultiplayer.exe"
        return dnplayer, str(ldmulti) if ldmulti.exists() else ""

    # 2. Program Files
    result = search_program_files("dnplayer.exe")
    if result:
        parent = Path(result).parent
        ldmulti = parent / "dnmultiplayer.exe"
        return result, str(ldmulti) if ldmulti.exists() else ""

    # 3. Desktop shortcuts
    result = search_desktop_shortcuts("LDPlayer")
    if result:
        return result, ""

    # 4. Start Menu
    result = search_start_menu("LDPlayer")
    if result:
        return result, ""

    return "", ""


def download_ldplayer(install_dir: str = "") -> str:
    """Download LDPlayer 9 installer."""
    print()
    info("Downloading LDPlayer 9 installer...")
    print(f"  URL: {LDPLAYER_DOWNLOAD_URL}")

    if not install_dir:
        install_dir = os.path.join(tempfile.gettempdir(), "farm_bot_setup")
    os.makedirs(install_dir, exist_ok=True)
    installer_path = os.path.join(install_dir, "LDPlayer9_installer.exe")

    try:
        urllib.request.urlretrieve(
            LDPLAYER_DOWNLOAD_URL,
            installer_path,
            reporthook=download_progress,
        )
        size_mb = os.path.getsize(installer_path) / (1024 * 1024)
        ok(f"Downloaded: {installer_path} ({size_mb:.1f} MB)")
        return installer_path
    except urllib.error.URLError as e:
        err(f"Download failed: {e}")
        print("  You can download LDPlayer manually from: https://www.ldplayer.net")
        return ""
    except Exception as e:
        err(f"Download failed: {e}")
        return ""


def install_ldplayer(installer_path: str) -> bool:
    """Run the LDPlayer installer. Tries silent install first."""
    if not os.path.exists(installer_path):
        err(f"Installer not found: {installer_path}")
        return False

    print()
    info("Running LDPlayer installer...")
    print("  (This may take a minute. The installer window may appear on screen.)")

    # Try silent install first
    try:
        info("Attempting silent install (/S)...")
        result = subprocess.run(
            [installer_path, "/S"],
            capture_output=True,
            timeout=300,
        )
        if result.returncode == 0:
            ok("Silent install completed.")
            return True
    except subprocess.TimeoutExpired:
        warn("Silent install timed out — trying GUI install instead...")
    except Exception:
        warn("Silent install failed — trying GUI install instead...")

    # GUI install
    try:
        info("Launching GUI installer...")
        cprint("  >>> Complete the installation in the LDPlayer window, then come back. <<<", Colors.YELLOW)
        subprocess.run([installer_path], check=False)
        ok("LDPlayer installer finished.")
        return True
    except Exception as e:
        err(f"Could not run installer: {e}")
        return False


def install_gnbots() -> bool:
    """Open GnBots download page in the user's browser and wait."""
    print()
    warn("GnBots requires an account — there's no direct download link.")
    info("I'll open the download page in your browser.")
    print()
    cprint("  Steps:", Colors.BOLD)
    print("    1. Log in or create a free account")
    print("    2. Download the PC version")
    print("    3. Install it (remember where it goes!)")
    print("    4. I will automatically detect when it finishes installing.")
    print()

    want_open = ask_yes_no("Open GnBots download page in your browser?", default=True)
    if want_open:
        try:
            import webbrowser
            webbrowser.open(GNBOTS_DOWNLOAD_PAGE)
            ok(f"Opened: {GNBOTS_DOWNLOAD_PAGE}")
        except Exception as e:
            warn(f"Could not open browser: {e}")
            print(f"  Go to: {GNBOTS_DOWNLOAD_PAGE}")
    else:
        print(f"  Download GnBots from: {GNBOTS_DOWNLOAD_PAGE}")

    print("\n  Waiting for GnBots to be installed... (Press Ctrl+C to skip auto-detect)")
    try:
        import time
        while True:
            if auto_detect_gnbots():
                print("\n")
                ok("GnBots installation detected automatically!")
                break
            time.sleep(2)
            sys.stdout.write(".")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n  Skipped auto-detect.")

    return True


def install_software(non_interactive: bool = False) -> dict:
    """Check for and optionally install GnBots and LDPlayer."""
    results = {
        "gnbots_path": "",
        "ldplayer_path": "",
        "ldmulti_path": "",
    }

    # ── GnBots ──
    print()
    info("Checking for GnBots...")
    gnbots = auto_detect_gnbots()
    if gnbots:
        ok(f"Found GnBots at: {gnbots}")
        results["gnbots_path"] = gnbots
    else:
        warn("GnBots not found on your system.")
        if not non_interactive:
            want_install = ask_yes_no("Would you like to install GnBots now?", default=True)
            if want_install:
                install_gnbots()
                gnbots = auto_detect_gnbots()
                if gnbots:
                    ok(f"Detected GnBots at: {gnbots}")
                    results["gnbots_path"] = gnbots
                else:
                    warn("Could not auto-detect GnBots location.")
                    print("  You'll need to provide the path manually.")
        else:
            print("  Skipping (non-interactive). Install it from:")
            print(f"    {GNBOTS_DOWNLOAD_PAGE}")

    # ── LDPlayer ──
    print()
    info("Checking for LDPlayer...")
    ldplayer, ldmulti = auto_detect_ldplayer()
    if ldplayer:
        ok(f"Found LDPlayer at: {ldplayer}")
        results["ldplayer_path"] = ldplayer
        results["ldmulti_path"] = ldmulti
    else:
        warn("LDPlayer not found on your system.")
        if not non_interactive:
            want_install = ask_yes_no(
                "Would you like to download and install LDPlayer 9 now?",
                default=True,
            )
            if want_install:
                installer_path = download_ldplayer()
                if installer_path:
                    success = install_ldplayer(installer_path)
                    if success:
                        ldplayer, ldmulti = auto_detect_ldplayer()
                        if ldplayer:
                            ok(f"Detected LDPlayer at: {ldplayer}")
                            results["ldplayer_path"] = ldplayer
                            results["ldmulti_path"] = ldmulti
                        else:
                            warn("Could not auto-detect LDPlayer location.")
                            print("  You'll need to provide the path manually.")
                    try:
                        os.remove(installer_path)
                    except OSError:
                        pass
        else:
            print("  Skipping (non-interactive). Download it from:")
            print("    https://www.ldplayer.net")

    # ── Manual path entry ──
    if not non_interactive:
        if not results["gnbots_path"]:
            print()
            gnbots_manual = ask("GnBots path (enter manually, or leave blank to skip)", "")
            if gnbots_manual:
                results["gnbots_path"] = gnbots_manual

        if not results["ldplayer_path"]:
            print()
            ldplayer_manual = ask(
                "LDPlayer path (enter manually, or leave blank to skip)",
                r"C:\LDPlayer\LDPlayer9\dnplayer.exe",
            )
            if ldplayer_manual:
                results["ldplayer_path"] = ldplayer_manual
                parent = Path(ldplayer_manual).parent
                ldmulti_guess = parent / "dnmultiplayer.exe"
                results["ldmulti_path"] = str(ldmulti_guess) if ldmulti_guess.exists() else ""

    return results


# ──────────────────────────────────────────────────────────────
#  Step 4: Directory Structure
# ──────────────────────────────────────────────────────────────

def create_directories() -> bool:
    info("Creating project directories...")
    all_ok = True
    for dir_path in DIRS_TO_CREATE:
        full_path = PROJECT_DIR / dir_path
        if full_path.exists():
            print(f"    {dir_path}/  — already exists")
        else:
            try:
                full_path.mkdir(parents=True, exist_ok=True)
                ok(f"{dir_path}/  — created")
            except OSError as e:
                err(f"{dir_path}/  — FAILED: {e}")
                all_ok = False
    return all_ok


# ──────────────────────────────────────────────────────────────
#  Step 5: User Configuration
# ──────────────────────────────────────────────────────────────

def generate_user_config(
    non_interactive: bool = False,
    detected_paths: dict = None,
) -> bool:
    if detected_paths is None:
        detected_paths = {}

    if USER_CONFIG_FILE.exists() and not non_interactive:
        overwrite = ask_yes_no("user_config.py already exists. Overwrite?", default=False)
        if not overwrite:
            info("Keeping existing user_config.py.")
            return True

    # Resolve paths
    gnbots_default = detected_paths.get("gnbots_path") or r"C:\Program Files\GnBots\GnBots.exe"
    ldplayer_default = detected_paths.get("ldplayer_path") or r"C:\LDPlayer\LDPlayer9\dnplayer.exe"
    ldmulti_default = detected_paths.get("ldmulti_path") or r"C:\LDPlayer\LDPlayer9\dnmultiplayer.exe"

    if non_interactive:
        gnbots_path = gnbots_default
        ldplayer_path = ldplayer_default
        ldmulti_path = ldmulti_default
        webhook_url = ""
        webhook_enabled = False
    else:
        print()
        info("I need a few paths to configure the bot for your system.")
        print("  Press Enter to accept the [default] value.\n")

        print("  Where is GnBots installed?")
        print("  (This can be the .exe, a shortcut .lnk, or a folder —")
        print("   the bot will launch whatever you point it at.)")
        gnbots_path = ask("GnBots path", gnbots_default)

        print()
        print("  Where is LDPlayer installed?")
        print("  (The main dnplayer.exe or a shortcut to it.)")
        ldplayer_path = ask("LDPlayer path", ldplayer_default)

        print()
        print("  Where is LDMultiPlayer? (optional, used for multi-instance)")
        ldmulti_path = ask("LDMultiPlayer path", ldmulti_default)

        print()
        cprint("  Want Discord/Slack notifications? (optional)", Colors.BOLD)
        print("  To get a Discord Webhook URL:")
        print("    1. Go to your Discord server settings > Integrations > Webhooks")
        print("    2. Click 'New Webhook', then 'Copy Webhook URL'")
        print("    3. Paste it below (or leave blank to skip)")
        webhook_url = ask("Webhook URL", "")
        webhook_enabled = bool(webhook_url)

    # ── Build the config file ──
    config_content = f'''"""
user_config.py — Your personal Farm Bot configuration.

This file overrides the defaults in config.py. It is NOT tracked by git,
so your paths and webhook URLs stay private.

To change settings later, edit this file directly, or run:
    python setup_farm_bot.py --reconfig
"""

from pathlib import Path

# ── Application Paths ─────────────────────────────────────
GNBOTS_PATH = Path(r"{gnbots_path}")
LDPLAYER_PATH = Path(r"{ldplayer_path}")
LDMULTIPLAYER_PATH = Path(r"{ldmulti_path}")

# ── Notifications ─────────────────────────────────────────
NOTIFICATIONS = {{
    "webhook_url": {repr(webhook_url) if webhook_url else "None"},
    "webhook_enabled": {webhook_enabled},
    "desktop_enabled": False,
    "on_cycle_start": True,
    "on_cycle_complete": True,
    "on_error": True,
    "on_health_fail": True,
    "on_completion_detected": True,
    "sound_file": None,
}}

# ── Monitor Position ─────────────────────────────────────
# Where to move the GnBots window (0,0 = primary monitor).
# config.py auto-detects your secondary monitor, so you usually
# don't need to change this. Override here if auto-detect fails.
# MONITOR2_X = 1920
# MONITOR2_Y = 0

# ── Headless Mode ────────────────────────────────────────
# True = bot doesn't move your mouse (uses PostMessage clicks)
# False = bot moves mouse to click (more reliable, but you can't use PC)
# HEADLESS = False

# ── Ghost Mode ───────────────────────────────────────────
# Makes windows invisible while bot runs. Requires HEADLESS=True.
# GHOST_MODE = False
# GHOST_ALPHA = 0   # 0=invisible, 1=trace, 255=off

# ── Virtual Display ──────────────────────────────────────
# Set True to prefer virtual displays (Parsec VDD, etc.)
# VDD_PREFER = True

# ── Coordinate Fallbacks ─────────────────────────────────
# If template matching fails, click these absolute screen coords.
# Use click_test.py --coords X Y to find values for your setup.
# COORD_FALLBACK_ENABLED = True
# COORD_FALLBACKS = {{
#     "start_btn": None,
#     "first_btn": None,
#     "continue_btn": None,
# }}
'''

    try:
        USER_CONFIG_FILE.write_text(config_content, encoding='utf-8')
        ok(f"Wrote user_config.py to: {USER_CONFIG_FILE}")
        return True
    except OSError as e:
        err(f"Failed to write user_config.py: {e}")
        return False


def generate_user_config_example() -> None:
    example_content = '''"""
user_config.example.py — Template for user_config.py.

Copy this file to user_config.py and fill in your paths:
    copy user_config.example.py user_config.py

Or just run: python setup_farm_bot.py
    (it generates user_config.py automatically and can install the apps)

user_config.py is .gitignored — your settings stay private.
"""

from pathlib import Path

# ── Application Paths ─────────────────────────────────────
GNBOTS_PATH = Path(r"C:\\Path\\To\\GnBots.exe")        # TODO: Set your path
LDPLAYER_PATH = Path(r"C:\\Path\\To\\dnplayer.exe")     # TODO: Set your path
LDMULTIPLAYER_PATH = Path(r"C:\\Path\\To\\dnmultiplayer.exe")  # TODO: Set your path

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
'''
    example_path = PROJECT_DIR / "user_config.example.py"
    try:
        example_path.write_text(example_content, encoding='utf-8')
        ok("Wrote user_config.example.py (template for repo)")
    except OSError as e:
        warn(f"Could not write user_config.example.py: {e}")


# ──────────────────────────────────────────────────────────────
#  Webhook Test
# ──────────────────────────────────────────────────────────────

def test_webhook(webhook_url: str) -> bool:
    """Send a test message to verify the webhook works."""
    if not webhook_url:
        return False

    info(f"Sending test message to webhook...")
    print(f"  URL: {webhook_url[:60]}...")

    payload = {
        "embeds": [{
            "title": "FarmBot: Setup Complete!",
            "description": "Your webhook is working. You'll receive notifications when farm cycles start, complete, or fail.",
            "color": 0x00FF00,
            "footer": {"text": datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
        }]
    } if "discord" in webhook_url else {
        "text": f"**FarmBot: Setup Complete!**\nYour webhook is working.\n_{datetime.now()}_"
    }

    try:
        import json as _json
        data = _json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                ok("Webhook test successful! Check your Discord/Slack.")
                return True
            else:
                warn(f"Webhook returned status {resp.status}")
                return False
    except urllib.error.URLError as e:
        err(f"Webhook test failed: {e}")
        print("  Check that the URL is correct and the webhook is active.")
        return False
    except Exception as e:
        err(f"Webhook test failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────
#  Step 6: Validation
# ──────────────────────────────────────────────────────────────

def validate_setup() -> bool:
    """Run post-setup validation checks. Returns True if all critical checks pass."""
    info("Running validation checks...\n")
    all_ok = True
    issues = []

    # Directories
    for dir_path in DIRS_TO_CREATE:
        full_path = PROJECT_DIR / dir_path
        if not full_path.exists():
            issues.append(f"Missing directory: {dir_path}")
            all_ok = False
        else:
            ok(f"{dir_path}/")

    # Virtual environment
    if VENV_DIR.exists():
        ok(".venv/")
    else:
        issues.append("Virtual environment not created")
        all_ok = False

    # Key Python packages
    venv_python = VENV_DIR / "Scripts" / "python.exe"
    if venv_python.exists():
        packages = ["psutil", "cv2", "pyautogui", "win32gui", "numpy"]
        for pkg in packages:
            try:
                result = subprocess.run(
                    [str(venv_python), "-c", f"import {pkg}"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    ok(f"{pkg} (installed)")
                else:
                    issues.append(f"Package not working: {pkg}")
                    all_ok = False
            except Exception as e:
                issues.append(f"Could not verify package {pkg}: {e}")
                all_ok = False
    else:
        issues.append("Venv python.exe not found — cannot check packages")
        all_ok = False

    # user_config.py
    if USER_CONFIG_FILE.exists():
        ok("user_config.py")
    else:
        issues.append("user_config.py not created")
        all_ok = False

    # GnBots / LDPlayer from user_config
    if USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, 'r') as f:
                content = f.read()
            for key, label in [("GNBOTS_PATH", "GnBots"), ("LDPLAYER_PATH", "LDPlayer")]:
                for line in content.splitlines():
                    if key in line and not line.strip().startswith("#"):
                        match = re.search(r'r"([^"]+)"', line)
                        if match:
                            app_path = Path(match.group(1))
                            if app_path.exists():
                                ok(f"{label} at {app_path}")
                            else:
                                issues.append(f"{label} path does not exist: {app_path}")
                                warn(f"{label} at {app_path} — NOT FOUND")
                        break
        except Exception:
            pass

    # Templates
    template_dir = PROJECT_DIR / "templates"
    start_btn = template_dir / "start_btn.png"
    if start_btn.exists():
        ok("templates/start_btn.png")
    else:
        issues.append("templates/start_btn.png is MISSING — the bot requires this!")
        err("templates/start_btn.png — MISSING (required!)")

    for tpl in ["first_btn.png", "continue_btn.png", "stop_btn.png", "completed.png"]:
        tpl_path = template_dir / tpl
        if tpl_path.exists():
            ok(f"templates/{tpl} (optional)")
        else:
            print(f"    {tpl}  — not found (optional)")

    # Summary
    print()
    if all_ok and not issues:
        cprint("  All validation checks PASSED!", Colors.BOLD + Colors.GREEN)
    else:
        cprint(f"  Validation found {len(issues)} issue(s):", Colors.BOLD + Colors.YELLOW)
        for i, issue in enumerate(issues, 1):
            cprint(f"    {i}. {issue}", Colors.YELLOW)

    return all_ok


# ──────────────────────────────────────────────────────────────
#  Status Screen
# ──────────────────────────────────────────────────────────────

def show_status_screen() -> None:
    """Clear summary of what's set up and what needs to happen next."""
    print()
    print("=" * 60)
    cprint("  SETUP STATUS", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print()

    checks = [
        ("Python environment", VENV_DIR.exists()),
        ("Dependencies installed", (VENV_DIR / "Scripts" / "python.exe").exists()),
        ("Directories created", all((PROJECT_DIR / d).exists() for d in DIRS_TO_CREATE)),
        ("user_config.py", USER_CONFIG_FILE.exists()),
        ("templates/start_btn.png", (PROJECT_DIR / "templates" / "start_btn.png").exists()),
        ("Tested (run test_setup.py)", (PROJECT_DIR / "logs" / ".tested").exists()),
    ]

    # Safe checkmark rendering for Windows cp1252 consoles
    try:
        check_char = "✓"
        cross_char = "✗"
        check_char.encode(sys.__stdout__.encoding or "utf-8")
    except UnicodeEncodeError:
        check_char = "OK"
        cross_char = "XX"

    for label, passed in checks:
        if passed:
            cprint(f"  [{check_char}] {label}", Colors.GREEN)
        else:
            cprint(f"  [{cross_char}] {label}", Colors.RED)

    print()
    cprint("  Next steps:", Colors.BOLD)
    print()

    # Check what's missing and suggest next actions
    has_templates = (PROJECT_DIR / "templates" / "start_btn.png").exists()
    has_venv = VENV_DIR.exists()

    if not has_venv:
        cprint("  1. Run setup again:", Colors.YELLOW)
        print("       python setup_farm_bot.py")
    elif not has_templates:
        cprint("  1. Capture template images:", Colors.YELLOW)
        print("       Double-click capture.bat")
        print("       (or: python capture_templates.py)")
        print()
        cprint("  2. Test your setup:", Colors.YELLOW)
        print("       Double-click test.bat")
        print("       (or: python test_setup.py)")
        print()
        cprint("  3. Run a farm cycle:", Colors.YELLOW)
        print("       Double-click start.bat")
        print("       (or: python farm_cycle.py)")
    else:
        cprint("  1. Test your setup:", Colors.YELLOW)
        print("       Double-click test.bat")
        print("       (or: python test_setup.py)")
        print()
        cprint("  2. Run a farm cycle:", Colors.YELLOW)
        print("       Double-click start.bat")
        print("       (or: python farm_cycle.py)")
        print()
        cprint("  3. (Optional) Set up auto-cycling:", Colors.YELLOW)
        print("       Double-click schedule.bat")
        print("       (or: python schedule_tasks.py)")
        print()
        cprint("  4. (Optional) Set up notifications:", Colors.YELLOW)
        print("       Double-click notifications.bat")
        print("       (or: python notifications.py)")

    print()
    info(f"Setup log: {SETUP_LOG_FILE}")
    info("Edit user_config.py anytime to change settings.")
    info("Run 'python setup_farm_bot.py --check' to re-validate.")


# ──────────────────────────────────────────────────────────────
#  Step 7: Task Scheduler with Presets
# ──────────────────────────────────────────────────────────────

def setup_task_scheduler() -> bool:
    if not is_admin():
        warn("Skipping Task Scheduler setup (requires admin).")
        print("  Re-run this script as admin to enable this step,")
        print("  or double-click schedule.bat")
        return False

    want_schedule = ask_yes_no("Set up Task Scheduler for auto-cycling?", default=True)
    if not want_schedule:
        info("Skipped. You can set this up later with schedule.bat")
        return True

    venv_pythonw = find_pythonw(VENV_DIR)
    farm_cycle = PROJECT_DIR / "farm_cycle.py"

    if not farm_cycle.exists():
        err(f"farm_cycle.py not found at {farm_cycle}")
        return False

    # Delete existing task
    subprocess.run(
        ['schtasks', '/Delete', '/TN', 'FarmCycle', '/F'],
        capture_output=True,
    )

    # ── Preset menu ──
    print()
    cprint("  Choose a schedule:", Colors.BOLD)
    print("    1. Every 1 hour  (more aggressive — uses trial resets often)")
    print("    2. Every 2 hours (balanced)")
    print("    3. Every 3 hours (recommended — GnBots free trial is 2 hours)")
    print("    4. Every 6 hours (conservative)")
    print("    5. Custom (you specify interval)")
    print()

    choice = ask("Choose 1-5", "3")

    presets = {
        "1": ("60", "1 hour"),
        "2": ("120", "2 hours"),
        "3": ("180", "3 hours"),
        "4": ("360", "6 hours"),
    }

    if choice in presets:
        interval, label = presets[choice]
    elif choice == "5":
        interval = ask("Interval in minutes", "180")
        label = f"{interval} minutes"
    else:
        warn(f"Invalid choice '{choice}', using default (3 hours)")
        interval, label = "180", "3 hours"

    start_time = ask("Start time (24h format, e.g. 08:00)", "08:00")

    create_cmd = [
        'schtasks', '/Create',
        '/TN', 'FarmCycle',
        '/TR', f'{venv_pythonw} {farm_cycle}',
        '/SC', 'DAILY',
        '/ST', start_time,
        '/RI', interval,
        '/DU', '24:00',
        '/RL', 'HIGHEST',
        '/F',
    ]

    try:
        result = subprocess.run(create_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            ok(f"Task 'FarmCycle' created successfully!")
            print(f"    Runs every {label} starting at {start_time}")
            print(f"    Python: {venv_pythonw}")
            print(f"    Script: {farm_cycle}")
            return True
        else:
            warn("Primary schedule failed, trying fallback...")
            create_cmd_fallback = [
                'schtasks', '/Create',
                '/TN', 'FarmCycle',
                '/TR', f'{venv_pythonw} {farm_cycle}',
                '/SC', 'DAILY',
                '/ST', start_time,
                '/RI', '150',
                '/DU', '23:59',
                '/RL', 'HIGHEST',
                '/F',
            ]
            result2 = subprocess.run(create_cmd_fallback, capture_output=True, text=True)
            if result2.returncode == 0:
                ok("Task 'FarmCycle' created (fallback schedule).")
                return True
            else:
                err("Could not create scheduled task.")
                print(f"  {result2.stderr}")
                return False
    except Exception as e:
        err(f"Error: {e}")
        return False


# ──────────────────────────────────────────────────────────────
#  Reconfig Mode
# ──────────────────────────────────────────────────────────────

def reconfig_mode() -> None:
    """Just regenerate user_config.py without full setup."""
    banner("Reconfigure")

    info("This will regenerate user_config.py with your current settings.")
    info("It will NOT touch the virtual environment, dependencies, or installed apps.")
    print()

    # Re-detect paths
    info("Re-scanning for installed apps...")
    gnbots = auto_detect_gnbots()
    ldplayer, ldmulti = auto_detect_ldplayer()

    detected = {
        "gnbots_path": gnbots,
        "ldplayer_path": ldplayer,
        "ldmulti_path": ldmulti,
    }

    if gnbots:
        ok(f"Found GnBots at: {gnbots}")
    else:
        warn("GnBots not detected")

    if ldplayer:
        ok(f"Found LDPlayer at: {ldplayer}")
    else:
        warn("LDPlayer not detected")

    print()
    generate_user_config(non_interactive=False, detected_paths=detected)
    generate_user_config_example()

    # Webhook test if applicable
    if USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, 'r') as f:
                content = f.read()
            for line in content.splitlines():
                if "webhook_url" in line and "None" not in line and not line.strip().startswith("#"):
                    match = re.search(r'"(https?://[^"]+)"', line)
                    if match:
                        print()
                        test_webhook(match.group(1))
                    break
        except Exception:
            pass

    print()
    validate_setup()
    show_status_screen()


# ──────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────

def main():
    enable_ansi_colors()

    # Parse args first — we need to know if --reconfig or --check
    non_interactive = "--non-interactive" in sys.argv
    check_only = "--check" in sys.argv
    reconfig = "--reconfig" in sys.argv
    no_elevate = "--no-elevate" in sys.argv

    # ── Self-elevation (skip for --check and --non-interactive) ──
    if not no_elevate and not check_only and not non_interactive:
        if not is_admin():
            # Show welcome first so user sees something
            show_welcome()
            if self_elevate():
                # The elevated process will run; this one exits
                sys.exit(0)
            else:
                warn("Continuing without admin — some features will be limited.")
                input("\n  Press Enter to continue...")
    else:
        show_welcome()

    # Start logging (after welcome, so it doesn't get duplicated across elevation)
    setup_logging()

    if check_only:
        banner("Validation Check Only")
        validate_setup()
        show_status_screen()
        return

    if reconfig:
        reconfig_mode()
        return

    total_steps = 8

    # ── Step 1: Environment ──
    step(1, total_steps, "Checking environment")
    if not check_python_version():
        sys.exit(1)
    check_os()
    check_admin_status()

    # ── Step 2: Virtual environment ──
    step(2, total_steps, "Setting up virtual environment")
    if not create_venv():
        warn("Could not create venv. Continuing with system Python.")

    # ── Step 3: Dependencies ──
    step(3, total_steps, "Installing dependencies")
    if VENV_DIR.exists():
        install_requirements()
    else:
        print("  No venv found. Install manually:")
        print(f"    pip install -r {REQUIREMENTS_FILE}")

    # ── Step 4: Software Installation ──
    step(4, total_steps, "Installing GnBots + LDPlayer")
    detected_paths = install_software(non_interactive=non_interactive)

    # ── Step 5: Directories ──
    step(5, total_steps, "Creating directory structure")
    create_directories()

    # ── Step 6: User configuration ──
    step(6, total_steps, "Configuring your setup")
    generate_user_config(non_interactive=non_interactive, detected_paths=detected_paths)
    generate_user_config_example()

    # Webhook test if a webhook was configured
    if not non_interactive and USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, 'r') as f:
                content = f.read()
            for line in content.splitlines():
                if "webhook_url" in line and "None" not in line and not line.strip().startswith("#"):
                    match = re.search(r'"(https?://[^"]+)"', line)
                    if match:
                        print()
                        want_test = ask_yes_no("Send a test message to verify the webhook works?", default=True)
                        if want_test:
                            test_webhook(match.group(1))
                    break
        except Exception:
            pass

    # ── Step 7: Validation ──
    step(7, total_steps, "Validating setup")
    validate_setup()

    # ── Step 8: Task Scheduler ──
    step(8, total_steps, "Task Scheduler setup (optional)")
    if not non_interactive:
        setup_task_scheduler()
    else:
        info("Skipped (non-interactive mode).")
        print("  Double-click schedule.bat to set up auto-cycling.")

    # ── Final status screen ──
    show_status_screen()

    # ── Auto-Launch Capture Tool ──
    if not non_interactive and not (PROJECT_DIR / "templates" / "start_btn.png").exists():
        print()
        cprint("  [!!] Missing required templates.", Colors.YELLOW)
        want_capture = ask_yes_no("Would you like to open the template capture tool now?", default=True)
        if want_capture:
            venv_python = VENV_DIR / "Scripts" / "python.exe"
            capture_script = PROJECT_DIR / "capture_templates.py"
            if venv_python.exists() and capture_script.exists():
                info("Launching capture tool...")
                subprocess.Popen([str(venv_python), str(capture_script)])
                ok("Capture tool opened in a new window.")


if __name__ == "__main__":
    main()
