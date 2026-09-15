
import ctypes
import sys
import os

def try_activate_existing_instance():
    """Ultra-fast Win32 named pipe pre-check (0.05ms) to activate running background instance without loading heavy libraries."""
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3

    pipe_name = r"\\.\pipe\DailyTasksAppIPCV2_5"
    handle = ctypes.windll.kernel32.CreateFileW(
        pipe_name,
        GENERIC_READ | GENERIC_WRITE,
        0, None, OPEN_EXISTING, 0, None
    )
    if handle != -1 and handle != 0xFFFFFFFF:
        bytes_written = ctypes.c_ulong()
        msg = b"ACTIVATE"
        ctypes.windll.kernel32.WriteFile(handle, msg, len(msg), ctypes.byref(bytes_written), None)
        ctypes.windll.kernel32.CloseHandle(handle)
        sys.exit(0)

try_activate_existing_instance()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.qt_app import run_qt_app

if __name__ == "__main__":
    run_qt_app()
