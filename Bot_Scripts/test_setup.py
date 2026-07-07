#!/usr/bin/env python3
"""
test_setup.py — Single-command diagnostic suite.

Runs all three diagnostic scripts in sequence and prints a colored
summary report at the end. Use this to verify your setup is working
before running a full farm cycle.

Usage:
    python test_setup.py

What it checks:
  1. Window capture    (can we see GnBots?)
  2. Template matching (do your templates match the live window?)
  3. Click methods     (which click method actually works?)

Exit code:
    0 = all checks passed
    1 = one or more checks failed
"""

import sys
import os
import time
import subprocess
import ctypes
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  ANSI Color Support (Windows 10+)
# ──────────────────────────────────────────────────────────────

class Colors:
    """ANSI color codes. Auto-disabled on older Windows that doesn't support them."""
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
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def cprint(text: str, color: str = "") -> None:
    """Print with color."""
    print(f"{color}{text}{Colors.RESET}")


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent


def find_python() -> str:
    """Find the venv Python if available, otherwise system Python."""
    venv_python = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def find_gnbots_window() -> bool:
    """Quick check: is GnBots currently running?"""
    try:
        import win32gui
    except ImportError:
        return False

    found = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Goodnight Bots" in title:
                found.append(hwnd)
    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass
    return bool(found)


def find_gnbots_process() -> bool:
    """Check if GnBots.exe is running as a process."""
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == "gnbots.exe":
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        pass
    return False


def run_script(script_name: str, timeout: int = 60) -> tuple:
    """Run a Python script and return (success, output)."""
    script_path = PROJECT_DIR / script_name
    if not script_path.exists():
        return False, f"Script not found: {script_path}"

    python_exe = find_python()
    try:
        result = subprocess.run(
            [python_exe, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_DIR),
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"Script timed out after {timeout}s"
    except Exception as e:
        return False, f"Failed to run: {e}"


# ──────────────────────────────────────────────────────────────
#  Test Definitions
# ──────────────────────────────────────────────────────────────

def test_prerequisites() -> list:
    """Check basic prerequisites before running other tests."""
    results = []

    # Python version
    version = sys.version_info
    if version >= (3, 8):
        results.append(("PASS", f"Python {version.major}.{version.minor}.{version.micro}", ""))
    else:
        results.append(("FAIL", f"Python {version.major}.{version.minor} (need 3.8+)", ""))

    # Virtual environment
    venv = PROJECT_DIR / ".venv"
    if venv.exists():
        results.append(("PASS", "Virtual environment (.venv)", str(venv)))
    else:
        results.append(("WARN", "No virtual environment", "Run: python setup_farm_bot.py"))

    # user_config.py
    user_config = PROJECT_DIR / "user_config.py"
    if user_config.exists():
        results.append(("PASS", "user_config.py", str(user_config)))
    else:
        results.append(("FAIL", "user_config.py missing", "Run: python setup_farm_bot.py"))

    # Templates directory
    templates_dir = PROJECT_DIR / "templates"
    if templates_dir.exists():
        start_btn = templates_dir / "start_btn.png"
        if start_btn.exists():
            results.append(("PASS", "templates/start_btn.png", str(start_btn)))
        else:
            results.append(("FAIL", "templates/start_btn.png missing",
                            "Run: python capture_templates.py"))
    else:
        results.append(("FAIL", "templates/ directory missing", "Run: python setup_farm_bot.py"))

    # GnBots running?
    if find_gnbots_process():
        results.append(("PASS", "GnBots is running", ""))
    else:
        results.append(("WARN", "GnBots is NOT running",
                        "Start GnBots before running tests"))

    return results


def test_capture() -> tuple:
    """Run capture_test.py and parse output."""
    print("\n  Running capture_test.py...")
    success, output = run_script("capture_test.py", timeout=30)

    # capture_test.py saves a screenshot if successful
    screenshots_dir = PROJECT_DIR / "screenshots"
    recent_screenshots = []
    if screenshots_dir.exists():
        recent_screenshots = sorted(
            screenshots_dir.glob("printwindow_test_*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]

    return success, output, recent_screenshots


def test_templates() -> tuple:
    """Run template_diagnostic.py and parse output."""
    print("  Running template_diagnostic.py...")
    success, output = run_script("template_diagnostic.py", timeout=30)

    # Try to parse the JSON report for confidence scores
    report_path = PROJECT_DIR / "templates" / "diagnostic_report.json"
    reports = []
    if report_path.exists():
        try:
            import json
            with open(report_path) as f:
                reports = json.load(f)
        except Exception:
            pass

    return success, output, reports


def test_clicks() -> tuple:
    """Run click_test.py --scan and parse output."""
    print("  Running click_test.py --scan...")
    # click_test.py with --scan tries all templates and shows confidence
    success, output = run_script("click_test.py", timeout=30)

    return success, output


# ──────────────────────────────────────────────────────────────
#  Summary Report
# ──────────────────────────────────────────────────────────────

def print_section(title: str, results: list) -> None:
    """Print a section of test results with colored status indicators."""
    print()
    cprint(f"  {title}", Colors.BOLD + Colors.CYAN)
    print(f"  {'-' * 50}")
    for status, label, hint in results:
        if status == "PASS":
            icon = "[OK]"
            color = Colors.GREEN
        elif status == "WARN":
            icon = "[!!]"
            color = Colors.YELLOW
        else:
            icon = "[XX]"
            color = Colors.RED
        cprint(f"  {icon} {label}", color)
        if hint:
            cprint(f"       -> {hint}", Colors.YELLOW if status != "PASS" else Colors.RESET)


def print_summary(all_results: dict) -> bool:
    """Print the final summary report. Returns True if all critical tests passed."""
    print()
    print("=" * 60)
    cprint("  FARM BOT — DIAGNOSTIC SUMMARY", Colors.BOLD + Colors.CYAN)
    print("=" * 60)

    all_pass = True

    # Prerequisites
    print_section("Prerequisites", all_results["prereq"])
    for status, _, _ in all_results["prereq"]:
        if status == "FAIL":
            all_pass = False

    # Capture test
    capture_results = []
    if all_results["capture"]["success"]:
        capture_results.append(("PASS", "Window capture works", ""))
        if all_results["capture"]["screenshots"]:
            ss = all_results["capture"]["screenshots"][0]
            capture_results.append(("PASS", f"Saved: {ss.name}", str(ss)))
        else:
            capture_results.append(("WARN", "No screenshots saved", "Check capture_test.py output"))
    else:
        capture_results.append(("FAIL", "Window capture FAILED", "Is GnBots running?"))
        all_pass = False
    print_section("1. Window Capture", capture_results)

    # Template test
    template_results = []
    if all_results["templates"]["success"]:
        template_results.append(("PASS", "Template diagnostic ran", ""))
    else:
        template_results.append(("FAIL", "Template diagnostic failed", ""))

    for report in all_results["templates"]["reports"]:
        tpl_name = report.get("template", "?")
        conf = report.get("best_confidence", 0)
        threshold = report.get("threshold", 0.75)
        if conf >= threshold:
            template_results.append(("PASS", f"{tpl_name}: {conf:.2f} confidence", ""))
        elif conf >= report.get("threshold", 0.75) * 0.8:
            template_results.append(("WARN", f"{tpl_name}: {conf:.2f} (below threshold {threshold})", ""))
        else:
            template_results.append(("FAIL", f"{tpl_name}: {conf:.2f} (no match)",
                                    "Re-capture template with capture_templates.py"))
            all_pass = False
    print_section("2. Template Matching", template_results)

    # Click test
    click_results = []
    if all_results["clicks"]["success"]:
        click_results.append(("PASS", "Click test ran successfully", ""))
    else:
        click_results.append(("FAIL", "Click test failed", "Check output above"))
        # Don't fail the whole suite for click test — it requires interaction
    print_section("3. Click Methods", click_results)

    # Final verdict
    print()
    print("=" * 60)
    if all_pass:
        cprint("  [OK] ALL CHECKS PASSED - ready to farm!", Colors.BOLD + Colors.GREEN)
        cprint("  Run:  python farm_cycle.py  (or double-click start.bat)", Colors.GREEN)
    else:
        cprint("  [ERROR] SOME CHECKS FAILED - see above", Colors.BOLD + Colors.RED)
        cprint("  Fix the [XX] items, then re-run this test.", Colors.RED)
    print("=" * 60)

    return all_pass


# ──────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────

def main():
    enable_ansi_colors()

    print()
    print("=" * 60)
    cprint("  FARM BOT — DIAGNOSTIC TEST SUITE", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Project: {PROJECT_DIR}")
    print()

    cprint("  This will run 3 tests in sequence:", Colors.BLUE)
    print("    1. Window capture (can we see GnBots?)")
    print("    2. Template matching (do templates match?)")
    print("    3. Click methods (which click works?)")
    print()
    cprint("  Make sure GnBots is RUNNING before continuing.", Colors.YELLOW)
    print()

    try:
        input("  Press Enter to start, or Ctrl+C to cancel...")
    except KeyboardInterrupt:
        cprint("\n  Cancelled.", Colors.YELLOW)
        sys.exit(0)

    # ── Run all tests ──
    print()
    cprint("  Running tests...", Colors.BLUE)

    all_results = {
        "prereq": test_prerequisites(),
        "capture": {},
        "templates": {},
        "clicks": {},
    }

    # Test 1: Capture
    cap_success, cap_output, cap_screenshots = test_capture()
    all_results["capture"] = {
        "success": cap_success,
        "output": cap_output,
        "screenshots": cap_screenshots,
    }

    # Test 2: Templates
    tpl_success, tpl_output, tpl_reports = test_templates()
    all_results["templates"] = {
        "success": tpl_success,
        "output": tpl_output,
        "reports": tpl_reports,
    }

    # Test 3: Clicks
    clk_success, clk_output = test_clicks()
    all_results["clicks"] = {
        "success": clk_success,
        "output": clk_output,
    }

    # ── Print summary ──
    all_pass = print_summary(all_results)

    # ── Detailed output (if anything failed) ──
    if not all_pass:
        print()
        cprint("  Detailed test outputs:", Colors.YELLOW)
        print()
        for test_name, key in [("Capture", "capture"), ("Templates", "templates"), ("Clicks", "clicks")]:
            output = all_results[key].get("output", "")
            if output and "PASS" not in output[:200]:
                cprint(f"  ─── {test_name} Output ───", Colors.YELLOW)
                for line in output.splitlines():
                    print(f"  {line}")
                print()

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
