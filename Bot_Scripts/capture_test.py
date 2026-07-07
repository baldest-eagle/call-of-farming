"""
capture_test.py — Quick diagnostic to test PrintWindow capture from GnBots.
Run with: python capture_test.py
Make sure GnBots is open first.
"""

import sys
import ctypes
from pathlib import Path

# Initialize DPI Awareness so coordinates match physical screen pixels.
# Must be done before any window-related imports or operations.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import win32gui
import win32ui
import win32con
import cv2
import numpy as np
from ctypes import windll

# ── Config ──────────────────────────────────────────────────────
WINDOW_TITLE = "Goodnight Bots"
SAVE_DIR = Path(__file__).resolve().parent / "screenshots"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def find_gnbots_window() -> int:
    """Find the GnBots window by partial title match."""
    results = []

    def callback(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if WINDOW_TITLE in title:
                    results.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass
    return results[0] if results else None


def capture_printwindow(hwnd: int) -> np.ndarray:
    """Capture a window using PrintWindow (works even if window is partially obscured)."""
    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]

    wDC = None
    dcObj = None
    cDC = None
    bmp = None

    try:
        wDC = win32gui.GetWindowDC(hwnd)
        dcObj = win32ui.CreateDCFromHandle(wDC)
        cDC = dcObj.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(dcObj, w, h)
        cDC.SelectObject(bmp)

        # PW_RENDERFULLCONTENT = 2 — captures even hardware-accelerated content
        windll.user32.PrintWindow(hwnd, cDC.GetSafeHdc(), 2)

        # Convert to numpy
        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype=np.uint8).reshape(
            bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4
        )
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    finally:
        # Always clean up GDI resources to prevent leaks
        try:
            if dcObj:
                dcObj.DeleteDC()
        except Exception:
            pass
        try:
            if cDC:
                cDC.DeleteDC()
        except Exception:
            pass
        try:
            if wDC and hwnd:
                win32gui.ReleaseDC(hwnd, wDC)
        except Exception:
            pass
        try:
            if bmp:
                win32gui.DeleteObject(bmp.GetHandle())
        except Exception:
            pass


def main():
    print("Looking for GnBots window...")
    hwnd = find_gnbots_window()

    if not hwnd:
        print("ERROR: GnBots window not found! Make sure it's open.")
        sys.exit(1)

    title = win32gui.GetWindowText(hwnd)
    print(f"Found: '{title}' (HWND: {hwnd})")

    rect = win32gui.GetWindowRect(hwnd)
    w = rect[2] - rect[0]
    h = rect[3] - rect[1]
    print(f"Window size: {w}x{h}")

    print("Capturing with PrintWindow...")
    img = capture_printwindow(hwnd)

    timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = SAVE_DIR / f"printwindow_test_{timestamp}.png"
    cv2.imwrite(str(save_path), img)
    print(f"Saved to: {save_path}")
    print("Done! Open that image and compare it to your snipping tool captures.")


if __name__ == "__main__":
    main()
