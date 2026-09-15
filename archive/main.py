import customtkinter as ctk
from src.app import DailyTasksApp
import os
import subprocess

# Set appearance mode and color theme
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

LOCK_FILE = os.path.abspath("instance.lock")

if __name__ == "__main__":
    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    # 1. Single Instance Check (Kill Old)
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    old_pid = int(content)
                    # Force kill the old process
                    subprocess.run(f"taskkill /F /PID {old_pid}", shell=True, capture_output=True)
        except Exception as e:
            print(f"Cleanup error: {e}")
            
    # 2. Write Current PID
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except: pass

    # 3. Run App
    try:
        app = DailyTasksApp()
        app.mainloop()
    finally:
        # Cleanup on exit
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except: pass
