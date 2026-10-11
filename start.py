import ctypes
import sys
import os

_INSTANCE_MUTEX = None

def try_activate_existing_instance():
    """Ultra-fast Win32 named pipe & mutex pre-check (<0.1ms) to activate running background instance without loading heavy libraries."""
    global _INSTANCE_MUTEX
    if sys.platform != "win32":
        return

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    ERROR_PIPE_BUSY = 231
    ERROR_ALREADY_EXISTS = 183
    INVALID_HANDLES = (None, 0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)

    pipe_name = r"\\.\pipe\DailyTasksAppIPCV2_5"

    # Grant the primary background instance permission to take foreground focus
    try:
        user32.AllowSetForegroundWindow(0xFFFFFFFF)
    except Exception:
        pass

    # 1. Fast path: connect directly to active IPC pipe
    handle = kernel32.CreateFileW(
        pipe_name,
        GENERIC_READ | GENERIC_WRITE,
        0, None, OPEN_EXISTING, 0, None
    )
    if handle in INVALID_HANDLES and kernel32.GetLastError() == ERROR_PIPE_BUSY:
        if kernel32.WaitNamedPipeW(pipe_name, 500):
            handle = kernel32.CreateFileW(
                pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0, None, OPEN_EXISTING, 0, None
            )

    if handle not in INVALID_HANDLES:
        # Closing the connected handle immediately triggers QLocalServer.newConnection
        # in the primary instance without blocking on 0-byte pipe buffers.
        kernel32.CloseHandle(handle)
        os._exit(0)

    # 2. Race-condition guard: check kernel mutex in case primary instance is still booting
    _INSTANCE_MUTEX = kernel32.CreateMutexW(None, False, "Local\\DailyTasksSingleInstanceMutex_V2_5")
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        for _ in range(30):
            handle = kernel32.CreateFileW(
                pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0, None, OPEN_EXISTING, 0, None
            )
            if handle not in INVALID_HANDLES:
                kernel32.CloseHandle(handle)
                os._exit(0)
            kernel32.Sleep(20)
        os._exit(0)

try_activate_existing_instance()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.qt_app import run_qt_app

if __name__ == "__main__":
    run_qt_app()

