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
    
    # Python executable and script path
    python_exe = r"C:\Users\kyleh\AppData\Local\Programs\Python\Python312\pythonw.exe"
    script_path = r"C:\Users\kyleh\.gemini\BotProject\farm_cycle.py"
    
    # 3 hours interval
    start_time = "16:20"
    
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
