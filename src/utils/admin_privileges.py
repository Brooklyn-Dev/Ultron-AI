import ctypes
import os
import sys

def is_admin() -> bool:
    try:
        if os.name == "nt":  # Windows
            return ctypes.windll.shell32.IsUserAnAdmin()
        else:  # Unix/Linux/macOS
            return os.geteuid() == 0
    except OSError as e:
        print(f"[ERROR]: OS error encountered while admin check: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR]: An unexpected error occurred during admin check: {e}", file=sys.stderr)
        return False
    
def check_admin_privileges() -> None:
    if not is_admin():
        print("[ERROR]: This script must be run as Administrator", file=sys.stderr)
        if os.name == "nt":  # Windows
            print('[SYSTEM]: Right-click start.bat and select "Run as administrator"', file=sys.stderr)
        else:  # Unix/Linux/macOS
            print('[SYSTEM]: Please run "sudo ./start.sh"', file=sys.stderr)
        sys.exit(1)
    else:
        print("[SYSTEM]: Admin privileges confirmed")