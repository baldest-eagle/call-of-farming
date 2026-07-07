#!/usr/bin/env python3
"""
notifications.py — Focused tool for toggling Discord/Slack notifications.

Use this anytime you want to:
  - Turn notifications ON (set up a webhook)
  - Turn notifications OFF
  - Test that your current webhook works
  - Change which events trigger notifications

Usage:
    python notifications.py

This tool only touches the NOTIFICATIONS section of user_config.py.
It won't change your GnBots path, LDPlayer path, or any other settings.
"""

import sys
import os
import re
import json
import ctypes
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  ANSI Colors
# ──────────────────────────────────────────────────────────────

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def enable_ansi():
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def cprint(text: str = "", color: str = "", end: str = "\n"):
    print(f"{color}{text}{Colors.RESET}", end=end)


def ok(msg): cprint(f"  [OK] {msg}", Colors.GREEN)
def warn(msg): cprint(f"  [!!] {msg}", Colors.YELLOW)
def err(msg): cprint(f"  [XX] {msg}", Colors.RED)
def info(msg): cprint(f"  {msg}", Colors.BLUE)
def heading(msg): cprint(f"\n  {msg}", Colors.BOLD + Colors.CYAN)


# ──────────────────────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent
USER_CONFIG_FILE = PROJECT_DIR / "user_config.py"


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

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


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


# ──────────────────────────────────────────────────────────────
#  Webhook Instructions
# ──────────────────────────────────────────────────────────────

def show_webhook_instructions() -> None:
    """Show step-by-step instructions for getting a webhook URL."""
    clear_screen()
    print()
    print("=" * 60)
    cprint("  What is a webhook?", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print()
    print("  A webhook is a special URL that lets one app send")
    print("  messages to another app. In this case, the Farm Bot")
    print("  uses a webhook to send notifications to your Discord")
    print("  or Slack channel.")
    print()
    print("  When the bot starts a farm cycle, finishes a cycle,")
    print("  or hits an error, it sends a message to the webhook")
    print("  URL — and you see it appear in your channel.")
    print()
    print("  The URL looks like this:")
    cprint("  https://discord.com/api/webhooks/1234567890/abcDEF...", Colors.DIM)
    print()
    print("=" * 60)
    cprint("  How to get a Discord webhook URL", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print()
    print("  1. Open Discord (the desktop app or discord.com)")
    print()
    print("  2. Go to the server where you want notifications")
    print("     (you must have 'Manage Webhooks' permission)")
    print()
    print("  3. Pick a channel for the bot messages")
    print("     - You can use an existing channel")
    print("     - Or create a new one: right-click the channel list")
    print("       → Create Channel → name it 'farm-bot' → Create")
    print()
    print("  4. Click the gear icon next to the channel name")
    print("     (Channel Settings)")
    print()
    print("  5. Click 'Integrations' in the left sidebar")
    print()
    print("  6. Click 'Webhooks'")
    print()
    print("  7. Click the blue 'New Webhook' button")
    print()
    print("  8. A new webhook appears — click it to edit:")
    print("     - Name it 'FarmBot' (or anything you like)")
    print("     - Optionally upload an icon image")
    print("     - Pick which channel it posts to")
    print()
    print("  9. Click the blue 'Copy Webhook URL' button")
    print()
    print("  10. Paste it below when prompted.")
    print()
    print("=" * 60)
    cprint("  How to get a Slack webhook URL", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print()
    print("  1. Go to https://api.slack.com/messaging/webhooks")
    print()
    print("  2. Click 'Create your Slack app'")
    print()
    print("  3. Name it (e.g., 'FarmBot'), pick your workspace")
    print()
    print("  4. Under 'Incoming Webhooks', toggle 'On'")
    print()
    print("  5. Click 'Add New Webhook to Workspace'")
    print()
    print("  6. Pick a channel and click 'Allow'")
    print()
    print("  7. Copy the webhook URL and paste it below.")
    print()
    print("=" * 60)
    input("  Press Enter when you have your webhook URL ready...")
    clear_screen()


# ──────────────────────────────────────────────────────────────
#  Webhook Testing
# ──────────────────────────────────────────────────────────────

def test_webhook(webhook_url: str) -> bool:
    """Send a test message to verify the webhook works."""
    if not webhook_url:
        return False

    info("Sending test message to webhook...")
    print(f"  URL: {webhook_url[:60]}...")

    # Detect Discord vs Slack/other
    is_discord = "discord.com" in webhook_url or "discordapp.com" in webhook_url

    if is_discord:
        payload = {
            "embeds": [{
                "title": "FarmBot: Test Notification",
                "description": (
                    "If you can see this, your webhook is configured correctly!\n\n"
                    "You'll receive notifications when:\n"
                    "• Farm cycles start\n"
                    "• Farm cycles complete\n"
                    "• Errors occur"
                ),
                "color": 0x00FF00,
                "footer": {"text": f"Test sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
            }]
        }
    else:
        # Slack/generic format
        payload = {
            "text": (
                f"*FarmBot: Test Notification*\n"
                f"If you can see this, your webhook is configured correctly!\n\n"
                f"You'll receive notifications when farm cycles start, complete, or fail.\n"
                f"_{datetime.now()}_"
            )
        }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                ok("Test message sent! Check your Discord/Slack channel.")
                return True
            else:
                warn(f"Webhook returned status {resp.status}")
                return False
    except urllib.error.HTTPError as e:
        err(f"Webhook test failed (HTTP {e.code}): {e.reason}")
        if e.code == 401:
            print("  The webhook URL is invalid or has been revoked.")
        elif e.code == 404:
            print("  The webhook URL is incorrect — check for typos.")
        elif e.code == 429:
            print("  Rate limited — wait a minute and try again.")
        return False
    except urllib.error.URLError as e:
        err(f"Webhook test failed: {e}")
        print("  Check that:")
        print("    - The URL starts with https://")
        print("    - You're connected to the internet")
        print("    - Your firewall isn't blocking outgoing HTTPS")
        return False
    except Exception as e:
        err(f"Webhook test failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────
#  user_config.py Parsing & Updating
# ──────────────────────────────────────────────────────────────

def read_current_config() -> dict:
    """Read the NOTIFICATIONS section from user_config.py.
    
    Returns a dict with keys: webhook_url, webhook_enabled, desktop_enabled,
    on_cycle_start, on_cycle_complete, on_error, on_health_fail,
    on_completion_detected, sound_file
    """
    if not USER_CONFIG_FILE.exists():
        return {}

    try:
        content = USER_CONFIG_FILE.read_text(encoding='utf-8')
    except Exception:
        return {}

    # Execute the file in a sandbox and grab the NOTIFICATIONS dict
    sandbox = {}
    try:
        exec(compile(content, str(USER_CONFIG_FILE), 'exec'), sandbox)
        return sandbox.get("NOTIFICATIONS", {})
    except Exception:
        # If the file has a syntax error, fall back to regex parsing
        pass

    # Regex fallback
    config = {}
    # Look for the NOTIFICATIONS = { ... } block
    match = re.search(
        r'NOTIFICATIONS\s*=\s*\{([^}]+)\}',
        content,
        re.DOTALL,
    )
    if not match:
        return config

    block = match.group(1)
    # Extract key-value pairs
    pairs = re.findall(r'"(\w+)"\s*:\s*([^,\n]+)', block)
    for key, value in pairs:
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            config[key] = value[1:-1]
        elif value.lower() in ("true", "false"):
            config[key] = value.lower() == "true"
        elif value.lower() == "none":
            config[key] = None
        else:
            config[key] = value

    return config


def show_current_config(config: dict) -> None:
    """Display the current notification settings."""
    heading("Current Notification Settings")
    print()

    if not config:
        warn("No notification settings found yet.")
        print("  (user_config.py may not exist or has no NOTIFICATIONS section)")
        return

    webhook_url = config.get("webhook_url")
    webhook_enabled = config.get("webhook_enabled", False)
    desktop_enabled = config.get("desktop_enabled", False)

    # Webhook status
    if webhook_enabled and webhook_url:
        ok(f"Webhook notifications: ON")
        # Show truncated URL for privacy
        if len(webhook_url) > 50:
            display_url = webhook_url[:30] + "..." + webhook_url[-15:]
        else:
            display_url = webhook_url
        print(f"    URL: {display_url}")
    elif webhook_enabled and not webhook_url:
        warn("Webhook notifications: enabled but NO URL set (won't work)")
    else:
        info("Webhook notifications: OFF")

    # Desktop toast
    if desktop_enabled:
        ok("Desktop toast: ON")
    else:
        info("Desktop toast: OFF")

    # Event types
    print()
    info("Events that trigger notifications:")
    events = [
        ("on_cycle_start", "Cycle starts"),
        ("on_cycle_complete", "Cycle completes"),
        ("on_error", "Errors occur"),
        ("on_health_fail", "Health check fails"),
        ("on_completion_detected", "Completion detected"),
    ]
    for key, label in events:
        enabled = config.get(key, False)
        status = "[x]" if enabled else "[ ]"
        color = Colors.GREEN if enabled else Colors.DIM
        cprint(f"    {status} {label}", color)


def write_config(config: dict) -> bool:
    """Write the NOTIFICATIONS section back to user_config.py.
    
    If user_config.py exists, we replace just the NOTIFICATIONS block.
    If not, we create a new file with just the NOTIFICATIONS section.
    """
    webhook_url = config.get("webhook_url")
    webhook_url_repr = repr(webhook_url) if webhook_url else "None"

    notifications_block = f'''NOTIFICATIONS = {{
    "webhook_url": {webhook_url_repr},
    "webhook_enabled": {config.get("webhook_enabled", False)},
    "desktop_enabled": {config.get("desktop_enabled", False)},
    "on_cycle_start": {config.get("on_cycle_start", True)},
    "on_cycle_complete": {config.get("on_cycle_complete", True)},
    "on_error": {config.get("on_error", True)},
    "on_health_fail": {config.get("on_health_fail", True)},
    "on_completion_detected": {config.get("on_completion_detected", True)},
    "sound_file": None,
}}'''

    if USER_CONFIG_FILE.exists():
        try:
            content = USER_CONFIG_FILE.read_text(encoding='utf-8')
        except Exception as e:
            err(f"Could not read user_config.py: {e}")
            return False

        # Replace existing NOTIFICATIONS block
        # Match: NOTIFICATIONS = { ... } (with possible nested braces handled by DOTALL)
        pattern = r'NOTIFICATIONS\s*=\s*\{[^}]*\}'
        if re.search(pattern, content, re.DOTALL):
            new_content = re.sub(pattern, notifications_block, content, count=1, flags=re.DOTALL)
        else:
            # No NOTIFICATIONS block found — append it
            new_content = content.rstrip() + "\n\n" + notifications_block + "\n"
    else:
        # Create new file
        new_content = f'''"""
user_config.py — Your personal Farm Bot configuration.

This file overrides the defaults in config.py. It is NOT tracked by git,
so your paths and webhook URLs stay private.

Generated by notifications.py on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
"""

from pathlib import Path

# ── Application Paths ─────────────────────────────────────
# (Run setup_farm_bot.py to configure your paths here automatically)

# ── Notifications ─────────────────────────────────────────
{notifications_block}
'''

    try:
        USER_CONFIG_FILE.write_text(new_content, encoding='utf-8')
        ok(f"Updated: {USER_CONFIG_FILE}")
        return True
    except OSError as e:
        err(f"Failed to write user_config.py: {e}")
        return False


# ──────────────────────────────────────────────────────────────
#  Menus
# ──────────────────────────────────────────────────────────────

def menu_enable_webhook() -> None:
    """Walk through enabling webhook notifications."""
    clear_screen()
    heading("Enable Webhook Notifications")
    print()

    # Check if user knows what a webhook is
    know_webhook = ask_yes_no(
        "Do you know what a webhook is / have a webhook URL ready?",
        default=False,
    )

    if not know_webhook:
        show_webhook_instructions()

    # Get webhook URL
    print()
    info("Paste your webhook URL below.")
    print("  (It should look like: https://discord.com/api/webhooks/...)")
    print("  (Or for Slack:        https://hooks.slack.com/services/...)")
    print()
    webhook_url = ask("Webhook URL", "").strip()

    if not webhook_url:
        warn("No URL entered — cancelling.")
        return

    # Basic validation
    if not webhook_url.startswith("https://"):
        err("URL must start with https://")
        print("  Discord and Slack both require HTTPS. Double-check the URL.")
        return

    if not any(domain in webhook_url for domain in ["discord.com", "discordapp.com", "slack.com", "hooks.slack.com"]):
        warn("This doesn't look like a Discord or Slack webhook URL.")
        print("  It might still work if it's a custom webhook, but most users want Discord/Slack.")
        proceed = ask_yes_no("Continue anyway?", default=False)
        if not proceed:
            return

    # Test it
    print()
    test_now = ask_yes_no("Send a test message to verify it works?", default=True)
    if test_now:
        success = test_webhook(webhook_url)
        if not success:
            print()
            retry = ask_yes_no("Test failed. Save the URL anyway?", default=False)
            if not retry:
                return

    # Choose which events trigger notifications
    print()
    heading("Choose which events trigger notifications")
    print("  (All are recommended ON — you can turn individual ones off later)")
    print()

    events = {
        "on_cycle_start": ("Cycle starts", True),
        "on_cycle_complete": ("Cycle completes", True),
        "on_error": ("Errors occur", True),
        "on_health_fail": ("Health check fails", True),
        "on_completion_detected": ("Completion detected", True),
    }

    config = {
        "webhook_url": webhook_url,
        "webhook_enabled": True,
        "desktop_enabled": False,  # Don't touch desktop setting
    }

    for key, (label, default_on) in events.items():
        config[key] = ask_yes_no(f"  Notify when {label}?", default=default_on)

    # Save
    print()
    save = ask_yes_no("Save these settings?", default=True)
    if not save:
        info("Cancelled — no changes made.")
        return

    # Merge with existing config to preserve desktop_enabled etc.
    existing = read_current_config()
    if existing:
        for key in ["desktop_enabled", "sound_file"]:
            if key in existing and key not in config:
                config[key] = existing[key]

    if write_config(config):
        ok("Notifications are now ON!")
        print()
        info("The next farm cycle will send notifications to your channel.")
        print()
        info("To turn them off later, run this script again and choose 'Turn off'.")


def menu_disable_webhook() -> None:
    """Turn off webhook notifications."""
    heading("Disable Webhook Notifications")
    print()

    confirm = ask_yes_no("Turn off webhook notifications?", default=False)
    if not confirm:
        info("Cancelled — no changes made.")
        return

    config = read_current_config()
    config["webhook_enabled"] = False
    # Keep the URL so they can re-enable easily

    if write_config(config):
        ok("Webhook notifications are now OFF.")
        print()
        info("Your webhook URL has been kept in user_config.py")
        info("so you can re-enable easily by running this script again.")


def menu_test_webhook() -> None:
    """Send a test message using the current config."""
    heading("Test Current Webhook")
    print()

    config = read_current_config()
    webhook_url = config.get("webhook_url")

    if not webhook_url:
        warn("No webhook URL is configured.")
        print("  Enable notifications first (option 1).")
        return

    if not config.get("webhook_enabled", False):
        warn("Webhook is currently disabled in your config.")
        proceed = ask_yes_no("Send a test anyway?", default=True)
        if not proceed:
            return

    test_webhook(webhook_url)


def menu_choose_events() -> None:
    """Let the user toggle individual event types."""
    heading("Choose Which Events Trigger Notifications")
    print()

    config = read_current_config()
    if not config.get("webhook_url"):
        warn("No webhook URL is configured.")
        print("  Enable notifications first (option 1).")
        return

    events = [
        ("on_cycle_start", "Cycle starts"),
        ("on_cycle_complete", "Cycle completes"),
        ("on_error", "Errors occur"),
        ("on_health_fail", "Health check fails"),
        ("on_completion_detected", "Completion detected"),
    ]

    print("  Toggle each event on/off:")
    print()
    for key, label in events:
        current = config.get(key, False)
        new_value = ask_yes_no(f"  {label}?", default=current)
        config[key] = new_value

    print()
    if write_config(config):
        ok("Event settings updated.")


def menu_desktop_toasts() -> None:
    """Toggle Windows desktop toast notifications."""
    heading("Desktop Toast Notifications")
    print()
    print("  Desktop toasts are pop-up notifications that appear in")
    print("  the bottom-right corner of your screen (Windows 10+).")
    print("  They only show up when you're at the PC — use webhooks")
    print("  if you want notifications while away.")
    print()

    config = read_current_config()
    current = config.get("desktop_enabled", False)

    if current:
        info("Desktop toasts are currently: ON")
        turn_off = ask_yes_no("Turn them off?", default=False)
        if turn_off:
            config["desktop_enabled"] = False
            write_config(config)
            ok("Desktop toasts are now OFF.")
    else:
        info("Desktop toasts are currently: OFF")
        turn_on = ask_yes_no("Turn them on?", default=True)
        if turn_on:
            config["desktop_enabled"] = True
            write_config(config)
            ok("Desktop toasts are now ON.")


# ──────────────────────────────────────────────────────────────
#  Main Menu
# ──────────────────────────────────────────────────────────────

def main_menu() -> None:
    """Show the main menu loop."""
    while True:
        clear_screen()
        print()
        print("=" * 60)
        cprint("  Farm Bot — Notification Settings", Colors.BOLD + Colors.CYAN)
        print("=" * 60)
        print()

        # Show current status
        config = read_current_config()
        show_current_config(config)

        print()
        print("=" * 60)
        cprint("  What would you like to do?", Colors.BOLD)
        print("=" * 60)
        print()
        print("    1. Enable webhook notifications (Discord/Slack)")
        print("    2. Disable webhook notifications")
        print("    3. Test current webhook (send a test message)")
        print("    4. Choose which events trigger notifications")
        print("    5. Toggle desktop toast notifications")
        print("    6. Show webhook setup instructions again")
        print("    q. Quit")
        print()
        choice = input("  Choose an option: ").strip().lower()

        if choice == "1":
            menu_enable_webhook()
            input("\n  Press Enter to return to the menu...")
        elif choice == "2":
            menu_disable_webhook()
            input("\n  Press Enter to return to the menu...")
        elif choice == "3":
            menu_test_webhook()
            input("\n  Press Enter to return to the menu...")
        elif choice == "4":
            menu_choose_events()
            input("\n  Press Enter to return to the menu...")
        elif choice == "5":
            menu_desktop_toasts()
            input("\n  Press Enter to return to the menu...")
        elif choice == "6":
            show_webhook_instructions()
            input("\n  Press Enter to return to the menu...")
        elif choice == "q":
            print()
            info("Goodbye!")
            return
        else:
            warn("Invalid choice. Enter 1-6 or q.")
            input("\n  Press Enter to continue...")


def main():
    enable_ansi()

    # Welcome
    print()
    print("=" * 60)
    cprint("  Farm Bot — Notification Setup", Colors.BOLD + Colors.CYAN)
    print("=" * 60)
    print()
    print("  This tool helps you configure Discord/Slack notifications")
    print("  for your Farm Bot. You can:")
    print()
    print("    • Turn notifications on or off")
    print("    • Set up a webhook (with step-by-step instructions)")
    print("    • Test that your webhook works")
    print("    • Choose which events trigger notifications")
    print("    • Toggle Windows desktop pop-up notifications")
    print()
    print("  This only changes notification settings — your GnBots")
    print("  and LDPlayer paths are left untouched.")
    print()
    input("  Press Enter to continue...")

    main_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        cprint("\n  Cancelled by user.", Colors.YELLOW)
        sys.exit(0)
