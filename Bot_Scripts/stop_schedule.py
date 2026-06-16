import ctypes
import sys
import subprocess
from pathlib import Path

# Import from the project's process_manager instead of duplicating
sys.path.insert(0, str(Path(__file__).resolve().parent))
from process_manager import is_admin

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
