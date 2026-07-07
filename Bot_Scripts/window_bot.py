"""
window_bot.py — Window management, screenshot capture, and template-based clicking.
Uses pywin32 for window control and OpenCV for template matching.

Key improvements over v2:
  - Dual capture: pyautogui (primary) + PrintWindow (fallback for obscured windows)
  - Screenshot differencing: before/after every click to verify it landed
  - Multi-scale template matching with configurable fallback threshold
  - Robust click: PostMessage/SendMessage as fallback when pyautogui misses
"""

import time
import logging
from pathlib import Path
from typing import Optional, Tuple, List

from PIL import Image
import pyautogui
import win32gui
import win32con
import win32ui
from ctypes import windll

from config import (
    SCREENSHOT_DIR,
    DIFF_THRESHOLD,
    DIFF_SAVE_ALL,
    DIFF_DIR,
    COORD_FALLBACK_ENABLED,
    COORD_FALLBACKS,
    HEADLESS,
)

logger = logging.getLogger("FarmBot.WindowBot")

# Global PyAutoGUI safety settings
pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = False


class WindowBot:
    """Manages a target window: finding, moving, capturing, and clicking via template matching.

    In HEADLESS mode (config.HEADLESS=True):
      - Uses PrintWindow for captures (no foreground needed)
      - Uses PostMessage for clicks (no mouse movement)
      - Skips bring_to_front() so you can use your PC
    In normal mode:
      - Uses pyautogui for captures and clicks (mouse moves)
      - PostMessage sent as backup
      - Brings window to front before clicks
    """

    def __init__(
        self,
        window_title: str,
        headless: Optional[bool] = None,
    ):
        self.window_title = window_title
        self.headless = headless if headless is not None else HEADLESS
        self._hwnd: Optional[int] = None
        self._template_cache: dict = {}
        self._screenshot_dir = Path(SCREENSHOT_DIR)
        self._diff_dir = Path(DIFF_DIR)

    # ── Window Finding & Management ──────────────────────────────

    def find_window(self, timeout: int = 30) -> bool:
        """Search for the window by partial title match. Returns True if found."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            hwnd = self._find_window_partial(self.window_title)
            if hwnd:
                self._hwnd = hwnd
                actual_title = win32gui.GetWindowText(hwnd)
                logger.info(f"Found window: '{actual_title}' (HWND: {hwnd})")
                return True
            logger.debug("Window not found yet, retrying in 0.5s...")
            time.sleep(0.5)
        logger.error(f"Window containing '{self.window_title}' not found after {timeout}s")
        return False

    def _find_window_partial(self, partial_title: str) -> Optional[int]:
        """Enumerate windows looking for a partial title match (case-insensitive).
        
        If multiple windows match, prefers the one that looks like a main
        application window (largest, with a title bar) over tooltips, 
        shadows, or dialogs.
        """
        results = []
        search = partial_title.lower()

        def callback(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if search in title.lower():
                        # Gather info to rank candidates
                        try:
                            rect = win32gui.GetWindowRect(hwnd)
                            area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                            classname = win32gui.GetClassName(hwnd)
                        except Exception:
                            area = 0
                            classname = ""
                        # Skip tooltip and shadow windows — they're not the main window
                        if any(cls in classname.lower() for cls in ["tooltip", "shadow", "broadcast"]):
                            return True
                        results.append((hwnd, area, title))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass

        if not results:
            return None

        # Return the largest window (most likely the main app window)
        results.sort(key=lambda r: r[1], reverse=True)
        return results[0][0]

    @property
    def hwnd(self) -> int:
        """Get the window handle, raising if invalid."""
        if not self._hwnd or not win32gui.IsWindow(self._hwnd):
            raise RuntimeError("Window handle invalid. Call find_window() first.")
        return self._hwnd

    @property
    def window_title_actual(self) -> str:
        """Get the actual window title text."""
        return win32gui.GetWindowText(self.hwnd)

    def move_to_monitor(self, x: int, y: int) -> bool:
        """Move the window to the given screen coordinates. Returns False on access denied."""
        hwnd = self.hwnd
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.5)
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            logger.info(f"Moved window to ({x}, {y}) size {width}x{height}")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(
                f"Could not move window (likely privilege mismatch): {e}. "
                f"Continuing without moving."
            )
            return False

    # ── Ghost Mode (Window Transparency) ─────────────────────────

    def make_transparent(self, alpha: int = 0) -> bool:
        """Make the window transparent using SetLayeredWindowAttributes.
        
        Alpha values:
            0   = fully invisible
            1   = nearly invisible (faint outline, for debugging)
            255 = fully opaque (restores normal visibility)
        
        Returns True on success, False on failure.
        Requires admin privileges for elevated windows.
        """
        hwnd = self.hwnd
        try:
            import ctypes
            
            # Get current window style
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            
            if alpha < 255:
                # Add WS_EX_LAYERED flag
                new_style = style | 0x80000  # WS_EX_LAYERED
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, new_style)
                
                # Set transparency: LWA_ALPHA = 0x02
                result = ctypes.windll.user32.SetLayeredWindowAttributes(
                    hwnd, 0, alpha, 0x02
                )
                if result:
                    visibility = "invisible" if alpha == 0 else f"alpha={alpha}"
                    logger.info(f"Ghost Mode: Window '{win32gui.GetWindowText(hwnd)}' is now {visibility}")
                    return True
                else:
                    logger.error(f"SetLayeredWindowAttributes failed (error: {ctypes.GetLastError()})")
                    return False
            else:
                # Remove WS_EX_LAYERED flag to restore normal window
                new_style = style & ~0x80000
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, new_style)
                logger.info(f"Ghost Mode: Window '{win32gui.GetWindowText(hwnd)}' restored to opaque")
                return True
                
        except Exception as e:
            logger.error(f"Ghost Mode failed: {e}")
            return False

    def make_opaque(self) -> bool:
        """Restore the window to full visibility. Convenience wrapper for make_transparent(255)."""
        return self.make_transparent(255)

    def bring_to_front(self) -> bool:
        """Attempt to bring the window to the foreground. Returns True on success."""
        hwnd = self.hwnd
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
            
            # Alt key trick to bypass Windows SetForegroundWindow restriction
            import ctypes
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0) # Alt Down
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0) # Alt Up
            
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.warning(f"SetForegroundWindow failed: {e}")
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.BringWindowToTop(hwnd)
                time.sleep(0.3)
                
                # As additional fallback, click the title bar to focus (using Win32 to support negative coordinates)
                rect = win32gui.GetWindowRect(hwnd)
                fx = rect[0] + 100
                fy = rect[1] + 15
                ctypes.windll.user32.SetCursorPos(fx, fy)
                time.sleep(0.1)
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                time.sleep(0.05)
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
                time.sleep(0.2)
                
                return True
            except Exception as e2:
                logger.error(f"Fallback focus also failed: {e2}")
                return False

    def get_window_rect(self) -> Tuple[int, int, int, int]:
        """Return (left, top, right, bottom) of the window."""
        return win32gui.GetWindowRect(self.hwnd)

    # ── Screenshot Capture ───────────────────────────────────────

    def capture_window_region(self) -> Optional[Image.Image]:
        """
        Capture a screenshot of the window region.

        In HEADLESS mode: uses PrintWindow first (works even if window is
        obscured or not foreground), falls back to pyautogui.
        In normal mode: uses pyautogui first (what's on screen), falls back
        to PrintWindow if the capture looks blank.

        Returns Pillow Image.
        """
        if self.headless:
            # Headless: PrintWindow first (no foreground needed)
            img_pw = self._capture_printwindow()
            if img_pw is not None:
                return img_pw
            img = self._capture_pyautogui()
            if img is not None:
                return img
            logger.error("All capture methods failed.")
            return None

        # Normal: pyautogui first, PrintWindow fallback
        img = self._capture_pyautogui()
        if img is not None:
            return img

        # Fallback to PrintWindow (can capture even if window is partially hidden)
        img_pw = self._capture_printwindow()
        if img_pw is not None:
            return img_pw

        logger.error("All capture methods failed.")
        return None

    def _capture_pyautogui(self) -> Optional[Image.Image]:
        """Capture via pyautogui — requires window to be visible on screen.
        
        Note: On high-DPI displays, win32gui returns physical (unscaled) pixel
        coordinates while pyautogui may use logical (DPI-scaled) coordinates.
        We detect and correct for this mismatch by comparing the screenshot
        dimensions to the reported window rect dimensions.
        """
        try:
            rect = self.get_window_rect()
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                logger.error(f"Invalid window dimensions: {width}x{height}")
                return None
            screenshot = pyautogui.screenshot(region=(left, top, width, height))

            # DPI mismatch detection: if pyautogui returns a screenshot that is
            # smaller than the physical window size, the coordinates are likely
            # in logical (scaled) pixels. Scale the capture region accordingly.
            if screenshot.height < height * 0.8 or screenshot.width < width * 0.8:
                scale_x = screenshot.width / width if width > 0 else 1.0
                scale_y = screenshot.height / height if height > 0 else 1.0
                logger.debug(
                    f"DPI mismatch detected: window={width}x{height}, "
                    f"capture={screenshot.width}x{screenshot.height}, "
                    f"scale=({scale_x:.2f}, {scale_y:.2f}). "
                    f"Recapturing with scaled coordinates..."
                )
                scaled_left = int(left * scale_x)
                scaled_top = int(top * scale_y)
                scaled_width = int(width * scale_x)
                scaled_height = int(height * scale_y)
                screenshot = pyautogui.screenshot(
                    region=(scaled_left, scaled_top, scaled_width, scaled_height)
                )

            logger.debug(f"pyautogui capture: {width}x{height} at ({left},{top})")
            return screenshot
        except Exception as e:
            logger.error(f"pyautogui capture failed: {e}")
            return None

    def _capture_printwindow(self) -> Optional[Image.Image]:
        """Capture via PrintWindow Win32 API — works even if window is obscured."""
        hwnd = self.hwnd
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if w <= 0 or h <= 0:
            return None

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

            # PW_RENDERFULLCONTENT = 2
            windll.user32.PrintWindow(hwnd, cDC.GetSafeHdc(), 2)

            bmpinfo = bmp.GetInfo()
            bmpstr = bmp.GetBitmapBits(True)
            
            # Load directly into Pillow
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            logger.debug(f"PrintWindow capture: {w}x{h}")
            return img
        except Exception as e:
            logger.debug(f"PrintWindow capture failed: {e}")
            return None
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



    def _win32_sendinput_click(self, x: int, y: int) -> None:
        """Simulate a mouse click using Windows SendInput API, supporting negative monitor coordinates."""
        import ctypes
        from ctypes import wintypes
        
        # 1. Move cursor to physical coordinate (works on all monitors)
        ctypes.windll.user32.SetCursorPos(x, y)
        time.sleep(0.1)

        # 2. Define SendInput structures
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("u", INPUT_UNION),
            ]

        extra = ctypes.pointer(wintypes.ULONG(0))
        
        # MOUSEEVENTF_LEFTDOWN = 0x0002
        click_down = INPUT()
        click_down.type = 0
        click_down.u.mi = MOUSEINPUT(0, 0, 0, 0x0002, 0, extra)
        
        # MOUSEEVENTF_LEFTUP = 0x0004
        click_up = INPUT()
        click_up.type = 0
        click_up.u.mi = MOUSEINPUT(0, 0, 0, 0x0004, 0, extra)
        
        # Send inputs
        ctypes.windll.user32.SendInput(1, ctypes.byref(click_down), ctypes.sizeof(INPUT))
        time.sleep(0.05)
        ctypes.windll.user32.SendInput(1, ctypes.byref(click_up), ctypes.sizeof(INPUT))

    def _do_click(self, x: int, y: int, force_pyautogui: bool = False) -> bool:
        """
        Click at the given coordinates.

        In HEADLESS mode:
          Primary: PostMessage WM_LBUTTONDOWN/UP with window-local coords.
          No mouse movement, no foreground needed. Falls back to Win32 click
          if PostMessage seems to fail, or if force_pyautogui is True
          (set after a failed verification retry).

        In normal mode:
          Primary: Win32 click (moves the mouse, supports all monitors).
          Backup: PostMessage sent as belt-and-suspenders.

        Safety: BlockInput is used to prevent the user from accidentally
        moving the mouse during a click. A safety thread ensures BlockInput
        is released after a maximum of 2 seconds even if the process crashes.
        """
        if self.headless and not force_pyautogui:
            # ── HEADLESS: PostMessage first (no mouse movement) ──
            post_ok = self._postmessage_click(x, y)
            if post_ok:
                logger.debug(f"Headless click via PostMessage at screen ({x}, {y})")
                return True

            # PostMessage threw an error — fall back to Win32 click (will move mouse)
            logger.warning("PostMessage click failed in headless mode, falling back to Win32 click (will move mouse)")
            try:
                self._safe_block_input(True)
                try:
                    self._win32_sendinput_click(x, y)
                    logger.debug(f"Fallback Win32 click({x}, {y})")
                finally:
                    self._safe_block_input(False)
                return True
            except Exception as e:
                logger.error(f"Fallback Win32 click also failed: {e}")
                self._safe_block_input(False)
                return False

        if self.headless and force_pyautogui:
            # PostMessage click didn't register (screen didn't change) — use Win32 click
            logger.info("PostMessage click not verified — retrying with Win32 click (mouse will move)")
            try:
                self._safe_block_input(True)
                try:
                    self._win32_sendinput_click(x, y)
                    logger.debug(f"Force-Win32 click({x}, {y})")
                finally:
                    self._safe_block_input(False)
                return True
            except Exception as e:
                logger.error(f"Win32 click failed: {e}")
                self._safe_block_input(False)
                return False

        # ── NORMAL: Win32 click first (moves mouse), PostMessage backup ──
        try:
            self._safe_block_input(True)
            try:
                self._win32_sendinput_click(x, y)
                logger.debug(f"Win32 SendInput click({x}, {y})")
            except Exception as e2:
                logger.warning(f"Win32 click failed: {e2}")
            finally:
                self._safe_block_input(False)
        except Exception as e:
            logger.warning(f"Win32 BlockInput failed: {e}")
            # Still unblock just in case
            self._safe_block_input(False)

        # Also send PostMessage as backup
        self._postmessage_click(x, y)
        return True

    def _safe_block_input(self, block: bool) -> None:
        """Block/unblock user input with a safety timeout.
        
        If block=True, starts a background thread that will automatically
        unblock input after 2 seconds, in case the process crashes or
        gets stuck while input is blocked.
        """
        import ctypes
        import threading

        if block:
            ctypes.windll.user32.BlockInput(True)
            # Safety net: auto-unblock after 2 seconds no matter what
            def _safety_unblock():
                time.sleep(2.0)
                try:
                    ctypes.windll.user32.BlockInput(False)
                except Exception:
                    pass
            t = threading.Thread(target=_safety_unblock, daemon=True)
            t.start()
        else:
            try:
                ctypes.windll.user32.BlockInput(False)
            except Exception:
                pass

    def _postmessage_click(self, screen_x: int, screen_y: int) -> bool:
        """
        Send WM_LBUTTONDOWN/UP via PostMessage using window-local coordinates.
        No mouse movement required — the click goes directly to the window.
        Must be running as admin (UIPI) for this to work on elevated windows.
        Returns True on success, False on failure.
        """
        try:
            hwnd = self.hwnd
            
            # Translate screen coordinates to client-area coordinates using Win32 ScreenToClient API
            import ctypes
            from ctypes import wintypes
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            
            pt = POINT(screen_x, screen_y)
            ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(pt))
            local_x = pt.x
            local_y = pt.y
            
            # Pack coordinates into lParam as signed 16-bit values.
            # struct.pack('hh', ...) correctly handles two's-complement for
            # negative coordinates (e.g. windows on a secondary monitor to the left).
            import struct as _struct
            lParam = _struct.unpack('L', _struct.pack('hh', local_x, local_y))[0]
            
            # Send WM_MOUSEMOVE to trigger hover states first, then click
            windll.user32.PostMessageW(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
            time.sleep(0.05)
            windll.user32.PostMessageW(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
            time.sleep(0.05)
            windll.user32.PostMessageW(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
            logger.debug(f"PostMessage click at window-local ({local_x}, {local_y})")
            return True
        except Exception as e:
            logger.debug(f"PostMessage click failed: {e}")
            return False

    def click_at(self, x: int, y: int, description: str = "") -> None:
        """Click at absolute screen coordinates."""
        self._do_click(x, y)
        label = description or f"({x}, {y})"
        logger.info(f"Clicked at {label}")

    # ── Debug / Diagnostics ──────────────────────────────────────

    def save_capture(self, filename: str, save_dir: Optional[str] = None) -> bool:
        """Save a screenshot of the window to disk. Returns True on success."""
        screenshot = self.capture_window_region()
        if screenshot is not None:
            save_path = Path(save_dir) / filename if save_dir else Path(filename)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(str(save_path))
            logger.info(f"Debug capture saved: {save_path}")
            return True
        return False
