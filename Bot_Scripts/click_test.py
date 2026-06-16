"""
click_test.py — Interactive click testing tool for GnBots window.
Use this to debug and fine-tune your clicking strategy without running a full farm cycle.

Usage:
    python click_test.py                        # Full interactive menu
    python click_test.py --template start_btn   # Test clicking a specific template
    python click_test.py --coords 500 300       # Test clicking specific coordinates
    python click_test.py --scan                 # Scan all templates and show confidence
    python click_test.py --all-methods          # Try ALL click methods on a template
    python click_test.py --deep                 # Enumerate child windows & try deep clicks
    python click_test.py --diff                 # Capture before/after diff for a click
    python click_test.py --spy                  # Window spy: click anywhere to see what's under cursor
"""

import sys
import time
import ctypes
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    TEMPLATE_DIR,
    SCREENSHOT_DIR,
    GNBOTS_TITLE,
    TEMPLATE_START,
    TEMPLATE_FIRST,
    TEMPLATE_CONTINUE,
    TEMPLATE_STOP,
    TEMPLATE_MATCH_THRESHOLD,
    TEMPLATE_FALLBACK_THRESHOLD,
    DIFF_DIR,
    MONITOR2_X,
    MONITOR2_Y,
    AUTO_ELEVATE,
)
from window_bot import WindowBot


def _ensure_admin():
    """Auto-elevate to admin if needed. GnBots runs as admin, so we must too."""
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False

    if is_admin:
        print("Running as admin — clicks will work.")
        return

    if not AUTO_ELEVATE:
        print("=" * 60)
        print("  WARNING: Not running as admin!")
        print("  GnBots runs as admin, and Windows blocks clicks from")
        print("  non-admin processes to admin windows (UIPI).")
        print("  All clicks will hover but NOT register.")
        print("")
        print("  Fix: Run from an admin Command Prompt, or set")
        print("  AUTO_ELEVATE = True in config.py")
        print("=" * 60)
        response = input("\n  Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            sys.exit(0)
        return

    print("Not running as admin — requesting elevation (UAC prompt)...")
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join([f'"{a}"' for a in sys.argv]),
            None, 1,
        )
        sys.exit(0)  # Original non-admin process exits here
    except Exception as e:
        print(f"Elevation failed: {e}")
        print("Please run from an admin Command Prompt instead.")
        sys.exit(1)


def setup_bot() -> WindowBot:
    """Create and initialize a WindowBot instance."""
    bot = WindowBot(
        window_title=GNBOTS_TITLE,
        template_dir=TEMPLATE_DIR,
    )
    if not bot.find_window(timeout=10):
        print("ERROR: GnBots window not found! Make sure it's running.")
        sys.exit(1)

    title = bot.window_title_actual
    rect = bot.get_window_rect()
    print(f"Found window: '{title}'")
    print(f"Position: ({rect[0]}, {rect[1]}) to ({rect[2]}, {rect[3]})")
    print(f"Size: {rect[2]-rect[0]}x{rect[3]-rect[1]}")
    return bot


def cmd_scan(bot: WindowBot):
    """Scan all templates against the current window and show confidence scores."""
    print("\n" + "=" * 60)
    print("  TEMPLATE CONFIDENCE SCAN")
    print("=" * 60)

    template_dir = Path(TEMPLATE_DIR)
    templates = sorted([f.name for f in template_dir.glob("*.png")])

    if not templates:
        print(f"No template images found in {TEMPLATE_DIR}")
        print("Make sure your .png files are in the templates/ folder.")
        return

    screenshot = bot.capture_window_region()
    if screenshot is None:
        print("ERROR: Could not capture the window.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = Path(SCREENSHOT_DIR)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    capture_path = screenshot_dir / f"{ts}_scan_capture.png"
    import cv2
    cv2.imwrite(str(capture_path), screenshot)
    print(f"Window capture saved: {capture_path}\n")

    for tpl in templates:
        report = bot.get_template_confidence_report(tpl)

        if "error" in report:
            print(f"  {tpl:30s}  ERROR: {report['error']}")
            continue

        conf = report.get("best_confidence", 0)
        above_primary = report.get("above_threshold", False)
        above_fallback = report.get("above_fallback", False)
        location = report.get("best_location", "?")
        tpl_size = report.get("template_size", "?")
        ss_size = report.get("screenshot_size", "?")

        if above_primary:
            status = "PASS"
        elif above_fallback:
            status = "FALLBACK"
        else:
            status = "FAIL"

        print(
            f"  {tpl:30s}  conf={conf:.3f}  loc={location}  "
            f"size={tpl_size}  win={ss_size}  [{status}]"
        )

    print()


def cmd_template_click(bot: WindowBot, template_name: str):
    """Find and click a specific template, showing detailed diagnostics."""
    print(f"\n{'=' * 60}")
    print(f"  CLICK TEST: {template_name}")
    print(f"{'=' * 60}")

    if not template_name.endswith('.png'):
        template_name += '.png'

    report = bot.get_template_confidence_report(template_name)
    print(f"\nConfidence Report:")
    for key, val in report.items():
        print(f"  {key}: {val}")

    if report.get("error"):
        print(f"\nCannot proceed — {report['error']}")
        return

    if not report.get("above_fallback", False):
        print(f"\nConfidence ({report.get('best_confidence', 0):.3f}) is below fallback threshold.")
        print("The template doesn't match the current window state.")
        print("\nPossible reasons:")
        print("  - The button isn't visible right now (wrong UI state)")
        print("  - The template image was captured at a different DPI/scale")
        print("  - GnBots updated its UI")
        print("\nTry running 'python template_diagnostic.py --live' to watch in real-time.")
        return

    print(f"\nAttempting click with verification...")
    result = bot.find_and_click(
        template_name,
        click_delay=1.0,
        retries=2,
        retry_delay=3.0,
        verify_click=True,
    )

    if result:
        print("Click SUCCEEDED (screen changed after click)")
    else:
        print("Click FAILED (screen did not change, or template not found)")
        print("\nTip: The click may have landed but the screen change is subtle.")
        print("Check the diff images in:", DIFF_DIR)


def cmd_coords_click(bot: WindowBot, x: int, y: int):
    """Click at specific screen coordinates and verify."""
    print(f"\n{'=' * 60}")
    print(f"  COORDINATE CLICK TEST: ({x}, {y})")
    print(f"{'=' * 60}")

    rect = bot.get_window_rect()
    local_x = x - rect[0]
    local_y = y - rect[1]
    print(f"Screen coords: ({x}, {y})")
    print(f"Window-local coords: ({local_x}, {local_y})")

    before = bot.capture_window_region()
    if before is not None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_dir = Path(SCREENSHOT_DIR)
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        import cv2
        cv2.imwrite(str(screenshot_dir / f"{ts}_coords_before.png"), before)

    print("\nClicking...")
    bot._do_click(x, y)
    time.sleep(1.0)

    after = bot.capture_window_region()
    if after is not None:
        import cv2
        cv2.imwrite(str(screenshot_dir / f"{ts}_coords_after.png"), after)

    if before is not None and after is not None:
        diff_result = bot._compute_diff(before, after, "coords_click")
        print(f"\nDiff result: mean={diff_result['mean_diff']:.1f}, max={diff_result['max_diff']:.1f}")
        if diff_result['changed']:
            print("Screen CHANGED — click had an effect!")
        else:
            print("Screen did NOT change — click may have missed or landed on a non-interactive area.")
            bot._save_diff_diagnostic(before, after, f"{ts}_coords_DIFF.png")


def cmd_all_methods(bot: WindowBot, template_name: str):
    """Try every available click method on a template, one at a time."""
    if not template_name.endswith('.png'):
        template_name += '.png'

    print(f"\n{'=' * 60}")
    print(f"  ALL METHODS TEST: {template_name}")
    print(f"{'=' * 60}")

    report = bot.get_template_confidence_report(template_name)
    if report.get("error") or not report.get("above_fallback", False):
        print(f"Template confidence too low ({report.get('best_confidence', 0):.3f}).")
        print("Cannot test click methods — button not visible.")
        return

    conf = report.get("best_confidence", 0)
    location = report.get("best_location", "?")
    print(f"Template found: confidence={conf:.3f}, location={location}")

    try:
        loc_str = location.strip("()")
        cx_local, cy_local = [int(v.strip()) for v in loc_str.split(",")]
    except Exception:
        print("Could not parse template location.")
        return

    rect = bot.get_window_rect()
    screen_x = rect[0] + cx_local
    screen_y = rect[1] + cy_local
    local_x = cx_local
    local_y = cy_local

    import cv2

    methods = [
        ("1. pyautogui.click only", lambda: _click_pyautogui_only(screen_x, screen_y)),
        ("2. PostMessage WM_LBUTTONDOWN/UP to MAIN window", lambda: _click_postmessage_only(bot, screen_x, screen_y)),
        ("3. SendMessage WM_LBUTTONDOWN/UP to MAIN window", lambda: _click_sendmessage(bot, screen_x, screen_y)),
        ("4. pyautogui.moveTo + click", lambda: _click_pyautogui_move_then_click(screen_x, screen_y)),
        ("5. ctypes mouse_event", lambda: _click_mouse_event(screen_x, screen_y)),
        ("6. ctypes SendInput (modern input injection)", lambda: _click_sendinput(screen_x, screen_y)),
        ("7. double-click via mouse_event", lambda: _click_doubleclick(screen_x, screen_y)),
        ("8. pyautogui press-and-hold (human-like)", lambda: _click_press_hold(screen_x, screen_y)),
    ]

    for method_name, method_func in methods:
        print(f"\n--- {method_name} ---")

        before = bot.capture_window_region()
        if before is None:
            print("  Could not capture before screenshot — skipping.")
            continue

        try:
            method_func()
        except Exception as e:
            print(f"  Method failed with error: {e}")
            continue

        time.sleep(1.0)

        after = bot.capture_window_region()
        if after is None:
            print("  Could not capture after screenshot.")
            continue

        diff_result = bot._compute_diff(before, after, method_name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = method_name.replace(" ", "_").replace(".", "").replace("+", "").replace("(", "").replace(")", "")

        if diff_result['changed']:
            print(f"  RESULT: CHANGED (diff={diff_result['mean_diff']:.1f}) — THIS METHOD WORKS!")
            bot._save_diff_diagnostic(before, after, f"{ts}_{safe_name}_SUCCESS.png")
        else:
            print(f"  RESULT: No change (diff={diff_result['mean_diff']:.1f}) — method didn't work.")
            bot._save_diff_diagnostic(before, after, f"{ts}_{safe_name}_NOCHANGE.png")

        print("  Waiting 3 seconds before next method...")
        time.sleep(3.0)

    print("\n" + "=" * 60)
    print("  Test complete. Check diff images in:", DIFF_DIR)
    print("=" * 60)


# ── Standard Click Methods ────────────────────────────────────

def _click_pyautogui_only(x, y):
    """Click using only pyautogui."""
    import pyautogui
    pyautogui.click(x, y)


def _click_postmessage_only(bot, screen_x, screen_y):
    """Click using only PostMessage WM_LBUTTONDOWN/UP to the main window."""
    import win32con
    from ctypes import windll
    rect = bot.get_window_rect()
    local_x = screen_x - rect[0]
    local_y = screen_y - rect[1]
    lParam = (local_y << 16) | (local_x & 0xFFFF)
    windll.user32.PostMessageW(bot.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
    time.sleep(0.05)
    windll.user32.PostMessageW(bot.hwnd, win32con.WM_LBUTTONUP, 0, lParam)


def _click_sendmessage(bot, screen_x, screen_y):
    """Click using SendMessage (synchronous, waits for processing)."""
    import win32con
    from ctypes import windll
    rect = bot.get_window_rect()
    local_x = screen_x - rect[0]
    local_y = screen_y - rect[1]
    lParam = (local_y << 16) | (local_x & 0xFFFF)
    windll.user32.SendMessageW(bot.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
    time.sleep(0.05)
    windll.user32.SendMessageW(bot.hwnd, win32con.WM_LBUTTONUP, 0, lParam)


def _click_pyautogui_move_then_click(x, y):
    """Move to position first, then click (more realistic mouse behavior)."""
    import pyautogui
    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.1)
    pyautogui.click()


def _click_mouse_event(x, y):
    """Click using ctypes mouse_event (low-level input simulation)."""
    import ctypes
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.1)
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP


def _click_sendinput(x, y):
    """Click using SendInput — the modern, most compatible input injection API."""
    import ctypes
    from ctypes import wintypes

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _fields_ = [
            ("type", wintypes.DWORD),
            ("_input", _INPUT),
        ]

    # Move cursor first
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.1)

    # Get screen dimensions for absolute coordinates
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1
    screen_w = ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN)

    # Convert to absolute coordinates (0-65535 range)
    abs_x = int(x * 65535 / screen_w)
    abs_y = int(y * 65535 / screen_h)

    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    extra = ctypes.pointer(wintypes.ULONG(0))

    # Move to absolute position
    move_input = INPUT()
    move_input.type = 0  # INPUT_MOUSE
    move_input._input.mi.dx = abs_x
    move_input._input.mi.dy = abs_y
    move_input._input.mi.mouseData = 0
    move_input._input.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
    move_input._input.mi.time = 0
    move_input._input.mi.dwExtraInfo = extra
    ctypes.windll.user32.SendInput(1, ctypes.byref(move_input), ctypes.sizeof(INPUT))
    time.sleep(0.05)

    # Click down
    down_input = INPUT()
    down_input.type = 0
    down_input._input.mi.dx = abs_x
    down_input._input.mi.dy = abs_y
    down_input._input.mi.mouseData = 0
    down_input._input.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN
    down_input._input.mi.time = 0
    down_input._input.mi.dwExtraInfo = extra
    ctypes.windll.user32.SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
    time.sleep(0.1)

    # Click up
    up_input = INPUT()
    up_input.type = 0
    up_input._input.mi.dx = abs_x
    up_input._input.mi.dy = abs_y
    up_input._input.mi.mouseData = 0
    up_input._input.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP
    up_input._input.mi.time = 0
    up_input._input.mi.dwExtraInfo = extra
    ctypes.windll.user32.SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))


def _click_doubleclick(x, y):
    """Double-click using mouse_event — some apps only respond to double-click."""
    import ctypes
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.1)
    # First click
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
    time.sleep(0.05)
    # Second click
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP


def _click_press_hold(x, y):
    """Press and hold like a human — longer press duration."""
    import pyautogui
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(0.1)
    pyautogui.mouseDown(button='left')
    time.sleep(0.15)  # Hold longer than instant click
    pyautogui.mouseUp(button='left')


# ── Deep Click: Child Window + Button Methods ─────────────────

def cmd_deep(bot: WindowBot):
    """
    Enumerate all child windows/controls in the GnBots window.
    Then try to click buttons using child-window-aware methods:
      - Find the child control at the button location
      - Send WM_LBUTTONDOWN/UP directly to that child
      - Send BM_CLICK to Button-class child controls
      - Use UI Automation (if pywinauto is installed)
    """
    import win32gui
    import win32con

    print(f"\n{'=' * 60}")
    print(f"  DEEP CLICK ANALYSIS: GnBots Window Hierarchy")
    print(f"{'=' * 60}")

    hwnd = bot.hwnd

    # ── Enumerate the entire window tree ──
    print(f"\nMain window: HWND={hwnd}, Class='{win32gui.GetClassName(hwnd)}'")
    print(f"Title: '{win32gui.GetWindowText(hwnd)}'")
    rect = win32gui.GetWindowRect(hwnd)
    print(f"Rect: {rect}")

    children = []

    def enum_callback(child_hwnd, _):
        cls = win32gui.GetClassName(child_hwnd)
        text = win32gui.GetWindowText(child_hwnd)
        child_rect = win32gui.GetWindowRect(child_hwnd)
        # Convert to parent-relative coords
        local_rect = (
            child_rect[0] - rect[0],
            child_rect[1] - rect[1],
            child_rect[2] - rect[0],
            child_rect[3] - rect[1],
        )
        visible = win32gui.IsWindowVisible(child_hwnd)
        enabled = win32gui.IsWindowEnabled(child_hwnd)

        indent = "  "
        # Find depth by walking parent chain
        depth = 0
        parent = win32gui.GetParent(child_hwnd)
        while parent and parent != hwnd:
            depth += 1
            parent = win32gui.GetParent(parent)

        prefix = indent * (depth + 1)
        vis_str = "VISIBLE" if visible else "hidden"
        en_str = "enabled" if enabled else "DISABLED"

        children.append({
            "hwnd": child_hwnd,
            "class": cls,
            "text": text,
            "rect": child_rect,
            "local_rect": local_rect,
            "visible": visible,
            "enabled": enabled,
            "depth": depth,
        })

        print(
            f"{prefix}HWND={child_hwnd}  Class='{cls}'  "
            f"Text='{text}'  LocalRect={local_rect}  {vis_str} {en_str}"
        )

    print("\nEnumerating child windows...\n")
    try:
        win32gui.EnumChildWindows(hwnd, enum_callback, None)
    except Exception as e:
        print(f"Enumeration error: {e}")

    if not children:
        print("\nNo child windows found! The entire UI is in the main window.")
        print("This likely means GnBots uses a custom rendering framework.")
        print("Trying alternative deep-click approaches...\n")
        _try_deep_clicks_no_children(bot)
        return

    print(f"\nFound {len(children)} child window(s).")

    # ── Look for button-like controls ──
    button_classes = ["Button", "button", "BUTTON", "QPushButton", "TPushButton",
                      "Chrome_Widget", "Chrome_RenderWidgetHostHWND", "WindowsForms10",
                      "Static", "SysLink", "TButton", "TBitBtn"]

    button_candidates = []
    for child in children:
        cls_lower = child["class"].lower()
        is_button = (
            "button" in cls_lower or
            "push" in cls_lower or
            cls_lower in [c.lower() for c in button_classes] or
            child["text"].strip() != ""  # Any child with text might be clickable
        )
        if is_button and child["visible"]:
            button_candidates.append(child)

    if button_candidates:
        print(f"\n{len(button_candidates)} clickable-looking child control(s):")
        for i, child in enumerate(button_candidates):
            print(
                f"  [{i}] HWND={child['hwnd']}  Class='{child['class']}'  "
                f"Text='{child['text']}'  Rect={child['local_rect']}"
            )

    # ── Try deep click methods ──
    print(f"\n{'=' * 60}")
    print(f"  DEEP CLICK METHODS")
    print(f"{'=' * 60}")

    # Get template position if available
    target_local_x, target_local_y = _get_template_position(bot)

    if target_local_x is not None:
        # Find which child window is at the button location
        print(f"\nButton is at local position: ({target_local_x}, {target_local_y})")
        child_at_point = win32gui.ChildWindowFromPoint(hwnd, (target_local_x, target_local_y))
        print(f"ChildWindowFromPoint returns: HWND={child_at_point}")

        if child_at_point and child_at_point != hwnd:
            child_class = win32gui.GetClassName(child_at_point)
            child_text = win32gui.GetWindowText(child_at_point)
            print(f"  Class: '{child_class}', Text: '{child_text}'")

            # Check if this child is in our list
            for child in children:
                if child["hwnd"] == child_at_point:
                    print(f"  This is a known child control ^")
                    break

            import cv2

            # Method A: PostMessage to the CHILD window
            print(f"\n--- Deep Method A: PostMessage to child HWND={child_at_point} ---")
            before = bot.capture_window_region()
            lParam = (target_local_y << 16) | (target_local_x & 0xFFFF)
            from ctypes import windll
            windll.user32.PostMessageW(child_at_point, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
            time.sleep(0.05)
            windll.user32.PostMessageW(child_at_point, win32con.WM_LBUTTONUP, 0, lParam)
            time.sleep(1.0)
            after = bot.capture_window_region()
            _report_diff(bot, before, after, "DeepA_PostMessage_to_child")

            # Method B: BM_CLICK if it's a button
            if "button" in child_class.lower():
                print(f"\n--- Deep Method B: BM_CLICK to button HWND={child_at_point} ---")
                before = bot.capture_window_region()
                win32gui.SendMessage(child_at_point, win32con.BM_CLICK, 0, 0)
                time.sleep(1.0)
                after = bot.capture_window_region()
                _report_diff(bot, before, after, "DeepB_BM_CLICK")

            # Method C: WM_COMMAND to parent (for standard Win32 buttons)
            print(f"\n--- Deep Method C: WM_COMMAND to main window ---")
            before = bot.capture_window_region()
            # Get control ID
            ctrl_id = win32gui.GetDlgCtrlID(child_at_point)
            print(f"  Control ID: {ctrl_id}")
            if ctrl_id:
                win32gui.PostMessage(hwnd, win32con.WM_COMMAND, ctrl_id, child_at_point)
                time.sleep(1.0)
                after = bot.capture_window_region()
                _report_diff(bot, before, after, "DeepC_WM_COMMAND")
            else:
                print("  No control ID — skipping WM_COMMAND.")

            # Method D: Real click with SetForegroundWindow first
            print(f"\n--- Deep Method D: SetForegroundWindow + SendInput ---")
            before = bot.capture_window_region()
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
            except Exception:
                pass
            screen_x = rect[0] + target_local_x
            screen_y = rect[1] + target_local_y
            _click_sendinput(screen_x, screen_y)
            time.sleep(1.0)
            after = bot.capture_window_region()
            _report_diff(bot, before, after, "DeepD_Foreground_plus_SendInput")

            # Method E: ChildWindowFromPointEx (deeper search)
            print(f"\n--- Deep Method E: WindowFromPoint + PostMessage ---")
            before = bot.capture_window_region()
            point_x = rect[0] + target_local_x
            point_y = rect[1] + target_local_y
            deep_child = win32gui.WindowFromPoint((point_x, point_y))
            if deep_child:
                deep_class = win32gui.GetClassName(deep_child)
                print(f"  WindowFromPoint: HWND={deep_child}, Class='{deep_class}'")
                deep_local_x = target_local_x
                deep_local_y = target_local_y
                # Adjust coords to deep child's parent
                deep_parent = win32gui.GetParent(deep_child)
                if deep_parent:
                    deep_parent_rect = win32gui.GetWindowRect(deep_parent)
                    deep_local_x = point_x - deep_parent_rect[0]
                    deep_local_y = point_y - deep_parent_rect[1]
                lParam_deep = (deep_local_y << 16) | (deep_local_x & 0xFFFF)
                windll.user32.PostMessageW(deep_child, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam_deep)
                time.sleep(0.05)
                windll.user32.PostMessageW(deep_child, win32con.WM_LBUTTONUP, 0, lParam_deep)
                time.sleep(1.0)
                after = bot.capture_window_region()
                _report_diff(bot, before, after, "DeepE_WindowFromPoint_PostMessage")
            else:
                print("  WindowFromPoint returned None.")

        else:
            print("  ChildWindowFromPoint returned the main window itself.")
            print("  The button position is on the main window surface, not a child control.")
            _try_deep_clicks_no_children(bot)
    else:
        print("\nCould not determine button position from templates.")
        print("Try providing coordinates manually with --coords.")

    # ── Try pywinauto / UI Automation if available ──
    _try_uiautomation(bot)


def _try_deep_clicks_no_children(bot):
    """Try deep click methods when no child windows were found."""
    import win32gui
    import win32con
    from ctypes import windll

    target_local_x, target_local_y = _get_template_position(bot)
    if target_local_x is None:
        print("Cannot determine button position.")
        return

    hwnd = bot.hwnd
    rect = bot.get_window_rect()
    screen_x = rect[0] + target_local_x
    screen_y = rect[1] + target_local_y

    import cv2

    # Method: WindowFromPoint to find what's actually at that screen position
    print(f"\n--- Finding what's at screen ({screen_x}, {screen_y}) ---")
    deep_hwnd = win32gui.WindowFromPoint((screen_x, screen_y))
    if deep_hwnd:
        deep_class = win32gui.GetClassName(deep_hwnd)
        deep_text = win32gui.GetWindowText(deep_hwnd)
        print(f"  WindowFromPoint: HWND={deep_hwnd}, Class='{deep_class}', Text='{deep_text}'")

        if deep_hwnd != hwnd:
            print(f"  DIFFERENT from main window! Clicks need to go to THIS child.")

            before = bot.capture_window_region()
            # Convert coords to this child's local space
            child_rect = win32gui.GetWindowRect(deep_hwnd)
            child_local_x = screen_x - child_rect[0]
            child_local_y = screen_y - child_rect[1]
            lParam = (child_local_y << 16) | (child_local_x & 0xFFFF)

            print(f"  Sending click to child at local ({child_local_x}, {child_local_y})...")
            windll.user32.PostMessageW(deep_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
            time.sleep(0.05)
            windll.user32.PostMessageW(deep_hwnd, win32con.WM_LBUTTONUP, 0, lParam)
            time.sleep(1.0)
            after = bot.capture_window_region()
            _report_diff(bot, before, after, "Deep_WindowFromPoint_child_click")

            # Also try BM_CLICK if it's a button
            if "button" in deep_class.lower():
                print(f"\n  It's a button! Trying BM_CLICK...")
                before = bot.capture_window_region()
                win32gui.SendMessage(deep_hwnd, win32con.BM_CLICK, 0, 0)
                time.sleep(1.0)
                after = bot.capture_window_region()
                _report_diff(bot, before, after, "Deep_BM_CLICK_on_found_button")
        else:
            print(f"  Same as main window — the click IS going to the right window.")
            print(f"  The app may be blocking programmatic clicks or using a custom framework.")

            # Last resort: try SetFocus + keypress (Enter/Space)
            print(f"\n--- Last resort: SetFocus + keyboard ---")
            before = bot.capture_window_region()
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
            except Exception:
                pass
            # Move cursor there first (some apps need hover for focus)
            import pyautogui
            pyautogui.moveTo(screen_x, screen_y, duration=0.2)
            time.sleep(0.2)
            # Try pressing Enter
            pyautogui.press('enter')
            time.sleep(1.0)
            after = bot.capture_window_region()
            _report_diff(bot, before, after, "Deep_keyboard_enter")

            if after is not None:
                diff_result = bot._compute_diff(before, after, "keyboard")
                if not diff_result['changed']:
                    # Try Space instead
                    before2 = bot.capture_window_region()
                    pyautogui.press('space')
                    time.sleep(1.0)
                    after2 = bot.capture_window_region()
                    _report_diff(bot, before2, after2, "Deep_keyboard_space")
    else:
        print("  WindowFromPoint returned None — unusual.")


def _try_uiautomation(bot):
    """Try using UI Automation (pywinauto) to find and click buttons."""
    print(f"\n{'=' * 60}")
    print(f"  UI AUTOMATION (pywinauto) ATTEMPT")
    print(f"{'=' * 60}")

    try:
        from pywinauto import Application
        print("pywinauto is installed! Trying to connect...")

        hwnd = bot.hwnd
        app = Application().connect(handle=hwnd)
        window = app.window(handle=hwnd)

        print(f"Connected to window via pywinauto.")
        print(f"Window title: '{window.window_text()}'")

        # Try to dump the control tree
        print("\nControl tree (first 30 items):")
        try:
            window.print_control_identifiers(depth=3)
        except Exception as e:
            print(f"  Could not print control tree: {e}")

        # Try to find and click a button
        print("\nLooking for clickable buttons...")
        try:
            # Try common button texts
            for text in ["Start", "First", "OK", "Continue", "Run"]:
                try:
                    btn = window.child(title=text, control_type="Button")
                    if btn.exists(timeout=1):
                        print(f"  Found button: '{text}' — attempting click...")
                        before = bot.capture_window_region()
                        btn.click()
                        time.sleep(1.0)
                        after = bot.capture_window_region()
                        _report_diff(bot, before, after, f"pywinauto_click_{text}")
                except Exception:
                    pass
        except Exception as e:
            print(f"  Button search failed: {e}")

        # Try click_input (more realistic, moves mouse)
        print("\nTrying click_input (simulates real mouse input)...")
        target_local_x, target_local_y = _get_template_position(bot)
        if target_local_x:
            rect = bot.get_window_rect()
            screen_x = rect[0] + target_local_x
            screen_y = rect[1] + target_local_y
            try:
                window.click_input(coords=(target_local_x, target_local_y))
                time.sleep(1.0)
                print("  click_input sent — check if it worked above.")
            except Exception as e:
                print(f"  click_input failed: {e}")

    except ImportError:
        print("\npywinauto is NOT installed.")
        print("This is the most powerful option for clicking stubborn windows.")
        print("Install it with:  pip install pywinauto")
        print("Then re-run this test.")
    except Exception as e:
        print(f"pywinauto error: {e}")


def _get_template_position(bot):
    """Try to get the local position of a template match in the window."""
    # Try start_btn first, then any available template
    for tpl_name in [TEMPLATE_START, TEMPLATE_FIRST, TEMPLATE_CONTINUE]:
        report = bot.get_template_confidence_report(tpl_name)
        if report.get("above_fallback") and "best_location" in report:
            try:
                loc_str = report["best_location"].strip("()")
                x, y = [int(v.strip()) for v in loc_str.split(",")]
                return x, y
            except Exception:
                continue
    return None, None


def _report_diff(bot, before, after, method_name):
    """Compare before/after screenshots and report the result."""
    if before is None or after is None:
        print("  Could not compare — missing screenshot.")
        return

    diff_result = bot._compute_diff(before, after, method_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = method_name.replace(" ", "_").replace(".", "")

    if diff_result['changed']:
        print(f"  RESULT: CHANGED (diff={diff_result['mean_diff']:.1f}) — THIS METHOD WORKS!")
        bot._save_diff_diagnostic(before, after, f"{ts}_{safe_name}_SUCCESS.png")
    else:
        print(f"  RESULT: No change (diff={diff_result['mean_diff']:.1f}) — didn't work.")
        bot._save_diff_diagnostic(before, after, f"{ts}_{safe_name}_NOCHANGE.png")


def cmd_spy(bot: WindowBot):
    """Window Spy — click anywhere and see what window/control is under the cursor."""
    import win32gui

    print(f"\n{'=' * 60}")
    print(f"  WINDOW SPY — Click anywhere to inspect")
    print(f"  Press Ctrl+C to stop")
    print(f"{'=' * 60}")

    print("\nMove your mouse over the GnBots button and I'll tell you what's there.\n")

    try:
        while True:
            import ctypes
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))

            hwnd_at_point = win32gui.WindowFromPoint((pt.x, pt.y))
            if hwnd_at_point:
                cls = win32gui.GetClassName(hwnd_at_point)
                text = win32gui.GetWindowText(hwnd_at_point)
                rect = win32gui.GetWindowRect(hwnd_at_point)

                # Get parent chain
                parent_chain = []
                parent = win32gui.GetParent(hwnd_at_point)
                while parent:
                    parent_chain.append(parent)
                    parent = win32gui.GetParent(parent)

                # Check if this is inside our GnBots window
                main_hwnd = bot.hwnd
                is_our_window = (
                    hwnd_at_point == main_hwnd or
                    hwnd_at_point in parent_chain or
                    main_hwnd in parent_chain
                )

                ctrl_id = 0
                try:
                    ctrl_id = win32gui.GetDlgCtrlID(hwnd_at_point)
                except Exception:
                    pass

                sys.stdout.write(
                    f"\r  ({pt.x:5d},{pt.y:5d}) → HWND={hwnd_at_point:10d}  "
                    f"Class='{cls:30s}'  Text='{text:20s}'  "
                    f"ID={ctrl_id:5d}  {'*OUR WINDOW*' if is_our_window else ''}     "
                )
                sys.stdout.flush()

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nSpy stopped.")
        print("\nTo use this info for deep clicking:")
        print("  1. Note the Class name and HWND of the control under the button")
        print("  2. If it shows a different HWND than the main window, that's the child you need")
        print("  3. The 'ID' value can be used with WM_COMMAND to trigger the button")


def cmd_diff_test(bot: WindowBot):
    """Capture a screenshot, wait for user to change something, capture again, show diff."""
    print(f"\n{'=' * 60}")
    print(f"  DIFF TEST: Manual before/after comparison")
    print(f"{'=' * 60}")

    import cv2

    print("\nCapturing BEFORE screenshot...")
    before = bot.capture_window_region()
    if before is None:
        print("ERROR: Could not capture window.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = Path(SCREENSHOT_DIR)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(screenshot_dir / f"{ts}_manual_before.png"), before)
    print("BEFORE captured and saved.")

    input("\nNow manually change the window (click something, etc.), then press ENTER to capture AFTER...")

    after = bot.capture_window_region()
    if after is None:
        print("ERROR: Could not capture window.")
        return

    cv2.imwrite(str(screenshot_dir / f"{ts}_manual_after.png"), after)

    diff_result = bot._compute_diff(before, after, "manual_diff")
    print(f"\nDiff: mean={diff_result['mean_diff']:.1f}, max={diff_result['max_diff']:.1f}")
    if diff_result['changed']:
        print("Screen CHANGED between captures.")
    else:
        print("Screen did NOT change between captures.")

    bot._save_diff_diagnostic(before, after, f"{ts}_manual_diff_diagnostic.png")
    print(f"Diagnostic image saved to: {DIFF_DIR}")


def cmd_move_window(bot: WindowBot):
    """Try moving the GnBots window to the second monitor."""
    print(f"\n{'=' * 60}")
    print(f"  WINDOW MOVE TEST")
    print(f"{'=' * 60}")

    rect = bot.get_window_rect()
    print(f"Current position: ({rect[0]}, {rect[1]}) to ({rect[2]}, {rect[3]})")

    print(f"Attempting move to ({MONITOR2_X}, {MONITOR2_Y})...")
    ok = bot.move_to_monitor(MONITOR2_X, MONITOR2_Y)
    if ok:
        new_rect = bot.get_window_rect()
        print(f"New position: ({new_rect[0]}, {new_rect[1]}) to ({new_rect[2]}, {new_rect[3]})")
        print("Move succeeded!")
    else:
        print("Move FAILED — likely privilege mismatch.")
        print("This is normal if GnBots runs as admin but this script doesn't.")
        print("Run this script as admin to fix: right-click → Run as Administrator")


def cmd_interactive():
    """Show the full interactive menu."""
    print("\n" + "=" * 60)
    print("  FARM BOT — CLICK TESTING TOOL")
    print("=" * 60)
    print("""
  Options:
    1. Scan all templates (show confidence scores)
    2. Test click by template name
    3. Test click by screen coordinates
    4. Test ALL click methods on a template
    5. DEEP click analysis (child windows + UI Automation)
    6. Window spy (hover to see what's under cursor)
    7. Manual before/after diff test
    8. Move window to second monitor
    9. Capture current window screenshot
    0. Exit
    """)

    bot = setup_bot()

    while True:
        choice = input("\nChoose option (0-9): ").strip()

        if choice == "1":
            cmd_scan(bot)
        elif choice == "2":
            name = input("Template name (e.g. start_btn or start_btn.png): ").strip()
            if name:
                cmd_template_click(bot, name)
        elif choice == "3":
            try:
                x = int(input("X coordinate: ").strip())
                y = int(input("Y coordinate: ").strip())
                cmd_coords_click(bot, x, y)
            except ValueError:
                print("Invalid coordinates.")
        elif choice == "4":
            name = input("Template name (e.g. start_btn or start_btn.png): ").strip()
            if name:
                cmd_all_methods(bot, name)
        elif choice == "5":
            cmd_deep(bot)
        elif choice == "6":
            cmd_spy(bot)
        elif choice == "7":
            cmd_diff_test(bot)
        elif choice == "8":
            cmd_move_window(bot)
        elif choice == "9":
            import cv2
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_dir = Path(SCREENSHOT_DIR)
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            bot.save_capture(f"{ts}_manual_capture.png", str(screenshot_dir))
            print(f"Screenshot saved.")
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


def main():
    parser = argparse.ArgumentParser(description="Click testing tool for GnBots automation")
    parser.add_argument("--template", "-t", help="Test clicking a specific template")
    parser.add_argument("--coords", "-c", nargs=2, type=int, metavar=("X", "Y"),
                        help="Test clicking at screen coordinates")
    parser.add_argument("--scan", "-s", action="store_true",
                        help="Scan all templates and show confidence")
    parser.add_argument("--all-methods", "-a", metavar="TEMPLATE",
                        help="Try ALL click methods on a template")
    parser.add_argument("--deep", "-d", action="store_true",
                        help="Deep analysis: enumerate child windows and try deep clicks")
    parser.add_argument("--spy", action="store_true",
                        help="Window spy: hover to see what's under the cursor")
    parser.add_argument("--diff", action="store_true",
                        help="Manual before/after diff test")
    parser.add_argument("--move", "-m", action="store_true",
                        help="Test moving window to second monitor")

    args = parser.parse_args()

    _ensure_admin()

    if not any(vars(args).values()):
        cmd_interactive()
        return

    bot = setup_bot()

    if args.scan:
        cmd_scan(bot)
    if args.template:
        cmd_template_click(bot, args.template)
    if args.coords:
        cmd_coords_click(bot, args.coords[0], args.coords[1])
    if args.all_methods:
        cmd_all_methods(bot, args.all_methods)
    if args.deep:
        cmd_deep(bot)
    if args.spy:
        cmd_spy(bot)
    if args.diff:
        cmd_diff_test(bot)
    if args.move:
        cmd_move_window(bot)


if __name__ == "__main__":
    main()
