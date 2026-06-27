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
git clone https://github.com/YOUR_USERNAME/farm-bot.git
cd farm-bot/Bot_Scripts
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

### 3. Capture template images

Double-click **`capture.bat`** — this opens a GUI tool that lets you drag-select button regions from a GnBots screenshot and saves them as template PNGs.

You need at least `templates/start_btn.png`. See the [Template Capture](#template-capture) section below.

### 4. Test your setup

Double-click **`test.bat`** — runs all three diagnostic tests (capture, template matching, clicks) and shows a colored summary:

```
[OK] Python 3.12.0
[OK] Virtual environment (.venv)
[OK] user_config.py
[OK] GnBots is running
[OK] templates/start_btn.png

1. Window Capture
[OK] Window capture works
[OK] Saved: printwindow_test_20260628_143022.png

2. Template Matching
[OK] start_btn.png: 0.92 confidence

3. Click Methods
[OK] Click test ran successfully

══════════════════════════════════════════════
  ✓ ALL CHECKS PASSED — ready to farm!
══════════════════════════════════════════════
```

### 5. Run a farm cycle

Double-click **`start.bat`** — runs one complete farm cycle.

### 6. Set up auto-cycling (optional)

Double-click **`schedule.bat`** — creates a Windows Task Scheduler entry.

---

## All Launcher Scripts

| Script | What it does |
|--------|-------------|
| `setup.bat` | Run the full setup (self-elevates to admin) |
| `start.bat` | Run one farm cycle |
| `stop.bat` | Kill all bot processes (GnBots, LDPlayer, Python) |
| `test.bat` | Run all diagnostic tests with summary |
| `capture.bat` | Open template capture GUI |
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

## Template Capture

The `capture_templates.py` tool (launched via `capture.bat`) lets you create template PNGs visually:

1. Make sure GnBots is running
2. Double-click `capture.bat`
3. Choose which template to capture (start_btn, first_btn, etc.)
4. A screenshot of GnBots appears
5. **Drag a box** around the button you want
6. Preview the cropped region
7. Press `s` to save, `r` to retry, `q` to quit

The tool automatically:
- Caches the screenshot for 60 seconds (so you don't re-capture for each template)
- Backs up existing templates before overwriting
- Shows the dimensions of saved templates

### Required vs Optional Templates

| File | Required? | Description |
|------|-----------|-------------|
| `start_btn.png` | **Yes** | The Start button in GnBots |
| `first_btn.png` | Optional | The First/OK button in the dialog |
| `continue_btn.png` | Optional | Continue dialog button |
| `stop_btn.png` | Optional | Stop button (diagnostic use) |
| `completed.png` | Optional | Completion indicator (diagnostic use) |

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

### Key settings

| Setting | Default | What it does |
|---------|---------|-------------|
| `HEADLESS` | `False` | `True` = no mouse movement (PostMessage clicks) |
| `GHOST_MODE` | `False` | Makes windows invisible while bot runs (needs HEADLESS) |
| `VDD_PREFER` | `True` | Prefer virtual displays over physical monitors |
| `VERIFY_CLICK` | `False` | Screenshot verification after each click |
| `COORD_FALLBACK_ENABLED` | `True` | Fall back to coordinate clicks if templates fail |

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

### "GnBots not found at: ..."
Edit `user_config.py` and set `GNBOTS_PATH` to the correct location. Or run `reconfig.bat` to re-scan.

### Template matching fails (confidence too low)
- Re-capture your templates with `capture.bat` — drag-select a tighter region
- Run `test.bat` to see confidence scores
- Try `python click_test.py --all-methods start_btn` to find a working method

### Clicks don't register
- Make sure you're running as admin (GnBots runs elevated — UIPI blocks clicks from non-admin)
- Set `HEADLESS = False` in `user_config.py` (uses real mouse movement instead of PostMessage)
- Set coordinate fallbacks: use `click_test.py --coords X Y` to find button positions

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

# Run diagnostic tests
python test_setup.py

# Capture template images
python capture_templates.py
python capture_templates.py --refresh   # Force fresh screenshot
python capture_templates.py --list      # List current templates
```

---

## File Structure After Setup

```
Bot_Scripts/
├── .venv/                          # Python virtual environment
├── templates/                      # Template PNGs (you create these)
│   ├── start_btn.png              # REQUIRED
│   ├── first_btn.png              # optional
│   └── ...
├── screenshots/                    # Bot screenshots (auto-generated)
│   └── diffs/                     # Before/after click comparisons
├── logs/                           # Log files
│   └── FarmLog.txt                # Main bot log
├── user_config.py                  # YOUR settings (gitignored)
├── user_config.example.py          # Template for user_config.py
├── setup.log                       # Setup script log
├── config.py                       # Default config (loads user_config.py)
├── farm_cycle.py                   # Main bot entry point
├── setup_farm_bot.py               # Setup script
├── test_setup.py                   # Diagnostic test suite
├── capture_templates.py            # Template capture GUI
├── requirements.txt                # Python dependencies
├── setup.bat                       # ← Double-click to setup
├── start.bat                       # ← Double-click to run
├── stop.bat                        # ← Double-click to stop
├── test.bat                        # ← Double-click to test
├── capture.bat                     # ← Double-click to capture templates
├── schedule.bat                    # ← Double-click to schedule
└── reconfig.bat                    # ← Double-click to reconfigure
```
