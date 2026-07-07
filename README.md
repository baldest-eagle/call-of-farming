# Farm Bot — Setup Guide

## Prerequisites

- **Windows 10/11** (this bot uses pywin32 for window management)
- **Python 3.8+** ([download](https://www.python.org/downloads/))
- **Admin privileges** (the setup script will request them automatically)

> **GnBots and LDPlayer are optional at the start** — the setup script can download and install them for you.

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/baldest-eagle/call-of-farming.git
cd call-of-farming/Bot_Scripts
```

### 2. Double-click `setup.bat`

That's it. The setup script will:
- Request admin privileges via UAC (click "Yes")
- Show a welcome screen explaining what it will do
- Create a Python virtual environment
- Install all Python dependencies
- **Download and install LDPlayer 9** (if not already installed)
- **Open the GnBots download page** so you can install it (requires account)
- Auto-detect where GnBots and LDPlayer are installed
- Create the directory structure
- Generate `user_config.py` with your paths pre-filled
- If you set up Discord/Slack notifications, send a test message
- Validate everything is in place
- Offer to set up Windows Task Scheduler (with presets: every 1h/2h/3h/6h)
- Show a final status screen with ✓/✗ for each step

A log file is saved to `setup.log` — share it if you need help.


### 3. Run a farm cycle

Double-click **`start.bat`** — runs one complete farm cycle.

### 4. Set up notifications (optional)

Double-click **`notifications.bat`** — opens an interactive menu to set up Discord/Slack notifications. Includes step-by-step instructions for getting a webhook URL if you don't have one.

### 5. Set up auto-cycling (optional)

Double-click **`schedule.bat`** — creates a Windows Task Scheduler entry.

---

## All Launcher Scripts

| Script | What it does |
|--------|-------------|
| `setup.bat` | Run the full setup (self-elevates to admin) |
| `start.bat` | Run one farm cycle |
| `stop.bat` | Kill all bot processes (GnBots, LDPlayer, Python) |
| `notifications.bat` | Set up Discord/Slack notifications (with webhook instructions) |
| `schedule.bat` | Set up Task Scheduler (self-elevates to admin) |
| `reconfig.bat` | Re-run just the configuration step |

---

## Software Installation Details

### LDPlayer 9

The setup script can **automatically download and install** LDPlayer 9:
- Downloads the latest offline installer from `ldplayer.net` CDN
- Attempts a silent install first (`/S` flag)
- Falls back to the GUI installer if silent install fails
- Auto-detects the install path afterward

If you prefer to install manually:
1. Download from [ldplayer.net](https://www.ldplayer.net)
2. Run the installer
3. The setup script will find it automatically

### GnBots

GnBots **cannot be auto-downloaded** — it requires an account on their website. The setup script will:
1. Open the GnBots download page in your browser
2. Wait for you to create an account, download, and install it
3. Auto-detect the install location after you're done

If you already have GnBots:
- The setup script scans common install paths automatically
- Also searches Program Files, desktop shortcuts, and Start Menu
- You can also provide the path manually

Download page: [gnbots.com/shop/download](https://www.gnbots.com/shop/download)

---



## Configuration

### user_config.py

Your personal settings live in `user_config.py` (not tracked by git). Edit it anytime:

```python
from pathlib import Path

# Your app paths
GNBOTS_PATH = Path(r"C:\Your\Path\To\GnBots.exe")
LDPLAYER_PATH = Path(r"C:\Your\Path\To\dnplayer.exe")

# Discord/Slack notifications (optional)
NOTIFICATIONS = {
    "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
    "webhook_enabled": True,
    ...
}
```

To reconfigure without redoing the full setup:
- Double-click `reconfig.bat`, OR
- Run: `python setup_farm_bot.py --reconfig`

---

## Notifications

The Farm Bot can send notifications to Discord or Slack when farm cycles start, complete, or fail. This is ideal if you want to monitor the bot while away from your PC.

### Easy way: use `notifications.bat`

Double-click **`notifications.bat`** (or run `python notifications.py`). It opens an interactive menu:

1. **Enable webhook notifications** — walks you through getting a webhook URL with step-by-step instructions (for both Discord and Slack), then sends a test message
2. **Disable webhook notifications** — turns them off but keeps your URL saved for easy re-enabling
3. **Test current webhook** — sends a test message to verify everything works
4. **Choose which events trigger notifications** — toggle individual events on/off
5. **Toggle desktop toast notifications** — Windows 10+ pop-up notifications
6. **Show webhook setup instructions again** — if you need a refresher

This tool only touches the `NOTIFICATIONS` section of `user_config.py` — your other settings are left untouched.

### Manual way: edit `user_config.py`

Open `user_config.py` in any text editor and modify the `NOTIFICATIONS` block:

```python
NOTIFICATIONS = {
    "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK",  # paste URL here
    "webhook_enabled": True,       # True = on, False = off
    "desktop_enabled": False,      # Windows toast pop-ups
    "on_cycle_start": True,        # notify when cycle starts
    "on_cycle_complete": True,     # notify when cycle finishes
    "on_error": True,              # notify on errors
    "on_health_fail": True,        # notify on health check failures
    "on_completion_detected": True,
    "sound_file": None,            # path to .wav for sound, or None
}
```

Save the file. The next farm cycle picks up the new settings automatically.

### What is a webhook?

A webhook is a special URL that lets one app send messages to another. When the bot has something to tell you (cycle started, error occurred, etc.), it sends an HTTP POST to the webhook URL, and the message appears in your Discord/Slack channel.

The `notifications.bat` tool includes full step-by-step instructions for creating a webhook in both Discord and Slack — you don't need to know what a webhook is in advance.

### Key settings

| Setting | Default | What it does |
|---------|---------|-------------|
| `HEADLESS` | `False` | `True` = no mouse movement (PostMessage keystrokes) |
| `GHOST_MODE` | `False` | Makes windows invisible while bot runs (needs HEADLESS) |
| `VDD_PREFER` | `True` | Prefer virtual displays over physical monitors |

---

## Task Scheduler Presets

When you set up auto-cycling, you can choose:

| Preset | Interval | Use case |
|--------|----------|----------|
| 1 | Every 1 hour | Aggressive — uses trial resets often |
| 2 | Every 2 hours | Balanced |
| 3 | Every 3 hours | **Recommended** — GnBots free trial is 2 hours |
| 4 | Every 6 hours | Conservative |
| 5 | Custom | You specify the interval in minutes |

---

## Troubleshooting

### "internal error: no installs error: no runtimes are installed"
This means you have the Python launcher (`py.exe`) installed but no actual Python runtime. The launcher is a stub that finds and runs Python — without Python installed, it errors out.

**Fix:**
1. Go to https://www.python.org/downloads/
2. Download the latest Python 3.x installer
3. Run the installer
4. **Check the box that says "Add Python to PATH"** at the bottom of the installer
5. Click "Install Now"
6. Close any open Command Prompt windows, then double-click `setup.bat` again

The .bat files now detect this case automatically and show the same instructions.

### "GnBots not found at: ..."
Edit `user_config.py` and set `GNBOTS_PATH` to the correct location. Or run `reconfig.bat` to re-scan.

### LDPlayer download fails
- Your firewall or antivirus may be blocking the download
- Download manually from [ldplayer.net](https://www.ldplayer.net/versions)
- Then re-run setup — it will find the existing installation

### Webhook test fails
- Check that the URL is correct (Discord: `https://discord.com/api/webhooks/...`)
- Make sure the webhook is still active in your Discord/Slack settings
- Webhook must use HTTPS

### Virtual display not detected
- Run `python virtual_display.py` for diagnostics
- Run `python virtual_display.py --parsec` for Parsec VDD status
- Run `python virtual_display.py --coords` to see auto-detected coordinates

### Something went wrong and I don't know what
- Check `setup.log` in the project directory — it contains everything the setup script did
- Share this log when asking for help

---

## Command-Line Reference

```bash
# Full interactive setup (auto-elevates to admin)
python setup_farm_bot.py

# Just regenerate user_config.py
python setup_farm_bot.py --reconfig

# Validation only, no changes
python setup_farm_bot.py --check

# Non-interactive (use defaults, skip software install)
python setup_farm_bot.py --non-interactive

# Skip auto-elevation (run with current privileges)
python setup_farm_bot.py --no-elevate
```

---

## File Structure After Setup

```
Bot_Scripts/
├── .venv/                          # Python virtual environment
├── screenshots/                    # Bot screenshots (auto-generated)
├── logs/                           # Log files
│   └── FarmLog.txt                # Main bot log
├── user_config.py                  # YOUR settings (gitignored)
├── user_config.example.py          # Template for user_config.py
├── setup.log                       # Setup script log
├── config.py                       # Default config (loads user_config.py)
├── farm_cycle.py                   # Main bot entry point
├── setup_farm_bot.py               # Setup script
├── notifications.py                # Notification setup tool
├── requirements.txt                # Python dependencies
├── setup.bat                       # ← Double-click to setup
├── start.bat                       # ← Double-click to run
├── stop.bat                        # ← Double-click to stop
├── notifications.bat               # ← Double-click to set up notifications
├── schedule.bat                    # ← Double-click to schedule
└── reconfig.bat                    # ← Double-click to reconfigure
```
