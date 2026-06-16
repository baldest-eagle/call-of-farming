"""
template_diagnostic.py — Template matching diagnostic tool.
Run this to check how well your templates match against a live GnBots window.

Usage:
    python template_diagnostic.py              # Check all templates
    python template_diagnostic.py start_btn    # Check specific template
    python template_diagnostic.py --live       # Continuous live monitoring
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    TEMPLATE_DIR,
    GNBOTS_TITLE,
    TEMPLATE_MATCH_THRESHOLD,
    TEMPLATE_FALLBACK_THRESHOLD,
)
from window_bot import WindowBot


def run_single_check(template_name=None):
    """Run a single diagnostic pass."""
    print("=" * 60)
    print("  TEMPLATE DIAGNOSTIC TOOL")
    print("=" * 60)

    bot = WindowBot(
        window_title=GNBOTS_TITLE,
        template_dir=TEMPLATE_DIR,
    )

    if not bot.find_window(timeout=10):
        print("ERROR: GnBots window not found!")
        sys.exit(1)

    print(f"\nWindow found. Running diagnostics...\n")

    template_dir = Path(TEMPLATE_DIR)
    if template_name:
        templates = [template_name if template_name.endswith('.png') else f"{template_name}.png"]
    else:
        templates = sorted([f.name for f in template_dir.glob("*.png")])

    if not templates:
        print(f"No templates found in {TEMPLATE_DIR}")
        sys.exit(1)

    results = []
    for tpl in templates:
        report = bot.get_template_confidence_report(tpl)
        results.append(report)

        if "error" in report:
            print(f"  {tpl:30s}  ERROR: {report['error']}")
            continue

        conf = report.get("best_confidence", 0)
        above_primary = report.get("above_threshold", False)
        above_fallback = report.get("above_fallback", False)

        if above_primary:
            status = "PASS"
        elif above_fallback:
            status = "FALLBACK OK"
        else:
            status = "FAIL"

        print(
            f"  {tpl:30s}  conf={conf:.3f}  "
            f"primary={TEMPLATE_MATCH_THRESHOLD:.2f}  "
            f"fallback={TEMPLATE_FALLBACK_THRESHOLD:.2f}  "
            f"[{status}]"
        )

    passed = sum(1 for r in results if r.get("above_threshold"))
    fallback = sum(1 for r in results if r.get("above_fallback") and not r.get("above_threshold"))
    failed = len(results) - passed - fallback

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} pass, {fallback} fallback, {failed} fail (of {len(results)} total)")
    print(f"{'=' * 60}")

    report_path = template_dir / "diagnostic_report.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed report saved to: {report_path}")


def run_live_monitor(interval=5):
    """Continuously monitor template confidence scores."""
    print("=" * 60)
    print("  LIVE TEMPLATE MONITOR (Ctrl+C to stop)")
    print("=" * 60)

    bot = WindowBot(
        window_title=GNBOTS_TITLE,
        template_dir=TEMPLATE_DIR,
    )

    if not bot.find_window(timeout=10):
        print("ERROR: GnBots window not found!")
        sys.exit(1)

    template_dir = Path(TEMPLATE_DIR)
    templates = sorted([f.name for f in template_dir.glob("*.png")])

    if not templates:
        print(f"No templates found in {TEMPLATE_DIR}")
        sys.exit(1)

    print(f"\nMonitoring {len(templates)} templates every {interval}s...\n")

    try:
        while True:
            screenshot = bot.capture_window_region()
            if screenshot is None:
                print(f"  [{time.strftime('%H:%M:%S')}] Could not capture window")
                time.sleep(interval)
                continue

            line = f"  [{time.strftime('%H:%M:%S')}] "
            for tpl in templates:
                match = bot.find_template(screenshot, tpl)
                if match:
                    _, _, conf = match
                    line += f"{tpl.replace('.png','')}: {conf:.2f}  "
                else:
                    line += f"{tpl.replace('.png','')}: ---  "
            print(line)
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


if __name__ == "__main__":
    if "--live" in sys.argv:
        run_live_monitor()
    else:
        template = None
        for arg in sys.argv[1:]:
            if not arg.startswith("-"):
                template = arg
        run_single_check(template)
