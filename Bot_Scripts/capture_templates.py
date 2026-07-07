#!/usr/bin/env python3
"""
capture_templates.py — GUI helper for creating template PNGs.

This tool lets you drag-select button regions from a GnBots screenshot
and save them as template PNGs. Eliminates the need to manually crop
images in an image editor.

How it works:
  1. Captures the GnBots window (or takes a fresh screenshot)
  2. Opens a window showing the screenshot
  3. You drag-select the button you want as a template
  4. Preview the cropped region
  5. Save it as start_btn.png, first_btn.png, etc.

Usage:
    python capture_templates.py                # Interactive mode
    python capture_templates.py --refresh      # Capture a fresh screenshot first
    python capture_templates.py --list         # List current templates

Requirements:
    - GnBots must be running (for live capture)
    - OpenCV (cv2), numpy, Pillow (PIL) — all in requirements.txt
"""

import sys
import os
import time
import ctypes
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  DPI Awareness (must be set before any window operations)
# ──────────────────────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
#  Imports
# ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_DIR / "templates"
SCREENSHOTS_DIR = PROJECT_DIR / "screenshots"


# ──────────────────────────────────────────────────────────────
#  Template Definitions
# ──────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "name": "start_btn.png",
        "description": "The Start button in GnBots (REQUIRED)",
        "required": True,
    },
    {
        "name": "first_btn.png",
        "description": "The First/OK button in the popup dialog",
        "required": False,
    },
    {
        "name": "continue_btn.png",
        "description": "The Continue button (if a Continue dialog appears)",
        "required": False,
    },
    {
        "name": "stop_btn.png",
        "description": "The Stop button (visible when bot is running)",
        "required": False,
    },
    {
        "name": "completed.png",
        "description": "The Completed indicator (when bot finishes its run)",
        "required": False,
    },
]


# ──────────────────────────────────────────────────────────────
#  Screenshot Capture
# ──────────────────────────────────────────────────────────────

def capture_gnbots_window() -> np.ndarray:
    """Capture the GnBots window using PrintWindow (works even if obscured)."""
    import win32gui
    import win32ui
    import win32con
    from ctypes import windll

    WINDOW_TITLE = "Goodnight Bots"
    found_hwnd = None

    def callback(hwnd, _):
        nonlocal found_hwnd
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if WINDOW_TITLE in title:
                    found_hwnd = hwnd
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass

    if not found_hwnd:
        raise RuntimeError(
            "GnBots window not found. Make sure GnBots is running and visible."
        )

    rect = win32gui.GetWindowRect(found_hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]

    if w <= 0 or h <= 0:
        raise RuntimeError(f"GnBots window has invalid size: {w}x{h}")

    wDC = None
    dcObj = None
    cDC = None
    bmp = None

    try:
        wDC = win32gui.GetWindowDC(found_hwnd)
        dcObj = win32ui.CreateDCFromHandle(wDC)
        cDC = dcObj.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(dcObj, w, h)
        cDC.SelectObject(bmp)

        # PW_RENDERFULLCONTENT = 2
        windll.user32.PrintWindow(found_hwnd, cDC.GetSafeHdc(), 2)

        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
            bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4
        )
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    finally:
        try:
            if dcObj: dcObj.DeleteDC()
        except Exception: pass
        try:
            if cDC: cDC.DeleteDC()
        except Exception: pass
        try:
            if wDC and found_hwnd: win32gui.ReleaseDC(found_hwnd, wDC)
        except Exception: pass
        try:
            if bmp: win32gui.DeleteObject(bmp.GetHandle())
        except Exception: pass


def capture_full_screen() -> np.ndarray:
    """Capture the full primary screen as fallback."""
    import pyautogui
    screenshot = pyautogui.screenshot()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


# ──────────────────────────────────────────────────────────────
#  Interactive Selection (using OpenCV)
# ──────────────────────────────────────────────────────────────

class TemplateCropper:
    """Lets the user drag-select a region on a screenshot."""

    def __init__(self, image: np.ndarray, window_title: str = "Select Template Region"):
        self.image = image.copy()
        self.window_title = window_title
        self.drawing = False
        self.start_x, self.start_y = -1, -1
        self.end_x, self.end_y = -1, -1
        self.crop = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_x, self.start_y = x, y
            self.end_x, self.end_y = x, y
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.end_x, self.end_y = x, y
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_x, self.end_y = x, y
            # Ensure start < end
            x1 = min(self.start_x, self.end_x)
            y1 = min(self.start_y, self.end_y)
            x2 = max(self.start_x, self.end_x)
            y2 = max(self.start_y, self.end_y)
            if x2 - x1 > 5 and y2 - y1 > 5:  # Minimum size
                self.crop = self.image[y1:y2, x1:x2]

    def run(self) -> np.ndarray:
        """Display the image and let user select a region. Returns cropped image or None."""
        cv2.namedWindow(self.window_title, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_title, self.mouse_callback)

        print()
        print("  ─── Template Capture ───")
        print("  Drag a box around the button you want to capture.")
        print("  Then press:")
        print("    [s] = Save this region as the template")
        print("    [r] = Reset and try again")
        print("    [q] = Quit without saving")
        print()

        while True:
            display = self.image.copy()

            # Draw current selection
            if self.start_x >= 0 and self.end_x >= 0:
                x1 = min(self.start_x, self.end_x)
                y1 = min(self.start_y, self.end_y)
                x2 = max(self.start_x, self.end_x)
                y2 = max(self.start_y, self.end_y)
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw instructions on image
            h, w = display.shape[:2]
            instructions = [
                "Drag to select | s=save | r=reset | q=quit",
            ]
            for i, text in enumerate(instructions):
                cv2.putText(
                    display, text, (10, 25 + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2
                )

            cv2.imshow(self.window_title, display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s') and self.crop is not None:
                cv2.destroyAllWindows()
                return self.crop
            elif key == ord('r'):
                self.start_x, self.start_y = -1, -1
                self.end_x, self.end_y = -1, -1
                self.crop = None
                print("  Reset.")
            elif key == ord('q') or key == 27:  # q or ESC
                cv2.destroyAllWindows()
                return None

    def preview_and_confirm(self, crop: np.ndarray, template_name: str) -> bool:
        """Show a preview of the cropped template and ask for confirmation."""
        preview_title = f"Preview: {template_name} — [s]ave / [r]etry / [q]uit"
        cv2.namedWindow(preview_title, cv2.WINDOW_NORMAL)

        # Scale up small previews for visibility
        h, w = crop.shape[:2]
        scale = max(1, 200 // max(h, w) if max(h, w) > 0 else 1)
        if scale > 1:
            display = cv2.resize(crop, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
        else:
            display = crop.copy()

        # Add border
        display = cv2.copyMakeBorder(display, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(0, 255, 0))

        cv2.imshow(preview_title, display)
        print(f"  Preview shown ({w}x{h}px). Press [s] to save, [r] to retry, [q] to quit.")

        while True:
            key = cv2.waitKey(0) & 0xFF
            if key == ord('s'):
                cv2.destroyAllWindows()
                return True
            elif key == ord('r'):
                cv2.destroyAllWindows()
                return False
            elif key == ord('q') or key == 27:
                cv2.destroyAllWindows()
                return None  # Signal quit


# ──────────────────────────────────────────────────────────────
#  Template Management
# ──────────────────────────────────────────────────────────────

def list_templates() -> None:
    """List all current templates and their status."""
    print()
    print("  ─── Current Templates ───")
    print(f"  Directory: {TEMPLATES_DIR}")
    print()

    if not TEMPLATES_DIR.exists():
        print("  Templates directory does not exist yet.")
        return

    for tpl in TEMPLATES:
        path = TEMPLATES_DIR / tpl["name"]
        required = " (REQUIRED)" if tpl["required"] else ""
        if path.exists():
            size = path.stat().st_size
            # Get image dimensions
            try:
                img = cv2.imread(str(path))
                if img is not None:
                    h, w = img.shape[:2]
                    print(f"  [OK]  {tpl['name']:25s} {w}x{h}px  ({size} bytes){required}")
                else:
                    print(f"  [??]  {tpl['name']:25s} exists but cannot read{required}")
            except Exception:
                print(f"  [??]  {tpl['name']:25s} exists ({size} bytes){required}")
        else:
            status = "[!!]" if tpl["required"] else "[--]"
            print(f"  {status}  {tpl['name']:25s} MISSING{required}")
            print(f"        → {tpl['description']}")


def save_template(crop: np.ndarray, template_name: str) -> bool:
    """Save the cropped image as a template. Returns True on success."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATES_DIR / template_name

    # Backup existing template
    if path.exists():
        backup_name = f"{path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
        backup_path = TEMPLATES_DIR / backup_name
        try:
            path.rename(backup_path)
            print(f"  Backed up existing template to: {backup_name}")
        except OSError:
            pass

    success = cv2.imwrite(str(path), crop)
    if success:
        h, w = crop.shape[:2]
        print(f"  Saved: {path} ({w}x{h}px)")
        return True
    else:
        print(f"  ERROR: Failed to save {path}")
        return False


# ──────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────

def print_menu() -> None:
    print()
    print("=" * 60)
    print("  FARM BOT — Template Capture Tool")
    print("=" * 60)
    print()
    print("  This tool helps you create template PNGs for the bot.")
    print("  You'll drag-select button regions from a GnBots screenshot.")
    print()
    print("  Options:")
    print("    1. Capture start_btn.png    (REQUIRED)")
    print("    2. Capture first_btn.png    (optional)")
    print("    3. Capture continue_btn.png (optional)")
    print("    4. Capture stop_btn.png     (optional)")
    print("    5. Capture completed.png    (optional)")
    print("    6. List current templates")
    print("    7. Capture a fresh GnBots screenshot")
    print("    q. Quit")
    print()


def capture_screenshot_for_templates(force_refresh: bool = False) -> np.ndarray:
    """Get a screenshot of GnBots. Caches the last capture to avoid re-capturing."""
    cache_path = SCREENSHOTS_DIR / "_template_capture_cache.png"
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Use cached screenshot if it's less than 60 seconds old
    if not force_refresh and cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < 60:
            print(f"  Using cached screenshot (captured {int(age)}s ago)")
            img = cv2.imread(str(cache_path))
            if img is not None:
                return img

    # Try to capture GnBots window
    print("  Capturing GnBots window...")
    try:
        img = capture_gnbots_window()
        cv2.imwrite(str(cache_path), img)
        print(f"  Captured: {img.shape[1]}x{img.shape[0]}px")
        return img
    except Exception as e:
        print(f"  Could not capture GnBots window: {e}")
        print("  Falling back to full screen capture...")
        try:
            img = capture_full_screen()
            cv2.imwrite(str(cache_path), img)
            print(f"  Captured full screen: {img.shape[1]}x{img.shape[0]}px")
            return img
        except Exception as e2:
            print(f"  Full screen capture also failed: {e2}")
            print("  Make sure GnBots is running, then try again.")
            sys.exit(1)


def capture_template_flow(template_info: dict, screenshot: np.ndarray) -> None:
    """Full flow for capturing one template."""
    name = template_info["name"]
    print()
    print(f"  ─── Capturing: {name} ───")
    print(f"  {template_info['description']}")

    while True:
        cropper = TemplateCropper(screenshot, f"Select: {name}")
        crop = cropper.run()

        if crop is None:
            print("  Cancelled.")
            return

        # Preview
        result = cropper.preview_and_confirm(crop, name)
        if result is True:
            save_template(crop, name)
            return
        elif result is None:
            print("  Quit.")
            sys.exit(0)
        # If False, loop and try again


def main():
    # Parse args
    if "--list" in sys.argv:
        list_templates()
        return

    force_refresh = "--refresh" in sys.argv

    # Welcome
    print_menu()

    # Initial screenshot
    print("  Getting a screenshot of GnBots to work with...")
    print("  (Make sure GnBots is running and visible!)")
    try:
        screenshot = capture_screenshot_for_templates(force_refresh=force_refresh)
    except SystemExit:
        return

    # Interactive menu
    while True:
        print_menu()
        choice = input("  Choose an option: ").strip().lower()

        if choice == "q":
            print("  Bye!")
            return
        elif choice == "6":
            list_templates()
        elif choice == "7":
            screenshot = capture_screenshot_for_templates(force_refresh=True)
        elif choice in ("1", "2", "3", "4", "5"):
            idx = int(choice) - 1
            if idx < len(TEMPLATES):
                capture_template_flow(TEMPLATES[idx], screenshot)
            else:
                print("  Invalid choice.")
        else:
            print("  Invalid choice. Enter 1-7 or q.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled by user.")
        # Make sure all OpenCV windows are closed
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        sys.exit(0)
