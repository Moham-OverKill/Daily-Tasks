"""
Daily Tasks - Qt Version Entry Point
Run this file to launch the app with full window transparency
Auto-closes previous instances to prevent duplicates
"""

import sys
import os
import psutil
import time
import traceback

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Prevent pythonw crash on print() when sys.stdout is None
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

def cleanup_old_instances():
    """Find and kill previous instances of this app"""
    current_pid = os.getpid()
    script_name = "main_qt.py"
    
    print(f"Checking for old instances... (Current PID: {current_pid})", flush=True)
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Skip self
            if proc.info['pid'] == current_pid:
                continue
                
            # Check if it's a python process running main_qt.py
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = proc.info['cmdline']
                if cmdline:
                    # Check if script name is in arguments
                    args = ' '.join(cmdline).lower()
                    if script_name in args or 'daily tasks' in args:
                        print(f"Found existing instance (PID {proc.info['pid']}) - Closing...", flush=True)
                        proc.terminate()
                        killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if killed_count > 0:
        print("Waiting for cleanup...", flush=True)
        time.sleep(1) # Wait for release

if __name__ == "__main__":
    try:
        from src.qt_app import run_qt_app
        run_qt_app()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}", flush=True)
        traceback.print_exc()
        input("Press Enter to exit...") # Keep window open if crashed
        sys.exit(1)
