# Daily Tasks

A modern, high-performance desktop task and daily routine manager built with **Python** and **PySide6 (Qt6)**. Designed for speed, minimal resource usage, and seamless task tracking throughout the day.

---

## Highlights & Features

- **Modern Frameless UI**: Translucent background with hardware-accelerated ambient particle effects (30 FPS cap, auto-paused when unfocused or minimized).
- **Native Windows Integration**: Windows Aero snap, custom draggable title bar, border edge/corner resizing, taskbar badge counting, and system tray minimization.
- **Ultra-Fast Single-Instance IPC**: Sub-millisecond Win32 named-pipe pre-check (`<0.1ms`) to bring background instances forward instantly.
- **Smart Routine & Page Organization**: Organize tasks across multiple custom pages, reorder pages, and export/import routines via Share IDs.
- **Global Prayer Times Calculator**: Integrated offline astronomical calculation algorithms with auto-geolocation and fallback cache support.
- **Audio & Visual Alerts**: Customizable sound effects, taskbar flashing, urgency indicators, and Do Not Disturb (DND) mode.
- **Dark & Light Themes**: Full theme support with custom styling across all dialogs, pickers, and widgets.

---

## Project Structure

```
Daily Tasks/
├── assets/                  # Icons, sound effects, and graphical assets
├── src/                     # Core application source code
│   ├── api_handler.py       # Geolocation and prayer time API handler
│   ├── constants.py         # Icon categories and emoji definitions
│   ├── prayer_calculator.py # Offline astronomical prayer calculation engine
│   ├── qt_app.py            # Main application window and runtime controller
│   ├── qt_components.py     # Custom Qt widgets, dialogs, cards, and title bar
│   ├── qt_effects.py        # Ambient particle background engine
│   ├── share_handler.py     # Routine export/import encoder & decoder
│   ├── sound_manager.py     # Asynchronous audio notification manager
│   └── task_manager.py      # Core task state machine and persistence engine
├── tests/                   # Automated unit and integration test suites
├── start.py                 # Fast launcher with Win32 named pipe pre-check
├── main_qt.py               # Application bootstrap entry point
├── DailyTasks.spec          # PyInstaller onedir directory build specification
├── setup.iss                # Inno Setup installer script with LZMA2 ultra solid compression
├── BUILD_PIPELINE.md        # Standardized build and packaging guidelines
└── requirements.txt         # Project dependencies
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- Git

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Moham-OverKill/Daily-Tasks.git
   cd Daily-Tasks
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python start.py
   ```

---

## Building & Packaging

The build pipeline uses **PyInstaller** (`onedir` mode) and **Inno Setup** with **LZMA2 Ultra Solid Compression**:

```powershell
# 1. Build directory bundle with PyInstaller
python -m PyInstaller DailyTasks.spec --noconfirm

# 2. Compile setup package with Inno Setup
& "node_modules\innosetup\bin\ISCC.exe" "setup.iss"
```

The resulting installer is output to `Output/DailyTasksSetup.exe`.

---

## Running Tests

Execute the automated test suites:
```bash
python tests\verify_logic.py
python tests\verify_toggle_flow.py
python tests\test_ui_launch.py
python tests\test_disabled_task.py
python tests\verify_london.py
```

---

## License

This project is licensed under the terms of the [license.txt](license.txt) file.
