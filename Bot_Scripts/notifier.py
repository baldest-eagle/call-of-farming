"""
notifier.py — Remote and local notification system.
Supports Discord/Slack webhooks (ideal when away from PC) and desktop toasts.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime

from config import NOTIFICATIONS

logger = logging.getLogger("FarmBot.Notifier")


def send(event: str, message: str = "") -> None:
    """Send a notification through all enabled channels."""
    # Check if this event type should be notified
    event_key = f"on_{event}"
    if not NOTIFICATIONS.get(event_key, False):
        return

    title = f"FarmBot: {event.replace('_', ' ').title()}"
    body = message or event
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ── Webhook (Discord / Slack / custom) ──
    if NOTIFICATIONS.get("webhook_enabled") and NOTIFICATIONS.get("webhook_url"):
        _send_webhook(title, body, timestamp)

    # ── Desktop toast ──
    if NOTIFICATIONS.get("desktop_enabled"):
        _send_desktop_toast(title, body)


def _send_webhook(title: str, body: str, timestamp: str) -> bool:
    """Send a Discord-style webhook notification."""
    url = NOTIFICATIONS["webhook_url"]
    if not url:
        return False

    # Detect Discord vs Slack by URL
    if "discord.com" in url or "discordapp.com" in url:
        payload = {
            "embeds": [{
                "title": title,
                "description": body,
                "color": _event_color(title),
                "footer": {"text": timestamp},
            }]
        }
    else:
        # Generic/Slack format
        payload = {
            "text": f"**{title}**\n{body}\n_{timestamp}_",
        }

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 300:
                logger.debug(f"Webhook sent: {title}")
                return True
            else:
                logger.warning(f"Webhook returned status {resp.status}")
                return False
    except Exception as e:
        logger.warning(f"Webhook failed: {e}")
        return False


def _event_color(title: str) -> int:
    """Return a Discord embed color based on event type."""
    title_lower = title.lower()
    if "error" in title_lower or "fail" in title_lower or "health" in title_lower:
        return 0xFF0000   # Red
    elif "complete" in title_lower or "detected" in title_lower:
        return 0x00FF00   # Green
    elif "start" in title_lower:
        return 0x0099FF   # Blue
    return 0xFFAA00       # Orange (default)


def _send_desktop_toast(title: str, body: str) -> bool:
    """Send a Windows desktop toast notification."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, body, duration=5, threaded=True)
        return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Toast notification failed: {e}")

    # Fallback: beep
    try:
        import winsound
        winsound.Beep(1000, 300)
    except Exception:
        pass
    return False
