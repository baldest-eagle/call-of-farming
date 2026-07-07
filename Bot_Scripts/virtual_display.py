"""
virtual_display.py — Virtual Display Driver (VDD) setup and diagnostic utility.

Supports:
  - Parsec VDD  (https://parsec.app, driver name "Parsec Virtual Display Adapter")
  - VirtualDrivers/Virtual-Display-Driver  (https://github.com/VirtualDrivers/Virtual-Display-Driver)
  - IddSampleDriver, Mirage driver, etc.

Use this script to:
  1. Detect if a virtual display is already installed and active
  2. Show monitor layout info (useful for configuring MONITOR2_X/Y)
  3. Test PrintWindow capture on the virtual display
  4. Verify Ghost Mode works with your setup
  5. Verify Parsec VDD specifically (driver + active display)

Usage:
    python virtual_display.py              # Show monitor info and VDD status
    python virtual_display.py --detect     # Just detect VDD presence (exit 0/1)
    python virtual_display.py --coords     # Print MONITOR2_X/Y for config.py
    python virtual_display.py --ghost-test # Test making GnBots invisible
    python virtual_display.py --parsec     # Detailed Parsec VDD status

──────────────────────────────────────────────────────────────────────────────
PARSECVDD SETUP (quick start)
──────────────────────────────────────────────────────────────────────────────
1. Install Parsec VDD (you've done this).
2. Open VDD Controller (the third-party app you also installed).
3. In VDD Controller, find the Parsec VDD entry and click "Plug In"
   (Parsec VDD starts in an "unplugged" state — like an HDMI cable
   that's not connected). Pick a resolution like 1920x1080 @ 60Hz.
4. Open Windows Settings → System → Display. You should now see a
   second monitor. Click "Extend desktop to this display" and drag
   it to the right of your primary monitor.
5. Run:  python virtual_display.py --parsec
   Confirm it says "Parsec VDD display: ACTIVE".
6. Run:  python virtual_display.py --coords
   It will print the MONITOR2_X / MONITOR2_Y that config.py will use
   automatically (config.py calls get_opposite_monitor_coords()).
7. (Optional) Run:  python virtual_display.py --ghost-test
   to verify PrintWindow still captures GnBots when made invisible.

If you don't see the second monitor in Display Settings, the VDD
is "unplugged" — open VDD Controller and click Plug In again.

──────────────────────────────────────────────────────────────────────────────
TROUBLESHOOTING
──────────────────────────────────────────────────────────────────────────────
* "Parsec VDD driver: NOT INSTALLED"
  → The Parsec VDD driver service isn't registered. Reinstall it
    (run the Parsec VDD installer as admin).

* "Parsec VDD driver: INSTALLED" but "Display: NOT ACTIVE"
  → The driver is loaded but no virtual monitor is plugged in.
    Open VDD Controller and click "Plug In".

* Monitor detected but `is_virtual=False` in the diagnostic
  → WMI may be returning a generic monitor name. Doesn't matter —
    config.py picks up any non-primary monitor anyway.

* Ghost Mode test produces blank captures
  → Some apps (Chromium-based) don't render to PrintWindow when
    invisible. Use GHOST_ALPHA=1 instead of 0 to keep a 1-pixel
    visible outline. See config.py for details.
"""

import sys
import ctypes
from pathlib import Path

# DPI awareness must be set before any window/monitor operations
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

import win32api
import win32con
import win32gui


# ──────────────────────────────────────────────────────────────────────────────
# WMI cross-check for monitor PNP device IDs
# ──────────────────────────────────────────────────────────────────────────────
# GetMonitorInfo returns device strings like "\\\\.\\DISPLAY2\\Monitor0" which
# don't contain vendor names. We cross-reference against WMI's
# Win32_DesktopMonitor to get the PNPDeviceID and friendly Name, which DO
# contain "Parsec" for Parsec VDD or "IddSampleDriver" for the open-source VDD.
def _get_monitor_pnp_names() -> dict:
    """Return a dict mapping monitor index (1-based) → (pnp_id, friendly_name).

    Returns an empty dict if WMI is unavailable (e.g., on non-Windows or if
    the WMI service is stopped).
    """
    try:
        import wmi  # lazy import — pywinauto removed, but wmi is independent
    except ImportError:
        return {}

    try:
        c = wmi.WMI()
        result = {}
        for i, m in enumerate(c.Win32_DesktopMonitor(), start=1):
            pnp_id = getattr(m, "PNPDeviceID", "") or ""
            name = getattr(m, "Name", "") or ""
            result[i] = (pnp_id, name)
        return result
    except Exception as e:
        # WMI failures are non-fatal — fall back to keyword detection only
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# Parsec VDD driver detection via registry
# ──────────────────────────────────────────────────────────────────────────────
def _check_parsec_vdd_installed() -> bool:
    """Check if the Parsec VDD driver service is registered.

    Parsec VDD installs as a kernel service named "ParsecVDD" under
    HKLM\\SYSTEM\\CurrentControlSet\\Services. We check for its presence.
    Doesn't require admin — read access to that key is allowed for users.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\ParsecVDD",
        ) as key:
            # If we can open the key, the service is registered
            winreg.QueryValueEx(key, "ImagePath")
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Monitor enumeration
# ──────────────────────────────────────────────────────────────────────────────
# Keywords that suggest a virtual display — extended to include Parsec VDD.
VIRTUAL_KEYWORDS = (
    "idd", "virtual", "rooted", "mirage",
    "parsec", "virtualdisplay", "indirectdisplay",
)


def get_all_monitors() -> list:
    """Return detailed info about all connected monitors.

    Cross-references Win32 EnumDisplayMonitors with WMI Win32_DesktopMonitor
    so we can identify virtual displays (Parsec VDD, VirtualDrivers VDD, etc.)
    by their PNP device ID / friendly name, not just by their Device string.
    """
    monitors = []
    wmi_names = _get_monitor_pnp_names()

    try:
        for idx, (hMonitor, _, rect) in enumerate(win32api.EnumDisplayMonitors(), start=1):
            info = win32api.GetMonitorInfo(hMonitor)
            device_name = info.get("Device", "Unknown")
            is_primary = bool(info.get("Flags", 0) & win32con.MONITORINFOF_PRIMARY)
            monitor_rect = info.get("Monitor", (0, 0, 0, 0))
            work_rect = info.get("Work", (0, 0, 0, 0))

            # Pull the WMI cross-reference (by index — WMI usually returns
            # monitors in the same order as EnumDisplayMonitors, though not
            # guaranteed; this is best-effort, not authoritative).
            pnp_id, friendly_name = wmi_names.get(idx, ("", ""))
            combined = f"{device_name} {pnp_id} {friendly_name}".lower()

            is_virtual = any(kw in combined for kw in VIRTUAL_KEYWORDS)
            is_parsec = "parsec" in combined

            monitors.append({
                "handle": hMonitor,
                "device": device_name,
                "pnp_id": pnp_id,
                "friendly_name": friendly_name,
                "is_primary": is_primary,
                "is_virtual": is_virtual,
                "is_parsec": is_parsec,
                "rect": monitor_rect,
                "work_area": work_rect,
                "width": monitor_rect[2] - monitor_rect[0],
                "height": monitor_rect[3] - monitor_rect[1],
                "x": monitor_rect[0],
                "y": monitor_rect[1],
            })
    except Exception as e:
        print(f"Error enumerating monitors: {e}")

    return monitors


def detect_vdd() -> dict:
    """Check if a Virtual Display Driver is installed and return its info."""
    monitors = get_all_monitors()
    virtual = [m for m in monitors if m["is_virtual"]]
    physical = [m for m in monitors if not m["is_virtual"]]
    parsec = [m for m in monitors if m["is_parsec"]]

    return {
        "total_monitors": len(monitors),
        "virtual_displays": virtual,
        "physical_displays": physical,
        "parsec_displays": parsec,
        "parsec_driver_installed": _check_parsec_vdd_installed(),
        "vdd_installed": len(virtual) > 0,
    }


def print_monitor_info():
    """Print a detailed summary of all monitors."""
    result = detect_vdd()

    print("=" * 60)
    print("  MONITOR / VIRTUAL DISPLAY DIAGNOSTIC")
    print("=" * 60)
    print()
    print(f"Total monitors detected:    {result['total_monitors']}")
    print(f"Virtual Display Driver:     {'INSTALLED' if result['vdd_installed'] else 'NOT DETECTED'}")
    print(f"Parsec VDD driver service:  {'INSTALLED' if result['parsec_driver_installed'] else 'NOT INSTALLED'}")
    print()

    for i, m in enumerate(result["physical_displays"], 1):
        label = "PRIMARY" if m["is_primary"] else "Secondary"
        print(f"  Physical Monitor {i} ({label}):")
        print(f"    Device:   {m['device']}")
        if m["friendly_name"]:
            print(f"    Name:     {m['friendly_name']}")
        if m["pnp_id"]:
            print(f"    PNP ID:   {m['pnp_id']}")
        print(f"    Position: ({m['x']}, {m['y']})")
        print(f"    Size:     {m['width']}x{m['height']}")
        print()

    for i, m in enumerate(result["virtual_displays"], 1):
        label = "PRIMARY" if m["is_primary"] else ("PARSEC" if m["is_parsec"] else "Virtual")
        print(f"  Virtual Display {i} ({label}):")
        print(f"    Device:   {m['device']}")
        if m["friendly_name"]:
            print(f"    Name:     {m['friendly_name']}")
        if m["pnp_id"]:
            print(f"    PNP ID:   {m['pnp_id']}")
        print(f"    Position: ({m['x']}, {m['y']})")
        print(f"    Size:     {m['width']}x{m['height']}")
        print()

    if not result["vdd_installed"] and not result["parsec_driver_installed"]:
        print("-" * 60)
        print("  No Virtual Display Driver detected!")
        print()
        print("  Recommended options (free):")
        print()
        print("  [A] Parsec VDD — easiest, GUI-based control")
        print("      1. Download from: https://parsec.app/downloads")
        print("      2. Install, then download VDD Controller from:")
        print("         https://github.com/MojoDB/VDDController")
        print("      3. Run VDD Controller and click 'Plug In'")
        print()
        print("  [B] VirtualDrivers/Virtual-Display-Driver — open source")
        print("      1. Download from:")
        print("         https://github.com/VirtualDrivers/Virtual-Display-Driver")
        print("      2. Run the installer (VDC app)")
        print("      3. Add a virtual display (e.g., 1920x1080 @ 60Hz)")
        print()
        print("  After installing, position the virtual display in")
        print("  Windows Settings → System → Display (extend right),")
        print("  then re-run this script.")
        print("-" * 60)
    elif result["parsec_driver_installed"] and not result["virtual_displays"]:
        print("-" * 60)
        print("  Parsec VDD driver is installed, but no virtual display")
        print("  is currently active ('plugged in').")
        print()
        print("  Fix: Open VDD Controller and click 'Plug In' to attach")
        print("  a virtual monitor. Then re-run this script.")
        print("-" * 60)

    return result


def print_coords():
    """Print the MONITOR2_X/Y values for config.py."""
    result = detect_vdd()

    # Prefer Parsec VDD > other virtual display > non-primary physical
    target = None
    if result["parsec_displays"]:
        target = result["parsec_displays"][0]
    elif result["virtual_displays"]:
        target = result["virtual_displays"][0]
    elif result["physical_displays"]:
        non_primary = [m for m in result["physical_displays"] if not m["is_primary"]]
        if non_primary:
            target = non_primary[0]

    if target:
        kind = "Parsec VDD" if target["is_parsec"] else ("virtual" if target["is_virtual"] else "physical")
        print(f"\nTarget monitor ({kind}) coordinates for config.py:")
        print(f"  MONITOR2_X = {target['x']}")
        print(f"  MONITOR2_Y = {target['y']}")
        print(f"  (Resolution: {target['width']}x{target['height']})")
        print()
        print("Note: config.py auto-detects these via get_opposite_monitor_coords().")
        print("You don't need to hardcode them unless you want to override.")
    else:
        print("\nNo secondary or virtual display found!")
        print("Plug in a VDD or connect a second monitor.")


def print_parsec_status():
    """Print Parsec VDD specific status."""
    print("=" * 60)
    print("  PARSEC VDD STATUS")
    print("=" * 60)
    print()

    # Driver
    driver_ok = _check_parsec_vdd_installed()
    print(f"  Driver service:  {'INSTALLED' if driver_ok else 'NOT INSTALLED'}")
    if not driver_ok:
        print()
        print("  The Parsec VDD driver is not registered with Windows.")
        print("  Re-run the Parsec VDD installer as administrator.")
        return

    # Active display
    result = detect_vdd()
    parsec_displays = result["parsec_displays"]

    if parsec_displays:
        print(f"  Display status:  ACTIVE ({len(parsec_displays)} display(s))")
        print()
        for i, m in enumerate(parsec_displays, 1):
            print(f"  Parsec VDD Display {i}:")
            print(f"    Device:    {m['device']}")
            if m["friendly_name"]:
                print(f"    Name:      {m['friendly_name']}")
            if m["pnp_id"]:
                print(f"    PNP ID:    {m['pnp_id']}")
            print(f"    Position:  ({m['x']}, {m['y']})")
            print(f"    Size:      {m['width']}x{m['height']}")
            print(f"    Primary:   {m['is_primary']}")
            print()
        print(f"  → config.py will target this display automatically")
        print(f"    (VDD_PREFER=True, MONITOR2_X/Y auto-detected)")
    else:
        print(f"  Display status:  NOT ACTIVE (plugged out)")
        print()
        print("  The Parsec VDD driver is loaded but no virtual monitor")
        print("  is currently attached.")
        print()
        print("  Fix: Open VDD Controller and click 'Plug In' to attach")
        print("  a virtual monitor at 1920x1080 (or any resolution).")
        print("  Then re-run: python virtual_display.py --parsec")


def test_ghost_mode():
    """Test Ghost Mode by making GnBots invisible and verifying capture."""
    from window_bot import WindowBot
    from config import GNBOTS_TITLE, TEMPLATE_DIR

    print("\n" + "=" * 60)
    print("  GHOST MODE TEST")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Find the GnBots window")
    print("  2. Capture it while visible")
    print("  3. Make it invisible (alpha=0)")
    print("  4. Capture it while invisible (PrintWindow)")
    print("  5. Restore it to visible")
    print()

    bot = WindowBot(
        window_title=GNBOTS_TITLE,
        template_dir=TEMPLATE_DIR,
    )

    if not bot.find_window(timeout=10):
        print("ERROR: GnBots window not found! Make sure it's running.")
        sys.exit(1)

    print(f"Found: '{bot.window_title_actual}'")

    # Capture while visible
    print("\n[1/5] Capturing while visible...")
    visible_img = bot.capture_window_region()
    if visible_img is not None:
        print(f"  Visible capture: {visible_img.width}x{visible_img.height}")
        from PIL import ImageStat
        print(f"  Mean brightness: {ImageStat.Stat(visible_img.convert('L')).mean[0]:.1f}")
    else:
        print("  FAILED: Could not capture visible window")

    # Make invisible
    print("\n[2/5] Making window invisible (alpha=0)...")
    result = bot.make_transparent(0)
    if not result:
        print("  FAILED: Could not make window transparent")
        print("  This usually means we don't have admin privileges.")
        sys.exit(1)
    print("  Window is now invisible.")

    # Capture while invisible
    print("\n[3/5] Capturing while invisible (PrintWindow)...")
    # Force PrintWindow capture by using headless mode temporarily
    original_headless = bot.headless
    bot.headless = True
    invisible_img = bot._capture_printwindow()
    bot.headless = original_headless

    if invisible_img is not None:
        print(f"  Invisible capture: {invisible_img.width}x{invisible_img.height}")
        
        # Compare the captures
        if visible_img is not None and visible_img.size == invisible_img.size:
            from PIL import ImageChops
            diff = ImageChops.difference(visible_img, invisible_img)
            
            # getbbox returns None if the image is completely black (no difference)
            if diff.getbbox() is None:
                print("  RESULT: PrintWindow captures are IDENTICAL — Ghost Mode works!")
            else:
                print("  RESULT: Captures differ slightly — still usable, but check quality.")
    else:
        print("  FAILED: PrintWindow capture returned nothing while invisible.")
        print("  Ghost Mode may not work with this application.")

    # Restore
    print("\n[4/5] Restoring window to visible...")
    bot.make_opaque()
    print("  Window restored.")

    # Save test images
    screenshot_dir = Path(__file__).resolve().parent / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    if visible_img is not None:
        visible_img.save(str(screenshot_dir / "ghost_test_visible.png"))
        print(f"\n[5/5] Saved: ghost_test_visible.png")
    if invisible_img is not None:
        invisible_img.save(str(screenshot_dir / "ghost_test_invisible.png"))
        print(f"  Saved: ghost_test_invisible.png")

    print("\nGhost Mode test complete. Check the screenshots directory.")


if __name__ == "__main__":
    if "--detect" in sys.argv:
        result = detect_vdd()
        print(f"VDD installed: {result['vdd_installed']}")
        print(f"Virtual displays: {len(result['virtual_displays'])}")
        sys.exit(0 if result['vdd_installed'] else 1)

    elif "--coords" in sys.argv:
        print_coords()

    elif "--ghost-test" in sys.argv:
        test_ghost_mode()

    elif "--parsec" in sys.argv:
        print_parsec_status()

    else:
        print_monitor_info()
