import ctypes
import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def elevate_and_run():
    if is_admin():
        main()
    else:
        print("Not running as admin. Requesting elevation...")
        script_path = Path(sys.argv[0]).resolve()
        args = [f'"{script_path}"'] + [f'"{a}"' for a in sys.argv[1:]]
        work_dir = str(script_path.parent)
        # Execute runas
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            " ".join(args),
            work_dir, 1
        )
        sys.exit(0)

def main():
    print("Running as admin. Creating scheduled task...")
    
    # Auto-detect paths relative to this script's location
    project_dir = Path(__file__).resolve().parent
    
    # Find pythonw.exe in the same Python installation that's running this script
    python_exe = Path(sys.executable).parent / "pythonw.exe"
    if not python_exe.exists():
        # Fallback: use python.exe if pythonw.exe is not available
        python_exe = Path(sys.executable)
        print(f"WARNING: pythonw.exe not found, using {python_exe}")
    
    script_path = project_dir / "farm_cycle.py"
    if not script_path.exists():
        print(f"ERROR: farm_cycle.py not found at {script_path}")
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description="Schedule the FarmCycle task.")
    parser.add_argument("--start", type=str, help="Start time in HH:MM format (e.g., 15:30)")
    parser.add_argument("--delay", type=int, help="Delay in minutes before the first run (e.g., 180)")
    args = parser.parse_known_args()[0]
    
    if args.start:
        start_time = args.start
    elif args.delay is not None:
        start_time = (datetime.now() + timedelta(minutes=args.delay)).strftime("%H:%M")
    else:
        # Default: current time
        start_time = datetime.now().strftime("%H:%M")
    
    # Build commands
    delete_cmd = 'schtasks /Delete /TN "FarmCycle" /F'
    create_cmd = (
        f'schtasks /Create /TN "FarmCycle" '
        f'/TR "{python_exe} {script_path}" '
        f'/SC DAILY /ST {start_time} /RI 180 /DU 24:00 /RL HIGHEST /F'
    )
    
    # Delete old tasks if any
    for task_name in ["FarmCycle_Run1", "FarmCycle_Run2", "FarmCycle_Run3", "FarmCycle_Run4", "FarmCycle"]:
        subprocess.run(f'schtasks /Delete /TN "{task_name}" /F', shell=True, capture_output=True)
    
    # Create new task
    print(f"Project dir:  {project_dir}")
    print(f"Python exe:   {python_exe}")
    print(f"Script path:  {script_path}")
    print(f"Executing: {create_cmd}")
    res = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
    
    print("STDOUT:")
    print(res.stdout)
    print("STDERR:")
    print(res.stderr)
    print("Return code:", res.returncode)
    
    if res.returncode != 0:
        # Try fallback without /DU 24:00 or with different duration
        print("Trying fallback with /DU 23:59...")
        create_cmd_fallback = (
            f'schtasks /Create /TN "FarmCycle" '
            f'/TR "{python_exe} {script_path}" '
            f'/SC DAILY /ST {start_time} /RI 150 /DU 23:59 /RL HIGHEST /F'
        )
        res_fb = subprocess.run(create_cmd_fallback, shell=True, capture_output=True, text=True)
        print("Fallback STDOUT:")
        print(res_fb.stdout)
        print("Fallback STDERR:")
        print(res_fb.stderr)
        print("Fallback Return code:", res_fb.returncode)

if __name__ == "__main__":
    elevate_and_run()
