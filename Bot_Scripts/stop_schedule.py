import ctypes
import sys
import subprocess
from pathlib import Path

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_and_run():
    if is_admin():
        main()
    else:
        script_path = Path(sys.argv[0]).resolve()
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{script_path}"',
            str(script_path.parent), 1
        )
        sys.exit(0)

def main():
    print("Deleting 'FarmCycle' task...")
    res = subprocess.run('schtasks /Delete /TN "FarmCycle" /F', shell=True, capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)

if __name__ == "__main__":
    elevate_and_run()
