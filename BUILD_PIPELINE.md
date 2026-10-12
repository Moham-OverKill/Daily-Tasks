# Daily Tasks - Standard Build & Packaging Pipeline

This document defines the mandatory build specifications, performance standards, and packaging requirements for all future releases and patches of **Daily Tasks**.

---

## 1. PyInstaller Execution Specification (`DailyTasks.spec`)
- **Mode**: `onedir` (`COLLECT` directory bundle) — **NEVER USE `onefile`**.
- **Rationale**: `onedir` eliminates PyInstaller's 2-second temporary directory (`_MEIxxxxxx`) disk extraction overhead on launch.
- **Module & Plugin Exclusions**:
  - Exclude heavy unused Qt binaries: `Qt6Quick.dll`, `Qt6Pdf.dll`, `Qt6Qml.dll`, `Qt6VirtualKeyboard.dll`, `Qt6Svg.dll`, `opengl32sw.dll`, `d3dcompiler_47.dll`, `libcrypto-3-x64.dll`, `Qt6WebEngineCore.dll`, `Qt6Sql.dll`, `Qt6Multimedia.dll`, `Qt6Sensors.dll`, `Qt6Bluetooth.dll`.
  - Exclude unused Python stdlib modules: `asyncio`, `concurrent`, `sqlite3`, `xmlrpc`, `http.server`, `ftplib`, `poplib`, `imaplib`, `smtplib`, `telnetlib`, `multiprocessing`, `curses`, `dbm`, `ctypes.test`, `test`.

---

## 2. Zero-Latency IPC Pre-Check (`start.py`)
- **Pre-Check**: Must execute `try_activate_existing_instance()` via native Win32 `ctypes.windll.kernel32.CreateFileW` on `\\.\pipe\DailyTasksAppIPCV2_5` at line 1 of `start.py` before importing PySide6 or heavy libraries.
- **Latency**: Activates existing background window in `<0.1ms`.

---

## 3. High-Performance GUI & Canvas Standards (`src/`)
- **Particle Loop**: Cap ambient particle updates to **30 FPS**.
- **Visibility Pausing**: Automatically pause `ParticleBackground.stop()` when window is minimized (`changeEvent`), hidden to tray (`hideEvent`), or obscured.
- **Offscreen Buffer Avoidance**: Use native translucent RGBA stylesheets instead of `QGraphicsOpacityEffect` offscreen framebuffers.
- **Window Sizing**: Set `setMinimumSize(700, 500)` and `setMaximumSize(16777215, 16777215)` for edge resizing.

---

## 4. Inno Setup Compression Specification (`setup.iss`)
- **Compression Protocol**: **LZMA2 Ultra Solid Compression** (Mandatory).
  ```iss
  Compression=lzma2/ultra64
  SolidCompression=yes
  LZMADictionarySize=65536
  LZMANumFastBytes=273
  ```
- **Source Directory**: `dist\Daily Tasks\*`
- **Output Target**: `Output\DailyTasksSetup.exe`

---

## 5. Standard Build Commands
```powershell
# Step 1: Run full unit + performance benchmark suite
python -m unittest discover -s tests -p "test_*.py" -v

# Step 2: Rebuild binary directory (optimize=2 stripped bytecode)
py -m PyInstaller DailyTasks.spec --noconfirm

# Step 3: Compile ultra-compressed setup package
& "E:\Programs\Projects\Code\Daily Tasks\node_modules\innosetup\bin\ISCC.exe" "E:\Programs\Projects\Code\Daily Tasks\setup.iss"
```

---

## 6. Mandatory Post-Update Performance & Resilience Verification Gate
Every code update MUST be verified against these non-negotiable standards before packaging:
1. **Locked 60 FPS & Zero-Reflow Delta Updates**:
   - `_load_tasks()` reuses the singleton `AddTaskCard` and skips `QGridLayout` teardown/reflow when task ordering is unchanged (`< 2ms` delta update).
   - Main UI thread is strictly isolated from disk writes, cache scans, and network requests (`save_tasks()`, `save_settings()`, and `_schedule_cache_cleanup()` run on background daemon workers).
2. **Instant Cold Boot & `<0.1ms` Secondary Handshake**:
   - `start.py` executes `try_activate_existing_instance()` via native Win32 `CreateFileW` on `\\.\pipe\DailyTasksAppIPCV2_5` prior to importing `PySide6`.
   - Dialogs and `SettingsPanel` are lazily constructed only upon first user interaction.
3. **Near-0% Idle CPU & Bounded Memory**:
   - Background scheduling uses precision `singleShot` wake timers (`_schedule_next_tick`) rather than short-interval polling.
   - `ParticleBackground` halts immediately when minimized or hidden to tray.
   - `TaskCard._PIXMAP_CACHE` is strictly bounded (128-entry LRU), and orphaned `cache/custom_*` files are pruned asynchronously on the background worker thread.

