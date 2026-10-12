"""
Daily Tasks App - PySide6 Version
Full window transparency with particles behind all UI elements
Complete feature parity with original CustomTkinter version
"""

import sys
import os
import json
import time
import ctypes
from ctypes import wintypes
import threading
import math
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, 
    QHBoxLayout, QScrollArea, QGridLayout, QFrame, QLabel,
    QSystemTrayIcon, QMenu, QSizePolicy, QGraphicsOpacityEffect,
    QAbstractButton, QComboBox, QSlider, QLineEdit, QTextEdit, QPlainTextEdit
)
from . import share_handler
from PySide6.QtCore import Qt, QTimer, Signal, QCoreApplication, QEvent, QPoint, QPointF, QRectF, QObject, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QPainter, QColor, QAction, QCursor, QPen, QBrush, QLinearGradient

from .qt_effects import ParticleBackground
from .qt_components import (
    TaskCard, Sidebar, AddTaskDialog, SettingsPanel, CustomTitleBar,
    ModernDialogs, PageButton, InfoBadge, _draw_dashed_rounded_rect,
    get_theme_spec, is_light_theme, apply_window_theme_frame, THEME_OPTIONS
)
from .task_manager import TaskManager, _parse_hhmm_to_secs
from .sound_manager import SoundManager
from .constants import ICON_CATEGORIES, APP_VERSION
from .updater import UpdateManager


class _Win32PipeServer(QObject):
    """Zero-dependency Win32 Named Pipe IPC server replacing PySide6.QtNetwork.QLocalServer."""
    activated = Signal()

    def __init__(self, pipe_name=r"\\.\pipe\DailyTasksAppIPCV2_5", parent=None):
        super().__init__(parent)
        self.pipe_name = pipe_name
        self._running = False
        self._pending = False
        self._thread = None

    def listen(self):
        if sys.platform != "win32" or self._running:
            return True
        self._running = True
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        return True

    def _serve_loop(self):
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateNamedPipeW.restype = ctypes.c_void_p
        kernel32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        PIPE_ACCESS_DUPLEX = 0x00000003
        PIPE_TYPE_BYTE = 0x00000000
        PIPE_WAIT = 0x00000000
        INVALID_HANDLES = (None, 0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)

        h_pipe = kernel32.CreateNamedPipeW(
            self.pipe_name,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_BYTE | PIPE_WAIT,
            255, 128, 128, 0, None
        )
        if h_pipe in INVALID_HANDLES:
            self._running = False
            return

        try:
            while self._running:
                ok = kernel32.ConnectNamedPipe(h_pipe, None)
                err = kernel32.GetLastError() if not ok else 0
                if ok or err in (535, 232):  # ERROR_PIPE_CONNECTED (535) or ERROR_NO_DATA (232)
                    self._pending = True
                    try:
                        self.activated.emit()
                    except RuntimeError:
                        break
                    kernel32.DisconnectNamedPipe(h_pipe)
                else:
                    time.sleep(0.05)
        finally:
            kernel32.CloseHandle(h_pipe)


def _build_global_theme_css(spec):
    ar, ag, ab = spec['accent_rgb']
    is_light = spec['is_light']
    sel_bg = f"rgba({ar}, {ag}, {ab}, 52)" if is_light else spec['accent_primary']
    sel_fg = spec['text_main'] if is_light else "#FFFFFF"
    return f"""
    QWidget {{
        color: {spec['text_main']};
        font-family: "Segoe UI";
    }}
    QDialog {{
        background-color: {spec['dialog_bg']};
        color: {spec['text_main']};
    }}
    
    QComboBox {{
        color: {spec['text_main']};
        background-color: {spec['input_bg']};
        border: 1px solid {spec['input_border']};
        padding: 6px;
        border-radius: 6px;
    }}
    QComboBox:hover {{ border: 1px solid {spec['accent']}; }}
    QComboBox::down-arrow {{
        image: none;
        width: 0px; height: 0px;
        margin: 0px;
        border: none;
    }}
    QComboBox::drop-down {{ border: none; width: 0px; }}
    QComboBox QAbstractItemView {{
        color: {spec['text_main']};
        background-color: {spec['dialog_bg']};
        border: 1px solid {spec['input_border']};
        selection-background-color: {sel_bg};
        selection-color: {sel_fg};
        outline: none;
    }}
    
    QLineEdit {{
        color: {spec['text_main']};
        background-color: {spec['input_bg']};
        border: 1px solid {spec['input_border']};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QLineEdit:focus {{ border: 1px solid {spec['accent']}; }}
    
    QLabel {{ color: {spec['text_main']}; background-color: transparent; }}
    
    QToolTip {{
        background-color: {spec['dialog_bg']};
        color: {spec['text_main']};
        border: 1px solid {spec['input_border']};
        border-radius: 6px;
        padding: 8px 10px;
    }}

    QScrollBar:vertical {{
        background: transparent; width: 8px; border: none;
    }}
    QScrollBar::handle:vertical {{
        background: rgba({ar}, {ag}, {ab}, 95); border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {spec['accent']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    
    QMenu {{
        background-color: {spec['dialog_bg']} !important;
        color: {spec['text_main']} !important;
        border: 1px solid {spec['input_border']} !important;
        padding: 5px !important;
        border-radius: 8px !important;
    }}
    QMenu::item {{
        padding: 6px 24px !important;
        background: transparent !important;
        border-radius: 5px !important;
    }}
    QMenu::item:selected {{
        background-color: rgba({ar}, {ag}, {ab}, 55) !important;
        color: {spec['accent']} !important;
    }}
    QMenu::separator {{
        height: 1px !important;
        background: {spec['input_border']} !important;
        margin: 4px 8px !important;
    }}
"""


DARK_THEME_CSS = _build_global_theme_css(get_theme_spec("dark"))
LIGHT_THEME_CSS = _build_global_theme_css(get_theme_spec("light"))


# ─────────────────────────────────────────────────────────────────────────────
# BUG-02 / OPT-03: Define _FLASHWINFO once at module level instead of
# re-creating it as a local class on every _flash_window / _stop_flashing call.
# ─────────────────────────────────────────────────────────────────────────────
class _FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize',    ctypes.c_uint),
        ('hwnd',      ctypes.c_void_p),
        ('dwFlags',   ctypes.c_uint),
        ('uCount',    ctypes.c_uint),
        ('dwTimeout', ctypes.c_uint),
    ]

_FLASHW_STOP  = 0
_FLASHW_ALL   = 3
_FLASHW_TIMER = 4

class DailyTasksWindow(QMainWindow):
    """
    Main application window with transparent background and particle effects.
    Full feature parity with CustomTkinter version.
    """
    
    prayer_sync_finished = Signal(bool)
    
    def __init__(self, base_path=None):
        super().__init__()
        
        # Path helper
        if base_path:
            self.base_path = base_path
        elif hasattr(sys, '_MEIPASS'):
            self.base_path = sys._MEIPASS
        else:
            self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        # Managers
        self.task_manager = TaskManager()
        self.sound_manager = SoundManager(self.base_path)
        self._icon_update_scheduled = False
        self._last_opened_date = None
        
        # Flashing state for active task batches
        self._has_flashed_batch = False
        self._flashed_urgent_tasks = set()
        
        # State
        self.dnd_enabled = False
        self.prayer_mode_enabled = False
        self.simple_mode_enabled = False
        self.hide_non_today_enabled = False
        self.hardcore_mode_enabled = False
        self.ui_sounds_enabled = True
        self.ui_volume = 80
        self.current_theme = "dark"  # dark or light
        self.task_cards = {}
        self.cols = 4
        self.current_date_str = datetime.now().strftime("%Y-%m-%d")
        self.last_badge_count = -1
        self.active_page_id = self.task_manager.get_default_page_id()
        self._settings_panel = None
        self._prayer_loading = False
        self._silent_prayer_sync = False
        self.update_manager = None
        self._update_state = {
            "state": "up_to_date",
            "version": APP_VERSION,
            "download_url": "",
            "progress": 0,
            "message": "",
        }
        
        # Settings Storage Paths & Coalesced Atomic Writer State
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.settings_dir = os.path.join(appdata, 'DailyTasks')
        self.settings_path = os.path.join(self.settings_dir, "settings.json")
        self._loading_settings = False
        self._settings_save_lock = threading.Lock()
        self._pending_settings_snapshot = None
        self._settings_writer_active = False

        # Clock drift / sleep-wake tracking
        self._last_tick_wall = time.time()
        self._last_tick_mono = time.monotonic()
        self._wm_taskbar_created = 0
        try:
            self._wm_taskbar_created = int(
                ctypes.windll.user32.RegisterWindowMessageW("TaskbarCreated")
            )
        except Exception:
            self._wm_taskbar_created = 0
        
        # Connect signals
        self.prayer_sync_finished.connect(self._post_prayer_sync)
        
        # Icon path
        self.icon_path = os.path.join(self.base_path, "assets", "icon.png")
        
        # Tray Support
        self.tray_icon = None
        
        # Preload lightweight settings before building UI so cards are built only once
        self._preload_settings()
        
        self._setup_window()
        self._setup_ui()
        self._apply_theme(self.current_theme, save=False)
        self._load_tasks(animate=False, first_load=True)
        
        # Defer non-critical startup operations so main window displays immediately
        QTimer.singleShot(0, self._deferred_startup)

    def _read_settings_dict(self):
        """Read settings.json safely, falling back to settings.json.bak if corrupted."""
        bak_path = self.settings_path + ".bak"
        for candidate in (self.settings_path, bak_path):
            if os.path.exists(candidate):
                try:
                    with open(candidate, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        return data
                except (OSError, json.JSONDecodeError, ValueError):
                    continue
        return None

    def _preload_settings(self):
        """Read lightweight user preferences before building the UI to prevent double rendering."""
        self._loading_settings = True
        try:
            settings = self._read_settings_dict()
            if settings is None:
                self.task_manager.synchronize_task_statuses()
                self._last_opened_date = datetime.now().strftime("%Y-%m-%d")
                return

            self.dnd_enabled = bool(settings.get('dnd_enabled', False))
            self.prayer_mode_enabled = bool(settings.get('prayer_mode_enabled', False))
            self.simple_mode_enabled = bool(settings.get('simple_mode_enabled', False))
            self.hide_non_today_enabled = bool(settings.get('hide_non_today_enabled', False))
            self.hardcore_mode_enabled = bool(settings.get('hardcore_mode_enabled', False))
            self.ui_sounds_enabled = bool(settings.get('ui_sounds_enabled', True))
            try:
                self.ui_volume = max(0, min(100, int(settings.get('ui_volume', 80))))
            except (ValueError, TypeError):
                self.ui_volume = 80
            self.current_theme = settings.get('theme', 'dark') or 'dark'
            self._initial_scroll_pos = settings.get('scroll_position', 0)

            saved_page = settings.get('active_page_id')
            if saved_page and self.task_manager._find_page(saved_page):
                self.active_page_id = saved_page

            today_str = datetime.now().strftime("%Y-%m-%d")
            last_date = settings.get('last_opened_date', today_str)
            if last_date != today_str:
                self.task_manager.reset_daily_tasks()

            if not self.prayer_mode_enabled:
                self.task_manager.remove_synced_tasks()

            self.task_manager.synchronize_task_statuses()
            self._last_opened_date = today_str
            self.sound_manager.set_dnd(self.dnd_enabled)
            self.sound_manager.set_ui_sounds_enabled(self.ui_sounds_enabled)
            self.sound_manager.set_ui_volume(self.ui_volume)
        except Exception as e:
            print(f"Preload settings warning: {e}")
            self.task_manager.synchronize_task_statuses()
            self._last_opened_date = datetime.now().strftime("%Y-%m-%d")
        finally:
            self._loading_settings = False


    @property
    def settings_panel(self):
        return self._ensure_settings_panel()

    def _ensure_settings_panel(self):
        """Lazily construct SettingsPanel on first request."""
        if self._settings_panel is None:
            parent = self.centralWidget() or self
            panel = SettingsPanel(parent)
            panel.hide()
            panel._set_theme(self.current_theme)
            panel.apply_theme(self.current_theme)
            panel.set_values(
                self.dnd_enabled,
                self.prayer_mode_enabled,
                self.simple_mode_enabled,
                self.hardcore_mode_enabled,
                self.ui_sounds_enabled,
                self.ui_volume,
                self.hide_non_today_enabled
            )
            panel.set_prayer_loading(self._prayer_loading)
            panel.set_update_state(**self._update_state)
            panel.close_clicked.connect(self._toggle_settings_panel)
            panel.dnd_toggled.connect(self._toggle_dnd)
            panel.prayer_mode_toggled.connect(self._toggle_prayer_mode)
            panel.simple_mode_toggled.connect(self._toggle_simple_mode)
            panel.hide_non_today_toggled.connect(self._toggle_hide_non_today)
            panel.hardcore_mode_toggled.connect(self._toggle_hardcore_mode)
            panel.ui_sounds_toggled.connect(self._toggle_ui_sounds)
            panel.ui_volume_changed.connect(self._on_ui_volume_changed)
            panel.theme_changed.connect(self._apply_theme)
            panel.check_updates_clicked.connect(self._on_check_updates_clicked)
            panel.install_update_clicked.connect(self._on_install_update_clicked)
            self._settings_panel = panel
        return self._settings_panel

    def _set_update_ui_state(
        self,
        state: str,
        version: str = "",
        download_url: str = "",
        progress: int = 0,
        message: str = "",
    ):
        """Cache update state and forward to SettingsPanel only if already instantiated."""
        if version:
            self._update_state["version"] = version.lstrip("vV")
        if download_url:
            self._update_state["download_url"] = download_url
        self._update_state["state"] = state
        self._update_state["progress"] = int(progress)
        self._update_state["message"] = message or ""
        if self._settings_panel is not None:
            self._settings_panel.set_update_state(**self._update_state)

    def _on_check_updates_clicked(self):
        if self.update_manager is None:
            self._init_update_manager()
        self.update_manager.check_for_updates(silent=False)

    def _on_install_update_clicked(self, version: str, download_url: str):
        if self.update_manager is None:
            self._init_update_manager()
        self.update_manager.download_and_install(download_url=download_url, version=version)

    def _on_update_check_started(self):
        self._set_update_ui_state("checking")

    def _on_update_up_to_date(self, current_ver: str):
        if hasattr(self, "sidebar") and self.sidebar is not None:
            self.sidebar.set_update_available(False)
        self._set_update_ui_state("up_to_date", version=current_ver, message="Up to date")

    def _on_update_available(self, latest_ver: str, download_url: str, _notes: str):
        if hasattr(self, "sidebar") and self.sidebar is not None:
            self.sidebar.set_update_available(True, latest_ver)
        self._set_update_ui_state(
            "update_available",
            version=latest_ver,
            download_url=download_url,
        )

    def _on_update_check_failed(self, err: str):
        self._set_update_ui_state("error", message=err)

    def _on_update_download_started(self, version: str):
        self._set_update_ui_state("downloading", version=version, progress=0)

    def _on_update_download_progress(self, pct: int):
        self._set_update_ui_state(
            "downloading",
            version=self._update_state.get("version", ""),
            download_url=self._update_state.get("download_url", ""),
            progress=pct,
        )

    def _on_update_download_finished(self, installer_path: str):
        self._set_update_ui_state(
            "downloading",
            version=self._update_state.get("version", ""),
            progress=100,
            message="Installing update...",
        )
        self.save_settings()
        if self.update_manager is not None:
            self.update_manager.launch_silent_installer(installer_path)

    def _on_update_download_failed(self, err: str):
        self._set_update_ui_state("error", message=err)

    def _init_update_manager(self):
        if self.update_manager is None:
            self.update_manager = UpdateManager(self, on_quit_callback=self._force_quit)
            self.update_manager.check_started.connect(self._on_update_check_started)
            self.update_manager.up_to_date.connect(self._on_update_up_to_date)
            self.update_manager.update_available.connect(self._on_update_available)
            self.update_manager.check_failed.connect(self._on_update_check_failed)
            self.update_manager.download_started.connect(self._on_update_download_started)
            self.update_manager.download_progress.connect(self._on_update_download_progress)
            self.update_manager.download_finished.connect(self._on_update_download_finished)
            self.update_manager.download_failed.connect(self._on_update_download_failed)

    def _deferred_startup(self):
        """Asynchronously initialize system tray, timers, startup registration, and background sync after window display"""
        self._update_app_icon()
        if self.tray_icon is None:
            self._setup_tray()
            
        if getattr(self, 'update_timer', None) is None:
            self.update_timer = QTimer(self)
            self.update_timer.setSingleShot(True)
            self.update_timer.timeout.connect(self._update_loop)
            self._schedule_next_tick()

        self._ensure_startup()

        if self.prayer_mode_enabled:
            self._sync_prayers_background(silent=True)

        self._init_update_manager()
        QTimer.singleShot(3000, lambda: self.update_manager.check_for_updates(silent=True))
        
    def _handle_ipc_activation(self):
        """Handle activation request from another instance"""
        if hasattr(self, '_ipc_server') and self._ipc_server is not None:
            self._ipc_server._pending = False
        self._restore_window()

    def _get_base_icon_pixmap(self):
        """Load and downscale base icon once to 128x128 (64 KB vs 4.2 MB full 1024x1024)."""
        pix = getattr(self, '_base_icon_pixmap', None)
        if pix is None:
            if os.path.exists(self.icon_path):
                raw = QPixmap(self.icon_path)
                if not raw.isNull():
                    pix = raw.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                else:
                    pix = QPixmap()
                del raw
            else:
                pix = QPixmap()
            self._base_icon_pixmap = pix
        return pix


    def _setup_window(self):
        """Configure the main window"""
        self.setWindowTitle("Daily Tasks (V2.5 - New Engine)")
        self._badge_icon_cache = {}
        self._last_mouse_filter_t = 0.0

        base_pix = self._get_base_icon_pixmap()
        if not base_pix.isNull():
            base_icon = QIcon(base_pix)
            self._badge_icon_cache[(0, False)] = base_icon
            self._badge_icon_cache[(0, True)] = base_icon
            self.setWindowIcon(base_icon)
            
        # Dimensions will be dynamically set by _update_window_size during _load_tasks
        # or by user settings later.
        self.cols = 3
        
        # Frameless window for custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # Enable transparency
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QMainWindow { background: transparent; }")
        
    def _setup_ui(self):
        """Build the UI structure"""
        # Central widget with custom background
        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet("""
            #CentralWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #080C14, stop:0.5 #0D1424, stop:1 #0F172A);
            }
        """)
        self.setCentralWidget(central)
        self.setMouseTracking(True)
        central.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)
        
        # Main layout (stacked: title bar, then particles + UI)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Custom title bar
        self.title_bar = CustomTitleBar("Daily Tasks", self.icon_path)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize_restore)
        self.title_bar.close_clicked.connect(self.close)
        main_layout.addWidget(self.title_bar)
        
        # Container for particles + UI
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        main_layout.addWidget(container)
        
        # Particle Background (behind everything)
        self.particles = ParticleBackground(container)
        self.particles.setGeometry(0, 0, 1000, 600)
        if self.simple_mode_enabled:
            self.particles.set_simple_mode(True)
        else:
            self.particles.spawn_ambient(50)  # Initial particle count
            self.particles.start(fps=60)  # 60 FPS during active motion, auto-suspends when idle
        
        # Sidebar (semi-transparent)
        self.sidebar = Sidebar()
        self.sidebar.add_task_clicked.connect(self._open_add_dialog)
        self.sidebar.settings_clicked.connect(self._toggle_settings_panel)
        
        # Page signals
        self.sidebar.page_selected.connect(self._on_page_selected)
        self.sidebar.page_add_clicked.connect(self._on_page_add)
        self.sidebar.page_rename.connect(self._on_page_rename)
        self.sidebar.page_delete.connect(self._on_page_delete)
        self.sidebar.page_export.connect(self._export_page)
        self.sidebar.page_mute_toggle.connect(self._on_page_mute_toggle)
        self.sidebar.page_reordered.connect(self._on_page_reordered)
        container_layout.addWidget(self.sidebar)
        
        # Initialize page list in sidebar
        self._refresh_page_list()
        
        # Task scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(15, 23, 42, 120);
                width: 8px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(148, 163, 184, 70);
                min-height: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(56, 189, 248, 160);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QScrollBar:horizontal {
                background: rgba(15, 23, 42, 120);
                height: 8px;
                margin: 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(148, 163, 184, 70);
                min-width: 28px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(56, 189, 248, 160);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: transparent;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
        
        # Task grid container
        self.task_container = QWidget()
        self.task_container.setStyleSheet("background: transparent;")
        self.task_layout = QGridLayout(self.task_container)
        self.task_layout.setSpacing(15)
        self.task_layout.setContentsMargins(15, 15, 15, 15)
        
        self.scroll.setWidget(self.task_container)
        container_layout.addWidget(self.scroll)
        
        # Empty State Label (Hidden by default, shown when no tasks)
        self.empty_state_label = QLabel("No tasks for today.\nClick '+ Add Task' to create one.")
        self.empty_state_label.setObjectName("empty_state_label")
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_label.setStyleSheet("color: #64748B; font-size: 16px; font-weight: 500;")
        self.empty_state_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.empty_state_label.hide()
        container_layout.addWidget(self.empty_state_label)
        
    def resizeEvent(self, event):
        """Handle window resize - update particle layer and grid columns"""
        super().resizeEvent(event)
        
        # Update particle layer size
        if hasattr(self, 'particles'):
            self.particles.setGeometry(0, 0, self.width(), self.height())
            
        # Keep settings panel anchored if visible
        if self._settings_panel is not None and self._settings_panel.isVisible():
            self._update_settings_pos()
            
    def _toggle_maximize_restore(self):
        """Toggle window maximized and restored states"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, 'title_bar'):
            self.title_bar.update_max_button_icon(self.isMaximized())

    def _update_resize_cursor(self, pos):
        """Update global cursor based on border proximity"""
        if self.isMaximized():
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            return None

        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        bor = 8

        if x < 0 or x > w or y < 0 or y > h:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            return None

        on_l, on_r = x < bor, x > w - bor
        on_t, on_b = y < bor, y > h - bor

        edge = None
        cursor_shape = None
        if on_t and on_l:
            edge = Qt.TopEdge | Qt.LeftEdge
            cursor_shape = Qt.SizeFDiagCursor
        elif on_t and on_r:
            edge = Qt.TopEdge | Qt.RightEdge
            cursor_shape = Qt.SizeBDiagCursor
        elif on_b and on_l:
            edge = Qt.BottomEdge | Qt.LeftEdge
            cursor_shape = Qt.SizeBDiagCursor
        elif on_b and on_r:
            edge = Qt.BottomEdge | Qt.RightEdge
            cursor_shape = Qt.SizeFDiagCursor
        elif on_l:
            edge = Qt.LeftEdge
            cursor_shape = Qt.SizeHorCursor
        elif on_r:
            edge = Qt.RightEdge
            cursor_shape = Qt.SizeHorCursor
        elif on_t:
            edge = Qt.TopEdge
            cursor_shape = Qt.SizeVerCursor
        elif on_b:
            edge = Qt.BottomEdge
            cursor_shape = Qt.SizeVerCursor

        if cursor_shape is not None:
            if QApplication.overrideCursor() is None or QApplication.overrideCursor().shape() != cursor_shape:
                QApplication.setOverrideCursor(cursor_shape)
        else:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        return edge

    _FILTERED_EVENTS = frozenset((
        QEvent.MouseMove, QEvent.Enter, QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Show
    ))

    def eventFilter(self, obj, event):
        """Handle border hover cursor, system resize, and global interactive UI audio feedback"""
        etype = event.type()
        if etype not in self._FILTERED_EVENTS:
            return False

        if not self.isVisible() or self.isMinimized() or QApplication.activeWindow() is None:
            return False

        if etype == QEvent.MouseMove:
            now_t = time.perf_counter()
            if now_t - self._last_mouse_filter_t >= 0.015:
                self._last_mouse_filter_t = now_t
                pos = self.mapFromGlobal(QCursor.pos())
                if not self.isMaximized():
                    self._update_resize_cursor(pos)
                if hasattr(self, 'particles'):
                    self.particles.on_mouse_move(pos.x(), pos.y())

        elif etype == QEvent.Enter:
            if isinstance(obj, (QAbstractButton, QComboBox, QSlider)):
                if obj.isEnabled():
                    self.sound_manager.play_hover(id(obj))
            elif isinstance(obj, (PageButton, TaskCard, InfoBadge)) or (
                isinstance(obj, QWidget) and obj.objectName() == 'AddTaskCard'
            ):
                if obj.isEnabled():
                    self.sound_manager.play_hover(id(obj))

        elif etype == QEvent.MouseButtonPress:
            btn = event.button()
            if btn == Qt.LeftButton:
                if not self.isMaximized():
                    pos = self.mapFromGlobal(QCursor.pos())
                    edge = self._update_resize_cursor(pos)
                    if edge is not None:
                        handle = self.windowHandle()
                        if handle:
                            handle.startSystemResize(edge)
                            return True

                if isinstance(obj, (QAbstractButton, QComboBox)) and obj.isEnabled():
                    self.sound_manager.play_click()
                elif isinstance(obj, PageButton) or (
                    isinstance(obj, QWidget) and obj.objectName() == 'AddTaskCard'
                ):
                    self.sound_manager.play_click()
                elif isinstance(obj, TaskCard) and obj.status not in ('pending', 'disabled'):
                    self.sound_manager.play_click()
            elif btn == Qt.RightButton:
                if isinstance(obj, PageButton) or (
                    isinstance(obj, TaskCard) and not obj.task_data.get('is_synced', False)
                ):
                    self.sound_manager.play_click()

        elif etype == QEvent.KeyPress:
            if isinstance(obj, (QLineEdit, QTextEdit, QPlainTextEdit)) and obj.isEnabled() and not obj.isReadOnly():
                key = event.key()
                if key not in (
                    Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta,
                    Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock,
                    Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab
                ):
                    self.sound_manager.play_type(key)

        elif etype == QEvent.Show and isinstance(obj, QMenu):
            if not getattr(obj, '_sfx_connected', False):
                obj._sfx_connected = True
                obj.hovered.connect(lambda action: self.sound_manager.play_hover(id(action)))
                obj.triggered.connect(lambda _action: self.sound_manager.play_click())

        return False
            
    def mouseMoveEvent(self, event):
        """Pass mouse position to particles (Interactive Background)"""
        if hasattr(self, 'particles'):
            self.particles.on_mouse_move(event.pos().x(), event.pos().y())
            
    def _regrid_tasks(self):
        """Reposition task cards in grid without recreating"""
        # Save scroll position
        v_scroll = self.scroll.verticalScrollBar().value()
        
        widgets = []
        for i in range(self.task_layout.count()):
            item = self.task_layout.itemAt(i)
            if item and item.widget():
                widgets.append(item.widget())
                
        # Remove all from layout (but don't delete)
        while self.task_layout.count():
            self.task_layout.takeAt(0)
            
        # Re-add in new positions
        for i, widget in enumerate(widgets):
            row = i // self.cols
            col = i % self.cols
            self.task_layout.addWidget(widget, row, col)
            
        # Update column stretches
        for i in range(self.cols):
            self.task_layout.setColumnStretch(i, 1)
            
        # Restore scroll position (process events to ensure layout updates first)
        QCoreApplication.processEvents()
        self.scroll.verticalScrollBar().setValue(v_scroll)

    def _update_window_size(self, total_cards, recenter=False):
        """Dynamically size the window (Min 3x2, Max 3x3) to prevent UI clipping"""

        # Lock columns to 3 for consistent width
        self.cols = 3
        
        # Clamp rows between 2 (Minimum height for Settings menu) and 3 (Max height)
        rows = max(2, min(3, math.ceil(total_cards / self.cols)))
        
        # Base fixed dimensions
        sidebar_w = 250
        margins_w = 30
        scrollbar_safety = 36
        card_w = 240
        gap_w = 15
        
        title_h = 32
        margins_h = 30
        bottom_safety = 0
        card_h = 250
        gap_h = 15
        
        # Calculated dynamic dimensions
        w = sidebar_w + (self.cols * card_w) + ((self.cols - 1) * gap_w) + margins_w + scrollbar_safety
        h = title_h + (rows * card_h) + ((rows - 1) * gap_h) + margins_h + bottom_safety

        # Enable window resizing by setting minimum size instead of hard locking fixed size
        self.setMinimumSize(700, 540)
        self.setMaximumSize(16777215, 16777215)
        
        # Initial centering / sizing - Only on first load to prevent jumps when switching pages
        if recenter:
            self.resize(int(w), int(h))
            try:
                screen = QApplication.primaryScreen().availableGeometry()
                # Center math: (Screen - Window) / 2
                self.move(
                    (screen.width() - int(w)) // 2,
                    (screen.height() - int(h)) // 2
                )
            except Exception as e:
                print(f"Centering failed: {e}")
            
    def _ensure_add_task_card(self):
        """Construct the '+' AddTaskCard once and reuse it across all grid refreshes."""
        if getattr(self, '_add_task_card', None) is not None:
            self._apply_add_card_theme()
            return self._add_task_card

        add_card = QFrame()
        add_card.setObjectName("AddTaskCard")
        add_card.setMinimumSize(240, 250)
        add_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_card.setCursor(Qt.PointingHandCursor)
        add_card.setStyleSheet("#AddTaskCard { background: transparent; border: none; }")
        add_card._hover_t = 0.0
        add_card._press_t = 0.0
        add_card._hover_anim = None
        add_card._press_anim = None

        add_card_layout = QVBoxLayout(add_card)
        add_card_layout.setContentsMargins(0, 0, 0, 0)
        add_card_layout.setAlignment(Qt.AlignCenter)

        plus_label = QLabel("")
        plus_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        plus_label.setStyleSheet("background: transparent; border: none;")
        add_card_layout.addWidget(plus_label)

        self._add_task_card = add_card
        self._add_task_plus_label = plus_label

        def _paint_add_card(event, _w=add_card):
            w = _w.width()
            h = _w.height()
            if w <= 4 or h <= 4:
                return
            spec = get_theme_spec(self.current_theme)
            is_light = spec['is_light']
            ht = float(getattr(_w, '_hover_t', 0.0))
            pt = float(getattr(_w, '_press_t', 0.0))

            def lerp_col(c1, c2, t):
                return QColor(
                    int(c1[0] + (c2[0] - c1[0]) * t),
                    int(c1[1] + (c2[1] - c1[1]) * t),
                    int(c1[2] + (c2[2] - c1[2]) * t),
                    int(c1[3] + (c2[3] - c1[3]) * t),
                )

            r1, g1, b1, _ = spec['card_bg1']
            r2, g2, b2, _ = spec['card_bg2']
            rh, gh, bh, _ = spec['card_hover_bg1']
            c_muted = QColor(spec['text_muted'])
            c_acc = QColor(spec['accent'])

            if is_light:
                bg1 = lerp_col((r1, g1, b1, 165), (rh, gh, bh, 205), ht)
                bg2 = lerp_col((r2, g2, b2, 180), (rh, gh, bh, 205), ht)
                bdr = lerp_col((c_muted.red(), c_muted.green(), c_muted.blue(), 215), (c_acc.red(), c_acc.green(), c_acc.blue(), 255), ht)
            else:
                bg1 = lerp_col((r1, g1, b1, 105), (rh, gh, bh, 175), ht)
                bg2 = lerp_col((r2, g2, b2, 125), (r1, g1, b1, 190), ht)
                bdr = lerp_col((c_muted.red(), c_muted.green(), c_muted.blue(), 95), (c_acc.red(), c_acc.green(), c_acc.blue(), 245), ht)
            plus_col = lerp_col((c_muted.red(), c_muted.green(), c_muted.blue(), 235), (c_acc.red(), c_acc.green(), c_acc.blue(), 255), ht)

            mx = 5.5 - (3.0 * ht) + (3.5 * pt)
            my_top = 5.5 - (3.0 * ht) + (3.5 * pt)
            my_bot = 5.5 - (1.5 * ht) + (2.0 * pt)
            rect = QRectF(mx, my_top, w - 2.0 * mx, h - my_top - my_bot)

            painter = QPainter(_w)
            painter.setRenderHint(QPainter.Antialiasing, True)

            grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
            grad.setColorAt(0.0, bg1)
            grad.setColorAt(1.0, bg2)

            _draw_dashed_rounded_rect(
                painter,
                rect,
                16.0,
                grad,
                bdr,
                pen_w=2.0,
                target_cycle_px=15.0,
            )

            if pt > 0.01:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 0, 0, int(26 * pt)))
                painter.drawRoundedRect(rect, 16.0, 16.0)

            cx = rect.center().x()
            cy = rect.center().y()
            arm = 14.0 + (1.0 * ht) - (1.0 * pt)
            plus_pen = QPen(plus_col, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(plus_pen)
            painter.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
            painter.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
            painter.end()

        add_card.paintEvent = _paint_add_card
        self._apply_add_card_theme()

        def _animate_add_card_hover(target, _w=add_card):
            if self.simple_mode_enabled:
                _w._hover_t = float(target)
                _w.update()
                return
            if _w._hover_anim is None:
                _w._hover_anim = QVariantAnimation(_w)
                _w._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
                def _step(v):
                    _w._hover_t = float(v)
                    _w.update()
                _w._hover_anim.valueChanged.connect(_step)
            _w._hover_anim.stop()
            _w._hover_anim.setDuration(145)
            _w._hover_anim.setStartValue(float(_w._hover_t))
            _w._hover_anim.setEndValue(float(target))
            _w._hover_anim.start()

        def _animate_add_card_press(target, duration=70, curve=QEasingCurve.OutQuad, _w=add_card):
            if self.simple_mode_enabled:
                _w._press_t = 0.0
                _w.update()
                return
            if _w._press_anim is None:
                _w._press_anim = QVariantAnimation(_w)
                def _step(v):
                    _w._press_t = float(v)
                    _w.update()
                _w._press_anim.valueChanged.connect(_step)
            _w._press_anim.stop()
            _w._press_anim.setDuration(duration)
            _w._press_anim.setEasingCurve(curve)
            _w._press_anim.setStartValue(float(_w._press_t))
            _w._press_anim.setEndValue(float(target))
            _w._press_anim.start()

        def _add_card_enter(event, _w=add_card):
            _animate_add_card_hover(1.0, _w)
            QFrame.enterEvent(_w, event)

        def _add_card_leave(event, _w=add_card):
            _animate_add_card_hover(0.0, _w)
            if _w._press_t > 0.0:
                _animate_add_card_press(0.0, 135, QEasingCurve.OutCubic, _w)
            QFrame.leaveEvent(_w, event)

        def _add_card_press(event, _widget=add_card):
            if event.button() == Qt.LeftButton:
                _animate_add_card_press(1.0, 70, QEasingCurve.OutQuad, _widget)
                self._open_add_dialog()
                _animate_add_card_press(0.0, 135, QEasingCurve.OutCubic, _widget)
            QFrame.mousePressEvent(_widget, event)

        def _add_card_release(event, _widget=add_card):
            if event.button() == Qt.LeftButton and _widget._press_t > 0.0:
                _animate_add_card_press(0.0, 135, QEasingCurve.OutCubic, _widget)
            QFrame.mouseReleaseEvent(_widget, event)

        add_card.enterEvent = _add_card_enter
        add_card.leaveEvent = _add_card_leave
        add_card.mousePressEvent = _add_card_press
        add_card.mouseReleaseEvent = _add_card_release
        return add_card

    def _load_tasks(self, animate=False, first_load=False):
        """Load and display tasks for the active page with zero-reflow delta update when order is unchanged."""
        tasks = self.task_manager.get_tasks(page_id=self.active_page_id)
        if getattr(self, 'hide_non_today_enabled', False):
            today_weekday = datetime.now().weekday()
            tasks = [
                t for t in tasks
                if today_weekday in t.get('repeat_days', [0, 1, 2, 3, 4, 5, 6])
                and t.get('status') != 'disabled'
            ]
        tasks.sort(key=lambda x: (0 if not x.get('start_time') else 1, x.get('start_time') or ''))

        new_grid_order = tuple(t['id'] for t in tasks)

        # Fast Delta Path: If the exact same task IDs are in the exact same grid order,
        # update card contents in-place without tearing down or reflowing QGridLayout.
        if (
            not first_load
            and getattr(self, '_last_grid_order', None) == new_grid_order
            and getattr(self, '_add_task_card', None) is not None
            and all(tid in self.task_cards for tid in new_grid_order)
        ):
            for task in tasks:
                card = self.task_cards[task['id']]
                card.update_content(task)
                if task.get('status') == 'active' and not card.is_pulsing:
                    card.start_active_pulse()
            self._apply_add_card_theme()
            self._update_app_icon()
            return

        # 1. CLEANUP: Find and remove cards that are no longer in our task list
        current_ids = set(new_grid_order)
        cards_to_remove = [tid for tid in self.task_cards if tid not in current_ids]
        for tid in cards_to_remove:
            card = self.task_cards.pop(tid)
            if hasattr(card, 'cleanup'):
                card.cleanup()
            else:
                card.stop_flashing()
                card.stop_pulse()
            card.deleteLater()

        # 2. Detach items from layout (widgets are preserved in self.task_cards & self._add_task_card)
        while self.task_layout.count():
            self.task_layout.takeAt(0)

        # Always show scroll area
        self.empty_state_label.hide()
        self.scroll.show()

        # Restore scroll if saved
        if hasattr(self, '_initial_scroll_pos'):
            pos = self._initial_scroll_pos
            del self._initial_scroll_pos
            QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(pos))

        # 3. Dynamic Resizing
        self._update_window_size(len(tasks) + 1, recenter=first_load)

        # Set column stretches
        for i in range(self.cols):
            self.task_layout.setColumnStretch(i, 1)

        # 4. Add/Update Task Cards
        for i, task in enumerate(tasks):
            tid = task['id']
            if tid in self.task_cards:
                card = self.task_cards[tid]
                card.update_content(task)
            else:
                card = TaskCard(task)
                card.set_animations_enabled(not self.simple_mode_enabled)
                card.apply_theme(self.current_theme)
                task_id = tid
                card.clicked.connect(lambda checked=False, _id=task_id: self._on_task_clicked_by_id(_id))
                card.delete_requested.connect(lambda checked=False, _id=task_id: self._delete_task_by_id(_id))
                card.edit_requested.connect(lambda checked=False, _id=task_id: self._edit_task_by_id(_id))
                self.task_cards[tid] = card

            row = i // self.cols
            col = i % self.cols
            self.task_layout.addWidget(card, row, col)

            if task.get('status') == 'active' and not card.is_pulsing:
                card.start_active_pulse()

        # 5. Reuse singleton AddTaskCard (+) at the end of the grid
        add_card = self._ensure_add_task_card()
        total_items = len(tasks)
        add_row = total_items // self.cols
        add_col = total_items % self.cols
        self.task_layout.addWidget(add_card, add_row, add_col)

        self._last_grid_order = new_grid_order
        self._update_app_icon()

    def _apply_add_card_theme(self):
        """Trigger repaint of AddTaskCard when theme or hover state updates."""
        add_card = getattr(self, '_add_task_card', None)
        if add_card is None:
            return
        try:
            add_card.update()
        except RuntimeError:
            pass
            
    def _on_task_clicked(self, task):
        """Handle task card click - strict state machine for status transitions.
        
        State Machine Rules:
        - PENDING/GHOST: No action (can't complete future or ghost task)
        - ACTIVE: → DONE (always allowed)
        - FAILED: → DONE (only if Hardcore OFF, else locked)
        - DONE: → ACTIVE (if within time) or → FAILED (if past time)
        """
        current_status = task.get('status', 'pending')
        now = datetime.now()

        # Ghost Check: If not scheduled for today, no action
        repeat_days = task.get('repeat_days', [0,1,2,3,4,5,6])
        if now.weekday() not in repeat_days:
            return  # Ghost task - no action
        
        # Parse task times via O(1) cached integer math
        start_str = task.get('start_time')
        end_str = task.get('end_time')
        now_secs = now.hour * 3600 + now.minute * 60 + now.second
        if not start_str:
            is_within_time = True
        elif not end_str:
            try:
                s_secs = _parse_hhmm_to_secs(start_str)
                is_within_time = now_secs >= s_secs
            except ValueError:
                is_within_time = True
        else:
            try:
                s_secs = _parse_hhmm_to_secs(start_str)
                e_secs = _parse_hhmm_to_secs(end_str)
                if e_secs < s_secs:
                    if now.hour < 12:
                        s_secs -= 86400
                    else:
                        e_secs += 86400
                is_within_time = s_secs <= now_secs <= e_secs
            except ValueError:
                is_within_time = True
        
        # === STATE MACHINE TRANSITIONS ===
        new_status = None
        
        # PENDING or DISABLED → No action (NEVER clickable)
        if current_status in ['pending', 'disabled'] or len(task.get('repeat_days', [0,1,2,3,4,5,6])) == 0:
            return
        
        # ACTIVE → DONE (always allowed)
        elif current_status == 'active':
            new_status = 'done'
        
        # FAILED → DONE (only if Hardcore OFF)
        elif current_status == 'failed':
            if self.hardcore_mode_enabled:
                return  # Locked in Hardcore mode
            new_status = 'done'
        
        # DONE → Undo based on current time
        elif current_status == 'done':
            if is_within_time:
                new_status = 'active'  # Still in time window
            else:
                new_status = 'failed'  # Past time window
        
        if new_status is None:
            return
        
        # Play sound for completing or undoing task
        if new_status == 'done':
            self.sound_manager.play_done()
            
            # Trigger confetti burst
            if not self.simple_mode_enabled:
                card = self.task_cards.get(task['id'])
                if card:
                    pos = card.mapTo(self, card.rect().center())
                    self.particles.burst_confetti(pos.x(), pos.y())
        elif current_status == 'done' and new_status in ('active', 'failed'):
            self.sound_manager.play_undo()
        
        # Update task status
        self.task_manager.update_task_status(task['id'], new_status)
        task['status'] = new_status
        
        # Update card visuals
        if task['id'] in self.task_cards:
            self.task_cards[task['id']].update_task(task)
            
        self._update_app_icon()
            
    def _open_add_dialog(self):
        """Open dialog to add new task"""
        dialog = None
        try:
            dialog = AddTaskDialog(self, icon_categories=ICON_CATEGORIES)
            if hasattr(dialog, 'apply_theme'):
                 dialog.apply_theme(self.current_theme)
            result = dialog.exec()
            if result == 1:  # Accepted
                data = dialog.get_task_data()
                self.task_manager.add_task(
                    name=data['name'],
                    start_time=data['start_time'],
                    end_time=data['end_time'],
                    image_path=data.get('image_path'),
                    repeat_days=data.get('repeat_days'),
                    page_id=self.active_page_id
                )
                self._load_tasks()
        except Exception as e:
            ModernDialogs.show_message(self, "Error", f"Failed to open Add Task dialog:\n{str(e)}", theme=self.current_theme)
            import traceback
            traceback.print_exc()
        finally:
            if dialog is not None:
                dialog.deleteLater()

    # BUG-05 FIX: ID-based dispatch methods — always re-fetch from task_manager so the
    # captured reference is never stale even after _load_tasks re-creates task dicts.
    def _on_task_clicked_by_id(self, task_id):
        task = self.task_manager.get_task_by_id(task_id)
        if task:
            self._on_task_clicked(task)

    def _delete_task_by_id(self, task_id):
        task = self.task_manager.get_task_by_id(task_id)
        if task:
            self._delete_task(task)

    def _edit_task_by_id(self, task_id):
        task = self.task_manager.get_task_by_id(task_id)
        if task:
            self._edit_task(task)

    # ═══════════════════════════════════════════════════════════
    # PAGE MANAGEMENT HANDLERS
    # ═══════════════════════════════════════════════════════════
    
    def _refresh_page_list(self):
        """Refresh the sidebar page list"""
        pages = self.task_manager.get_pages()
        self.sidebar.set_pages(pages, self.active_page_id)
    
    def _on_page_selected(self, page_id):
        """Switch to a different page"""
        if page_id != self.active_page_id:
            self.sound_manager.play_click()
        self.active_page_id = page_id
        self.sidebar.set_active_page(page_id)
        self._load_tasks()
        self.save_settings()
    
    def _on_page_add(self):
        """Show dialog to create new page or import a share ID"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QStackedWidget, QWidget, QTextEdit
        from src.qt_components import AnimatedPushButton as QPushButton
        
        spec = get_theme_spec(self.current_theme)
        is_light = spec['is_light']
        ar, ag, ab = spec['accent_rgb']
        rh, gh, bh, ha = spec['card_hover_bg1']
        # Custom dialog with Name + Import option
        dialog = QDialog(self)
        dialog.current_theme = self.current_theme
        dialog.setWindowTitle("New Page")
        dialog.setFixedSize(360, 220)
        dialog.setAttribute(Qt.WA_StyledBackground, True)
        dialog.setAutoFillBackground(True)
        pal = dialog.palette()
        pal.setColor(dialog.backgroundRole(), QColor(spec['dialog_bg']))
        pal.setColor(dialog.foregroundRole(), QColor(spec['text_main']))
        dialog.setPalette(pal)
        dialog.ensurePolished()
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {spec['dialog_bg']};
                color: {spec['text_main']};
            }}
            QLabel {{
                color: {spec['text_main']};
                background: transparent;
            }}
            QLineEdit, QTextEdit {{
                background-color: {spec['input_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['input_border']};
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {spec['accent']};
            }}
            QPushButton {{
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        dialog.style().unpolish(dialog)
        dialog.style().polish(dialog)
        apply_window_theme_frame(dialog, self.current_theme)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(0)
        layout.setContentsMargins(20, 20, 20, 20)
        
        stack = QStackedWidget()
        layout.addWidget(stack)
        
        # ─── PAGE 1: CREATE ───
        page1 = QWidget()
        p1_layout = QVBoxLayout(page1)
        p1_layout.setContentsMargins(0, 0, 0, 0)
        p1_layout.setSpacing(12)
        
        name_label = QLabel("Page Name:")
        name_label.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p1_layout.addWidget(name_label)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g. Work Routine")
        p1_layout.addWidget(name_input)
        
        p1_layout.addStretch()
        
        # Buttons for Page 1
        p1_btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        import_btn = QPushButton("Import")
        create_btn = QPushButton("Create")
        
        primary_btn_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {spec['accent_primary']}, stop:1 {spec['accent_hover']});
                color: #FFFFFF;
                border: 1px solid rgba({ar}, {ag}, {ab}, 95);
            }}
            QPushButton:hover {{
                background: {spec['accent_hover']};
                border: 1px solid {spec['accent']};
            }}
            QPushButton:disabled {{
                background-color: {'#E2E8F0' if is_light else spec['input_bg']};
                color: {spec['text_muted']};
                border: 1px solid {spec['input_border']};
            }}
        """
        sec_bg = "#E2E8F0" if is_light else spec['input_bg']
        sec_fg = spec['text_main'] if is_light else spec['text_muted']
        sec_hover = "#CBD5E1" if is_light else f"rgba({rh}, {gh}, {bh}, {ha})"
        secondary_btn_style = f"""
            QPushButton {{
                background-color: {sec_bg};
                color: {sec_fg};
                border: 1px solid {spec['input_border']};
            }}
            QPushButton:hover {{
                background-color: {sec_hover};
                color: {spec['text_main']};
            }}
        """
        cancel_btn.setStyleSheet(secondary_btn_style)
        import_btn.setStyleSheet(secondary_btn_style)
        create_btn.setStyleSheet(primary_btn_style)
        
        # RELIABITY FIX: Disable autoDefault to prevent Enter from triggering buttons unexpectedly
        cancel_btn.setAutoDefault(False)
        import_btn.setAutoDefault(False)
        create_btn.setAutoDefault(False)
        
        # SECURITY HOOK: Install event filter to strictly guard Enter key
        # We reuse the filter from ModernDialogs since it's already imported
        filter = ModernDialogs._EnterKeyFilter(create_btn, dialog)
        dialog.installEventFilter(filter)
        
        # RELIABITY FIX: Removed static setDefault(True) to prevent hijacked Enter events
        
        # BUG-09 FIX: Create the opacity effect ONCE outside the closure
        # so we don't allocate a new QGraphicsOpacityEffect object on every keystroke.
        _disabled_effect = QGraphicsOpacityEffect(create_btn)
        _disabled_effect.setOpacity(0.5)

        # Reactive validation for New Page
        def validate_name():
            is_valid = bool(name_input.text().strip())
            create_btn.setEnabled(is_valid)
            create_btn.setDefault(is_valid)  # DYNAMIC DEFAULT

            # Toggle the cached effect instead of creating a new one
            create_btn.setGraphicsEffect(_disabled_effect if not is_valid else None)

        name_input.textChanged.connect(validate_name)
        validate_name()  # Initial state

        p1_btn_layout.addWidget(cancel_btn)
        p1_btn_layout.addWidget(import_btn)
        p1_btn_layout.addWidget(create_btn)
        p1_layout.addLayout(p1_btn_layout)
        
        stack.addWidget(page1)
        
        # ─── PAGE 2: IMPORT ───
        page2 = QWidget()
        p2_layout = QVBoxLayout(page2)
        p2_layout.setContentsMargins(0, 0, 0, 0)
        p2_layout.setSpacing(12)
        
        import_label = QLabel("Paste Shared ID:")
        import_label.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p2_layout.addWidget(import_label)
        
        import_input = QTextEdit()
        import_input.setPlaceholderText("Paste Share ID string here...")
        p2_layout.addWidget(import_input)
        
        p2_btn_layout = QHBoxLayout()
        back_btn = QPushButton("Back")
        do_import_btn = QPushButton("Import")
        
        back_btn.setStyleSheet(secondary_btn_style)
        do_import_btn.setStyleSheet(primary_btn_style)
        
        p2_btn_layout.addWidget(back_btn)
        p2_btn_layout.addWidget(do_import_btn)
        p2_layout.addLayout(p2_btn_layout)
        
        stack.addWidget(page2)
        
        # ─── LOGIC & ROUTING ───
        result_state = {"action": None}
        
        def attempt_create():
            if create_btn.isEnabled():
                result_state["action"] = "create"
                dialog.accept()
                
        def attempt_import():
            if import_input.toPlainText().strip():
                result_state["action"] = "import"
                dialog.accept()
            else:
                ModernDialogs.show_message(dialog, "Import Error", "Please paste a Share ID string.", theme=self.current_theme)
                import_input.setFocus()

        cancel_btn.clicked.connect(dialog.reject)
        import_btn.clicked.connect(lambda: stack.setCurrentIndex(1))
        back_btn.clicked.connect(lambda: stack.setCurrentIndex(0))
        
        create_btn.clicked.connect(attempt_create)
        name_input.returnPressed.connect(lambda: attempt_create() if create_btn.isEnabled() else None)
        do_import_btn.clicked.connect(attempt_import)
        
        accepted = (dialog.exec() == QDialog.Accepted)
        share_id_text = import_input.toPlainText().strip()
        page_name = name_input.text().strip()
        dialog.deleteLater()
        if not accepted:
            return
            
        action = result_state["action"]
        
        if action == "import":
            try:
                decoded_page_name, tasks = share_handler.decode_tasks(share_id_text)
                if not tasks:
                    ModernDialogs.show_message(self, "Import Error", "Invalid Share ID.", theme=self.current_theme)
                    return
                # Use decoded page name (fallback if empty)
                final_name = decoded_page_name or "Imported Routine"
                
                page = self.task_manager.import_tasks_as_page(final_name, tasks)
                self.active_page_id = page['id']
                self._refresh_page_list()
                self._load_tasks()
                self.save_settings()
            except Exception as e:
                ModernDialogs.show_message(self, "Import Error", f"Failed to import: {e}", theme=self.current_theme)
                
        elif action == "create":
            page = self.task_manager.add_page(page_name)
            self.active_page_id = page['id']
            self._refresh_page_list()
            self.task_manager.synchronize_task_statuses()
            self._load_tasks()
            self.save_settings()
    
    def _on_page_rename(self, page_id, _unused):
        """Rename a page via input dialog"""
        current_name = ""
        for p in self.task_manager.get_pages():
            if p['id'] == page_id:
                current_name = p['name']
                break
        
        new_name, ok = ModernDialogs.get_text(
            self, "Rename Page", "New name:", default_text=current_name, theme=self.current_theme
        )
        if ok and new_name.strip():
            self.task_manager.rename_page(page_id, new_name.strip())
            self._refresh_page_list()
    
    def _on_page_delete(self, page_id):
        """Delete a page after confirmation"""
        # Don't allow deleting the last page
        pages = self.task_manager.get_pages()
        if len(pages) <= 1:
            ModernDialogs.show_message(self, "Delete Page", "Can't delete the last page.", theme=self.current_theme)
            return
        
        page_name = ""
        for p in pages:
            if p['id'] == page_id:
                page_name = p['name']
                break
        
        if not ModernDialogs.ask_yes_no(
            self, "Delete Page",
            f"Delete '{page_name}' and all its tasks?\nThis cannot be undone.",
            theme=self.current_theme, is_danger=True
        ):
            return
        
        self.task_manager.delete_page(page_id)
        
        # If we deleted the active page, switch to the first one
        if self.active_page_id == page_id:
            self.active_page_id = self.task_manager.get_default_page_id()
        
        self._refresh_page_list()
        self.task_manager.synchronize_task_statuses()
        self._load_tasks()
        self.save_settings()
        
    def _on_page_reordered(self, new_order):
        """Handle drag-and-drop page reordering"""
        self.task_manager.reorder_pages(new_order)
        self._refresh_page_list()
    
    def _export_page(self, page_id):
        """Export a specific page's tasks to Share ID"""
        page_tasks = self.task_manager.get_tasks(page_id=page_id)
        
        # Get page name
        page_name = "Routine"
        for p in self.task_manager.get_pages():
            if p['id'] == page_id:
                page_name = p['name']
                break
        
        # BUG-16 FIX: Filter by is_synced flag and global_ ID prefix, NOT by task name.
        # The old name-based filter silently dropped any custom task coincidentally
        # named after a prayer (e.g. "Fajr meditation").
        shareable_tasks = [
            t for t in page_tasks
            if not t.get('is_synced', False) and not str(t.get('id', '')).startswith('global_')
        ]
        
        if not shareable_tasks:
            ModernDialogs.show_message(self, "Export", "No custom tasks to export on this page!", theme=self.current_theme)
            return
            
        try:
            share_id = share_handler.encode_tasks(shareable_tasks, page_name=page_name)
            QApplication.clipboard().setText(share_id)
            self.sidebar.show_copy_feedback(page_id)
            
            try:
                from plyer import notification
                notification.notify(
                    title="Daily Tasks",
                    message=f"Share ID for '{page_name}' copied!",
                    app_name="Daily Tasks",
                    timeout=3
                )
            except Exception:
                pass
        except Exception as e:
            ModernDialogs.show_message(self, "Export Error", f"Failed to encode: {e}", theme=self.current_theme)
    
    def _on_page_mute_toggle(self, page_id):
        """Toggle mute for a page"""
        new_mute = self.task_manager.toggle_mute(page_id)
        self.sidebar.update_page_mute(page_id, new_mute)
        self._update_app_icon()
            
    def _edit_task(self, task):
        """Open dialog to edit task"""
        dialog = AddTaskDialog(self, task_data=task, icon_categories=ICON_CATEGORIES, theme=self.current_theme)
        dialog.apply_theme(self.current_theme)
        try:
            result = dialog.exec()
            if result == 1:  # Accepted (Save)
                data = dialog.get_task_data()
                self._on_task_save(
                    data['name'], data['start_time'], data['end_time'], 
                    data.get('repeat_days'), data.get('image_path'), task['id']
                )
            elif result == 2:  # Delete
                self._delete_task(task)
        finally:
            dialog.deleteLater()
            
    def _delete_task(self, task):
        """Handle task deletion"""
        confirm = ModernDialogs.confirm(
            self, "Delete Task", 
            f"Are you sure you want to delete '{task['name']}'?",
            theme=self.current_theme
        )
        if confirm:
            self.task_manager.delete_task(task['id'])

            # Structural change (task count changed): do a full reload
            self.task_manager.synchronize_task_statuses()
            self._load_tasks()
            self._update_app_icon()
        
    def _on_task_save(self, name, start, end, repeat, iconsrc, task_id):
        """Handle task save from dialog"""
        if task_id:
            # Edit existing
            self.task_manager.update_task_details(task_id, name, start, end, iconsrc, repeat)
        else:
            # Add new
            self.task_manager.add_task(name, start, end, iconsrc, repeat_days=repeat, page_id=self.active_page_id)
            
        # Structural change: full reload needed
        self.task_manager.synchronize_task_statuses()
        self._load_tasks()
        self._update_app_icon()
        
    def _toggle_dnd(self, enabled):
        """Toggle Do Not Disturb mode"""
        self.dnd_enabled = bool(enabled)
        self.sound_manager.set_dnd(self.dnd_enabled)
        
        if self.dnd_enabled:
            self._stop_flashing()

        if self._settings_panel is not None:
            cb = self._settings_panel.dnd_checkbox.checkbox
            if cb.isChecked() != self.dnd_enabled:
                cb.blockSignals(True)
                cb.setChecked(self.dnd_enabled)
                cb.blockSignals(False)
                self._settings_panel._update_checkbox_visual(cb, self.dnd_enabled)
            self._settings_panel._update_volume_visibility(animate=self._settings_panel.isVisible())
            
        self._update_app_icon()
        self.save_settings()

    def _toggle_ui_sounds(self, enabled):
        """Toggle interactive UI sound effects (hover, click, typing) independently of task alerts."""
        self.ui_sounds_enabled = bool(enabled)
        self.sound_manager.set_ui_sounds_enabled(self.ui_sounds_enabled)
        if self.ui_sounds_enabled:
            self.sound_manager.play_click()
        if self._settings_panel is not None:
            cb = self._settings_panel.ui_sounds_checkbox.checkbox
            if cb.isChecked() != self.ui_sounds_enabled:
                cb.blockSignals(True)
                cb.setChecked(self.ui_sounds_enabled)
                cb.blockSignals(False)
                self._settings_panel._update_checkbox_visual(cb, self.ui_sounds_enabled)
            self._settings_panel._update_volume_visibility(animate=self._settings_panel.isVisible())
        self.save_settings()

    def _on_ui_volume_changed(self, volume):
        """Adjust interactive UI sound volume (0-100%) independently of task alerts."""
        self.ui_volume = max(0, min(100, int(volume)))
        self.sound_manager.set_ui_volume(self.ui_volume)
        if not hasattr(self, '_vol_save_timer') or self._vol_save_timer is None:
            self._vol_save_timer = QTimer(self)
            self._vol_save_timer.setSingleShot(True)
            self._vol_save_timer.timeout.connect(self.save_settings)
        self._vol_save_timer.start(250)
        
    def _sync_prayers_background(self, silent=False):
        """Synchronize prayer times in a background worker thread (deduplicated)."""
        if getattr(self, '_prayer_loading', False):
            return
        self._silent_prayer_sync = silent
        self._prayer_loading = True
        if self._settings_panel is not None:
            self._settings_panel.set_prayer_loading(True)

        def sync():
            try:
                success = self.task_manager.sync_prayer_times()
                self.prayer_sync_finished.emit(success)
            except Exception as e:
                print(f"Prayer sync failed: {e}")
                self.prayer_sync_finished.emit(False)

        threading.Thread(target=sync, daemon=True).start()


    def _toggle_prayer_mode(self, enabled):
        """Toggle prayer times feature"""
        self.prayer_mode_enabled = enabled
        if enabled:
            self.save_settings()
            self._sync_prayers_background(silent=False)
        else:
            try:
                # Remove synced tasks
                self.task_manager.remove_synced_tasks()
                self.task_manager.synchronize_task_statuses()
                self._load_tasks()
                self.save_settings()
            except Exception as e:
                print(f"Error disabling prayer mode: {e}")
                pass
            
    def _post_prayer_sync(self, success):
        """Handle prayer sync completion"""
        self._prayer_loading = False
        if self._settings_panel is not None:
            self._settings_panel.set_prayer_loading(False)
            self.prayer_mode_enabled = self._settings_panel.prayer_checkbox.checkbox.isChecked()
        
        silent = getattr(self, '_silent_prayer_sync', False)
        self._silent_prayer_sync = False

        # Check if user disabled it while we were syncing
        if not self.prayer_mode_enabled:
            self.task_manager.remove_synced_tasks()
            self._load_tasks()
            return
            
        if success:
            changed = getattr(self.task_manager, 'last_prayer_sync_changed', True)
            if changed or not silent:
                self.task_manager.synchronize_task_statuses()
                self._load_tasks()
            if not silent and not getattr(self, '_prayer_synced_once', False):
                self._send_notification("Daily Tasks", "Prayer Timers synced successfully!")
            self._prayer_synced_once = True
        else:
            if not silent:
                self._send_notification("Sync Issue", "Could not update prayer times. Using cached data.")
                self.task_manager.synchronize_task_statuses()
                self._load_tasks()
        
    def _toggle_simple_mode(self, enabled):
        """Toggle simple mode (disable particles and animations)"""
        self.simple_mode_enabled = enabled
        self.particles.set_simple_mode(enabled)
        self.save_settings()
        
        # Propagate to all TaskCards
        for card in self.task_cards.values():
            card.set_animations_enabled(not enabled)

    def _toggle_hide_non_today(self, enabled):
        """Toggle hiding tasks that are not scheduled for today"""
        self.hide_non_today_enabled = bool(enabled)
        self._load_tasks()
        self.save_settings()
            
    def _toggle_hardcore_mode(self, enabled):
        """Toggle hardcore mode"""
        self.hardcore_mode_enabled = enabled
        self.save_settings()
        
    def _monitor_task_states(self, changes):
        """
        BUG-01 / OPT-01 FIX: Handle monitoring actions (sounds, notifications,
        urgent flashing) based on transitions already computed by
        synchronize_task_statuses. Does NOT re-compute statuses.
        """
        now = datetime.now()
        has_active = False
        has_urgent = False

        # 1. Trigger transition events (sounds, notifications) for non-muted tasks
        for task, old_status, new_status in changes:
            if self.task_manager.is_task_on_muted_page(task.get('id', '')):
                continue
            if self.dnd_enabled:
                continue

            if old_status == 'pending' and new_status == 'active' and task.get('start_time'):
                self._send_notification(f"Task Started: {task['name']}", "It's time!")
                self.sound_manager.play_start()
            elif old_status == 'active' and new_status == 'failed':
                self.sound_manager.play_fail()

        # 2. Scan current monitoring tasks for active/urgent state (read-only)
        now_secs = now.hour * 3600 + now.minute * 60 + now.second
        for task in self.task_manager.get_tasks_for_monitoring():
            if not task.get('enabled', True):
                continue

            status = task.get('status', 'pending')
            tid = str(task.get('id', ''))

            if status != 'active':
                # Stop any stale flash animation on non-active cards
                if tid in self.task_cards:
                    self.task_cards[tid].stop_flashing()
                continue

            has_active = True

            start_str = task.get('start_time')
            end_str = task.get('end_time')
            if start_str and end_str:
                try:
                    s_secs = _parse_hhmm_to_secs(start_str)
                    e_secs = _parse_hhmm_to_secs(end_str)
                except ValueError:
                    s_secs = None
                    e_secs = None
            else:
                s_secs = None
                e_secs = None

            if s_secs is not None and e_secs is not None:
                if e_secs < s_secs:
                    if now.hour < 12:
                        s_secs -= 86400
                    else:
                        e_secs += 86400

                rem_secs = e_secs - now_secs
                if 0 < rem_secs < 1800:
                    has_urgent = True
                    if tid in self.task_cards:
                        self.task_cards[tid].start_urgent_flashing()
                    if tid not in self._flashed_urgent_tasks:
                        if not self.dnd_enabled:
                            self._flash_window()
                        self._flashed_urgent_tasks.add(tid)
                else:
                    if tid in self.task_cards:
                        self.task_cards[tid].stop_flashing()
                        self.task_cards[tid].start_active_pulse()
            else:
                if tid in self.task_cards:
                    self.task_cards[tid].stop_flashing()
                    self.task_cards[tid].start_active_pulse()

        # 3. Batch flash logic: flash once when first active task appears
        if has_active:
            if not self._has_flashed_batch:
                if not self.dnd_enabled:
                    self._flash_window()
                self._has_flashed_batch = True
                self._update_app_icon()
        else:
            self._has_flashed_batch = False

        return has_active, has_urgent

    def _update_cards_incremental(self, changed_ids):
        """
        BUG-04 / OPT-04 FIX: Update only specific task cards without rebuilding
        the entire grid. Falls back to _load_tasks only if a card is missing.
        """
        if not changed_ids:
            return

        all_tasks = self.task_manager.get_tasks(page_id=self.active_page_id)
        if getattr(self, 'hide_non_today_enabled', False):
            today_weekday = datetime.now().weekday()
            all_tasks = [
                t for t in all_tasks
                if today_weekday in t.get('repeat_days', [0, 1, 2, 3, 4, 5, 6])
                and t.get('status') != 'disabled'
            ]
        task_map = {str(t['id']): t for t in all_tasks}

        for tid in changed_ids:
            if tid in self.task_cards:
                if tid in task_map:
                    self.task_cards[tid].update_content(task_map[tid])
                else:
                    # Task disappeared from active page (e.g. prayer removed) — full reload
                    self._load_tasks()
                    return
            elif tid in task_map:
                self._load_tasks()
                return

        self._update_app_icon()

    def _schedule_next_tick(self):
        """Schedule singleShot update_timer for the exact next minute boundary (eliminates 1s polling)."""
        if getattr(self, 'update_timer', None) is None:
            return
        now = datetime.now()
        ms_into_minute = (now.second * 1000) + (now.microsecond // 1000)
        delay_ms = max(1000, min(60050, 60025 - ms_into_minute))
        self.update_timer.start(int(delay_ms))

    def _update_loop(self):
        """Precision minute-boundary update for task statuses with sleep/wake and clock-jump resilience."""
        try:
            now_wall = time.time()
            now_mono = time.monotonic()
            wall_delta = now_wall - getattr(self, '_last_tick_wall', now_wall)
            mono_delta = now_mono - getattr(self, '_last_tick_mono', now_mono)
            self._last_tick_wall = now_wall
            self._last_tick_mono = now_mono

            # Detect system standby/hibernation wake, manual clock change, or DST/timezone shift
            if wall_delta > 75.0 or wall_delta < -1.0 or abs(wall_delta - mono_delta) > 5.0:
                self._on_system_resume_or_time_change()
                return

            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # 1. Daily Reset Check
            if today_str != self.current_date_str:
                self.current_date_str = today_str
                self._last_opened_date = today_str
                self._flashed_urgent_tasks.clear()
                self.task_manager.reset_daily_tasks()
                if not self.dnd_enabled:
                    self.sound_manager.play_start()
                if self.prayer_mode_enabled:
                    self._sync_prayers_background(silent=True)
                self._load_tasks()
                self.save_settings()
                return

            # 2. Single-pass status synchronization
            sync_modified, changes = self.task_manager.synchronize_task_statuses()

            # 3. Handle sound / notification / flash side-effects for transitions
            self._monitor_task_states(changes)

            # 4. Incremental card refresh
            if sync_modified:
                changed_ids = {str(t['id']) for t, _, _ in changes}
                self._update_cards_incremental(changed_ids)
        except Exception as e:
            print(f"Update loop recovery warning: {e}")
        finally:
            self._schedule_next_tick()

    def _on_system_resume_or_time_change(self):
        """Recover cleanly from Windows Sleep/Hibernate or system clock/timezone/DST changes."""
        try:
            self._last_tick_wall = time.time()
            self._last_tick_mono = time.monotonic()

            # Reconnect audio output handles in case audio endpoint reset across sleep
            if hasattr(self, 'sound_manager') and self.sound_manager is not None:
                self.sound_manager.reset_audio_devices()

            today_str = datetime.now().strftime("%Y-%m-%d")
            if today_str != self.current_date_str:
                self.current_date_str = today_str
                self._last_opened_date = today_str
                self._flashed_urgent_tasks.clear()
                self.task_manager.reset_daily_tasks()
                if not self.dnd_enabled:
                    self.sound_manager.play_start()
                if self.prayer_mode_enabled:
                    self._sync_prayers_background(silent=True)
                self._load_tasks()
                self.save_settings()
            else:
                sync_modified, changes = self.task_manager.synchronize_task_statuses()
                self._monitor_task_states(changes)
                self._load_tasks()
                self._update_app_icon()
        except Exception as e:
            print(f"System resume recovery warning: {e}")
        finally:
            self._schedule_next_tick()

    def _re_register_tray_icon(self):
        """Re-register system tray icon when Windows Explorer (explorer.exe) restarts."""
        try:
            if self.tray_icon is not None:
                self.tray_icon.hide()
                self.tray_icon.show()
                self._last_badge_cache_key = None
                self._update_app_icon()
        except Exception as e:
            print(f"Tray re-registration warning: {e}")

    def nativeEvent(self, eventType, message):
        """Intercept Win32 power-resume, time-change, and Explorer taskbar-recreated messages."""
        try:
            if message:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                # WM_POWERBROADCAST (0x0218): PBT_APMRESUMECRITICAL(0x06), PBT_APMRESUMESUSPEND(0x07), PBT_APMRESUMEAUTOMATIC(0x12)
                if msg.message == 0x0218 and msg.wParam in (0x0006, 0x0007, 0x0012):
                    QTimer.singleShot(250, self._on_system_resume_or_time_change)
                # WM_TIMECHANGE (0x001E): System clock, DST, or timezone changed
                elif msg.message == 0x001E:
                    QTimer.singleShot(150, self._on_system_resume_or_time_change)
                # TaskbarCreated: explorer.exe restarted
                elif self._wm_taskbar_created and msg.message == self._wm_taskbar_created:
                    QTimer.singleShot(300, self._re_register_tray_icon)
        except Exception:
            pass
        return super().nativeEvent(eventType, message)


    def _send_notification(self, title, message):
        """Send Windows notification"""
        if self.dnd_enabled:
            return
            
        # Flash taskbar
        self._flash_window()
        
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name="Daily Tasks",
                timeout=10
            )
        except Exception as e:
            print(f"Notification failed: {e}")
                
    def _flash_window(self):
        """Flash window in taskbar (Continuous until focused)"""
        if self.dnd_enabled:
            return

        try:
            # BUG-02 FIX: Use module-level _FLASHWINFO struct (defined once, not per-call)
            hwnd = int(self.winId())
            finfo = _FLASHWINFO()
            finfo.cbSize = ctypes.sizeof(_FLASHWINFO)
            finfo.hwnd = hwnd
            finfo.dwFlags = _FLASHW_ALL | _FLASHW_TIMER
            finfo.uCount = 0  # Flash until stopped
            finfo.dwTimeout = 0
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(finfo))
        except Exception as e:
            print(f"Flash failed: {e}")

    def _stop_flashing(self):
        """Stop window flashing"""
        try:
            # BUG-02 FIX: Use module-level _FLASHWINFO struct
            hwnd = int(self.winId())
            finfo = _FLASHWINFO()
            finfo.cbSize = ctypes.sizeof(_FLASHWINFO)
            finfo.hwnd = hwnd
            finfo.dwFlags = _FLASHW_STOP
            finfo.uCount = 0
            finfo.dwTimeout = 0
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(finfo))
        except Exception:
            pass

    def changeEvent(self, event):
        """Detect window activation to stop flashing and manage particle timer on minimize/restore"""
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                self._stop_flashing()
                # Consider user 'notified' if they viewed the app
                self._has_flashed_batch = True
                if hasattr(self, 'particles') and not self.isMinimized() and self.isVisible():
                    self.particles.start(fps=60)
        
        elif event.type() == QEvent.WindowStateChange:
            if hasattr(self, 'title_bar'):
                self.title_bar.update_max_button_icon(self.isMaximized())
            if self.isMinimized():
                # Stop particles to save CPU when minimized
                if hasattr(self, 'particles'):
                    self.particles.stop()
            else:
                # Restart particles when restored
                if hasattr(self, 'particles') and self.isVisible():
                    self.particles.start(fps=60)
        super().changeEvent(event)

    def hideEvent(self, event):
        """Immediately halt background particle timer when window is hidden to tray."""
        if hasattr(self, 'particles') and self.particles is not None:
            self.particles.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Resume particles when window is shown and active."""
        if hasattr(self, 'particles') and self.particles is not None and not self.isMinimized():
            self.particles.start(fps=60)
        super().showEvent(event)
            
    def _update_app_icon(self):
        """Update app icon with badge count (debounced)"""
        if self._icon_update_scheduled:
            return
        self._icon_update_scheduled = True
        QTimer.singleShot(200, self._perform_icon_update)
        
    def _perform_icon_update(self):
        """Actually update the app icon using cached 128x128 pixmap and badge cache"""
        self._icon_update_scheduled = False
        
        try:
            base_pix = self._get_base_icon_pixmap()
            if base_pix.isNull():
                return
                
            # Count active tasks
            active_count = 0
            now = datetime.now()
            weekday = now.weekday()
            if not self.dnd_enabled:
                for t in self.task_manager.get_tasks_for_monitoring():
                    # Skip Ghost Tasks
                    if weekday not in t.get('repeat_days', [0,1,2,3,4,5,6]):
                        continue
                        
                    if t.get('status') == 'active':
                        active_count += 1
                        
            cache_key = (active_count, self.dnd_enabled)
            if getattr(self, '_last_badge_cache_key', None) == cache_key:
                return
            self._last_badge_cache_key = cache_key
            self.last_badge_count = active_count

            if active_count > 0:
                self.setWindowTitle(f"({active_count}) Daily Tasks (V2.5 - New Engine)")
            else:
                self.setWindowTitle("Daily Tasks (V2.5 - New Engine)")

            icon = self._badge_icon_cache.get(cache_key)
            if icon is None:
                if active_count > 0:
                    pixmap = base_pix.copy()
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    
                    w = pixmap.width()
                    h = pixmap.height()
                    badge_size = int(w * 0.45)
                    x0 = w - badge_size
                    y0 = h - badge_size
                    
                    painter.setBrush(QColor("#D32F2F"))
                    painter.setPen(QPen(Qt.white, max(1, int(w * 0.02))))
                    painter.drawEllipse(x0, y0, badge_size, badge_size)
                    
                    painter.setPen(Qt.white)
                    font = QFont("Arial", int(badge_size * 0.55), QFont.Bold)
                    painter.setFont(font)
                    painter.drawText(QRectF(x0, y0, badge_size, badge_size), Qt.AlignCenter, str(active_count))
                    painter.end()
                    icon = QIcon(pixmap)
                else:
                    icon = QIcon(base_pix)
                if len(self._badge_icon_cache) >= 16:
                    self._badge_icon_cache.clear()
                self._badge_icon_cache[cache_key] = icon
            
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)
            
            if self.tray_icon:
                self.tray_icon.setIcon(icon)
                self.tray_icon.setToolTip(f"Daily Tasks ({active_count} active)" if active_count > 0 else "Daily Tasks")
            
        except Exception as e:
            print(f"Badge update failed: {e}")
            
    def load_settings(self):
        """Load user preferences safely with re-entrancy guard and backup fallback."""
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.settings_dir = os.path.join(appdata, 'DailyTasks')
        self.settings_path = os.path.join(self.settings_dir, "settings.json")
        
        self._loading_settings = True
        try:
            settings = self._read_settings_dict()
            if settings is None:
                return
                
            dnd = bool(settings.get('dnd_enabled', False))
            prayer = bool(settings.get('prayer_mode_enabled', False))
            simple = bool(settings.get('simple_mode_enabled', False))
            hide_non_today = bool(settings.get('hide_non_today_enabled', False))
            hardcore = bool(settings.get('hardcore_mode_enabled', False))
            ui_sounds = bool(settings.get('ui_sounds_enabled', True))
            try:
                ui_vol = max(0, min(100, int(settings.get('ui_volume', 80))))
            except (ValueError, TypeError):
                ui_vol = 80
            theme = settings.get('theme', 'dark') or 'dark'
            
            self.dnd_enabled = dnd
            self.prayer_mode_enabled = prayer
            self.simple_mode_enabled = simple
            self.hide_non_today_enabled = hide_non_today
            self.hardcore_mode_enabled = hardcore
            self.ui_sounds_enabled = ui_sounds
            self.ui_volume = ui_vol
            self.current_theme = theme
            self.sound_manager.set_ui_sounds_enabled(ui_sounds)
            self.sound_manager.set_ui_volume(ui_vol)

            if self._settings_panel is not None:
                self._settings_panel._set_theme(theme)
                self._settings_panel.set_values(
                    dnd, prayer, simple, hardcore, ui_sounds, ui_vol, hide_non_today
                )
            self._apply_theme(theme, save=False)
            
            self._initial_scroll_pos = settings.get('scroll_position', 0)
            
            saved_page = settings.get('active_page_id')
            if saved_page and self.task_manager._find_page(saved_page):
                self.active_page_id = saved_page
            
            today_str = datetime.now().strftime("%Y-%m-%d")
            last_date = settings.get('last_opened_date', today_str) 
            
            if last_date != today_str:
                self.task_manager.reset_daily_tasks()
                
            self.task_manager.synchronize_task_statuses()
                
            self._last_opened_date = today_str
            
            if dnd:
                self._toggle_dnd(True)
            if simple:
                self._toggle_simple_mode(True)
            if hardcore:
                self._toggle_hardcore_mode(True)
            if prayer:
                self._toggle_prayer_mode(True)
            else:
                self.task_manager.remove_synced_tasks()
                self._load_tasks()
        except Exception as e:
            print(f"Load settings warning: {e}")
        finally:
            self._loading_settings = False
        self.save_settings()
            
    def _update_settings_pos(self):
        """Anchor settings panel above the settings button (Robust Global Mapping)"""
        try:
            if not hasattr(self, 'sidebar') or not hasattr(self.sidebar, 'settings_btn'):
                return
            panel = self._ensure_settings_panel()
                
            # 1. Get Button's Global Position
            btn_global = self.sidebar.settings_btn.mapToGlobal(QPoint(0, 0))
            
            # 2. Convert to Panel's Parent Coordinates (central widget)
            parent = panel.parent()
            if not parent:
                parent = self # Fallback
                
            target_pos = parent.mapFromGlobal(btn_global)
            
            # 3. Calculate Target X,Y (anchor top edge using expanded reference height so items never shift)
            ref_h = getattr(panel, '_EXPANDED_HEIGHT', panel.height())
            x = target_pos.x() + 10
            y = target_pos.y() - ref_h - 10
            
            # 4. Clamp to safe area (Title bar ~40px)
            if y < 40: y = 40
            
            panel.move(x, y)
        except Exception as e:
            print(f"Error positioning settings: {e}")
            panel = self._ensure_settings_panel()
            x = (self.width() - panel.width()) // 2
            y = (self.height() - panel.height()) // 2
            panel.move(x, y)

    def _toggle_settings_panel(self):
        """Show/hide settings panel"""
        panel = self._ensure_settings_panel()
        if panel.isVisible():
            panel.hide()
        else:
            self._update_settings_pos()
            panel.show()
            panel.raise_()
            
    def _apply_theme(self, theme, save=True):
        """Apply theme globally across all 10 themes"""
        spec = get_theme_spec(theme)
        ar, ag, ab = spec['accent_rgb']
        self.current_theme = theme if theme in dict(THEME_OPTIONS) else "dark"
        if save:
            self.save_settings()
        
        bg_gradient = spec['window_bg']
        if spec['is_light']:
            scroll_bg = "rgba(148, 163, 184, 90)"
            scroll_handle = f"rgba({ar}, {ag}, {ab}, 135)"
            scroll_hover = spec['accent']
        else:
            scroll_bg = "rgba(0, 0, 0, 115)"
            scroll_handle = f"rgba({ar}, {ag}, {ab}, 95)"
            scroll_hover = spec['accent']
        QApplication.instance().setStyleSheet(_build_global_theme_css(spec))
            
        # Update central widget
        self.centralWidget().setStyleSheet(f"""
            #CentralWidget {{
                background: {bg_gradient};
            }}
        """)
        
        # Update particles for theme contrast
        if hasattr(self, 'particles') and self.particles is not None:
            self.particles.set_theme(self.current_theme)
        
        # Update sidebar
        self.sidebar.apply_theme(self.current_theme)
        if self._settings_panel is not None:
            self._settings_panel.apply_theme(self.current_theme)
        
        # Update scroll area
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: {scroll_bg};
                width: 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                min-height: 28px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scroll_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: {scroll_bg};
                height: 8px;
                margin: 2px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scroll_handle};
                min-width: 28px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {scroll_hover};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                background: transparent;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
        """)
        
        # Update task cards and (+) add card
        for card in self.task_cards.values():
            card.apply_theme(self.current_theme)
        self._apply_add_card_theme()
        
        # Update title bar
        self.title_bar.apply_theme(self.current_theme)

    def _ensure_startup(self):
        """Enforce startup registry key and clean up any stale legacy key."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            
            app_name = "Daily Tasks"
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
                cmd = f'"{exe_path}"'
            else:
                script = os.path.abspath(sys.argv[0])
                py_exe = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.exists(py_exe):
                    py_exe = sys.executable
                cmd = f'"{py_exe}" "{script}"'
                
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            # Remove legacy "DailyTasks" (no space) key if present so Windows doesn't launch duplicate/missing paths
            try:
                winreg.DeleteValue(key, "DailyTasks")
            except OSError:
                pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Startup registration failed: {e}")

    def _flush_settings_worker(self):
        """Single serialized worker thread that writes coalesced settings snapshots atomically."""
        import shutil
        while True:
            with self._settings_save_lock:
                snapshot = self._pending_settings_snapshot
                self._pending_settings_snapshot = None
                if snapshot is None:
                    self._settings_writer_active = False
                    return

            tmp_path = f"{self.settings_path}.{threading.get_ident()}.tmp"
            bak_path = self.settings_path + ".bak"
            try:
                os.makedirs(self.settings_dir, exist_ok=True)
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(snapshot, f, separators=(',', ':'))
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
                if os.path.exists(self.settings_path):
                    try:
                        if os.path.getsize(self.settings_path) > 2:
                            shutil.copy2(self.settings_path, bak_path)
                    except OSError:
                        pass
                for attempt in range(4):
                    try:
                        os.replace(tmp_path, self.settings_path)
                        break
                    except PermissionError:
                        if attempt == 3:
                            raise
                        time.sleep(0.015)
            except Exception as e:
                print(f"Failed to save settings: {e}")
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass


    def save_settings(self):
        """Save user preferences using a coalesced atomic writer (no thread accumulation)."""
        if getattr(self, '_loading_settings', False):
            return

        try:
            prayer_enabled = (
                self._settings_panel.prayer_checkbox.checkbox.isChecked()
                if self._settings_panel is not None
                else self.prayer_mode_enabled
            )
            scroll_val = (
                self.scroll.verticalScrollBar().value()
                if hasattr(self, 'scroll') and self.scroll is not None
                else 0
            )
            settings = {
                'dnd_enabled': self.dnd_enabled,
                'simple_mode_enabled': self.simple_mode_enabled,
                'hide_non_today_enabled': getattr(self, 'hide_non_today_enabled', False),
                'prayer_mode_enabled': prayer_enabled,
                'hardcore_mode_enabled': self.hardcore_mode_enabled,
                'ui_sounds_enabled': getattr(self, 'ui_sounds_enabled', True),
                'ui_volume': getattr(self, 'ui_volume', 80),
                'theme': self.current_theme,
                'scroll_position': scroll_val,
                'last_opened_date': getattr(self, '_last_opened_date', datetime.now().strftime("%Y-%m-%d")),
                'active_page_id': self.active_page_id
            }

            with self._settings_save_lock:
                self._pending_settings_snapshot = settings
                if not self._settings_writer_active:
                    self._settings_writer_active = True
                    threading.Thread(target=self._flush_settings_worker, daemon=True).start()
        except Exception as e:
            print(f"Failed to prepare settings: {e}")
            
    def _setup_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Set tray icon from cached 128x128 pixmap
        base_pix = self._get_base_icon_pixmap()
        if not base_pix.isNull():
            self.tray_icon.setIcon(self.windowIcon() if not self.windowIcon().isNull() else QIcon(base_pix))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        
        self.tray_icon.setToolTip("Daily Tasks")
        
        # Context Menu
        tray_menu = QMenu()
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(self._restore_window)
        tray_menu.addAction(open_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._force_quit)
        tray_menu.addAction(quit_action)
        
        # Style the menu manually to match app
        spec = get_theme_spec(self.current_theme)
        tray_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {spec['dialog_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['input_border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 22px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background-color: {spec['accent_primary']};
                color: #FFFFFF;
            }}
        """)
        
        self.tray_menu = tray_menu
        # Note: We handle context menu manually in activated() to ensure correct positioning
        # self.tray_icon.setContextMenu(tray_menu)
        
        self.tray_icon.activated.connect(self._tray_icon_activated)
        self.tray_icon.show()
        
    def _tray_icon_activated(self, reason):
        """Handle tray icon click"""
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._restore_window()
        elif reason == QSystemTrayIcon.DoubleClick:
            self._restore_window()
        elif reason == QSystemTrayIcon.Context:
            self.tray_menu.setWindowFlags(self.tray_menu.windowFlags() | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            self.tray_menu.setAttribute(Qt.WA_ShowWithoutActivating)

            # BUG-15 FIX: Position menu correctly regardless of taskbar edge.
            # Old code assumed bottom taskbar and always subtracted height.
            # Now we clamp to the available screen geometry.
            self.tray_menu.adjustSize()
            cursor_pos = QCursor.pos()
            menu_w = self.tray_menu.sizeHint().width()
            menu_h = self.tray_menu.sizeHint().height()

            screen = QApplication.screenAt(cursor_pos)
            if screen is None:
                screen = QApplication.primaryScreen()
            avail = screen.availableGeometry()

            # Prefer opening upward; fall back to below if not enough space
            x = max(avail.left(), min(cursor_pos.x(), avail.right() - menu_w))
            if cursor_pos.y() - menu_h >= avail.top():
                y = cursor_pos.y() - menu_h  # Above cursor
            else:
                y = cursor_pos.y()            # Below cursor (top taskbar)

            self.tray_menu.exec(QPoint(x, y))
                


    def _restore_window(self):
        """Robust restore from tray with Win32 foreground enforcement"""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            hwnd = ctypes.c_void_p(int(self.winId()))
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(hwnd, 5)  # SW_SHOW

            fg_hwnd = user32.GetForegroundWindow()
            fg_thread = user32.GetWindowThreadProcessId(ctypes.c_void_p(fg_hwnd), None) if fg_hwnd else 0
            cur_thread = kernel32.GetCurrentThreadId()
            attached = False
            if fg_thread and fg_thread != cur_thread:
                attached = bool(user32.AttachThreadInput(fg_thread, cur_thread, True))
            try:
                flags = 0x0001 | 0x0002 | 0x0040  # SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
                user32.SetWindowPos(hwnd, ctypes.c_void_p(-1), 0, 0, 0, 0, flags)  # HWND_TOPMOST
                user32.SetWindowPos(hwnd, ctypes.c_void_p(-2), 0, 0, 0, 0, flags)  # HWND_NOTOPMOST
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    user32.AttachThreadInput(fg_thread, cur_thread, False)
        except Exception:
            pass
        self.raise_()
        self.activateWindow()
                
    def closeEvent(self, event):
        """Minimize to tray on close, save settings first"""
        self.save_settings()
        
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
        else:
            event.accept()
            QApplication.quit()
        
    def _force_quit(self):
        """Clean shutdown releasing timers, audio handles, and tray icon."""
        try:
            self.save_settings()
        except Exception:
            pass
        if hasattr(self, 'update_timer') and self.update_timer is not None:
            self.update_timer.stop()
        if hasattr(self, 'particles') and self.particles is not None:
            self.particles.stop()  # Stop particle timer to prevent background CPU burn
        if hasattr(self, 'sound_manager') and self.sound_manager is not None:
            self.sound_manager.close()
        if self.tray_icon:
            self.tray_icon.hide()  # Remove icon from tray
        QApplication.quit()


# ═══════════════════════════════════════════════════════════
# NUCLEAR UI FIX: GLOBAL MENU FILTER
# ═══════════════════════════════════════════════════════════
class GlobalMenuFilter(QObject):
    """
    Intercepts every QMenu and QDialog as it is created/shown to:
    1. Force-disable WA_TranslucentBackground (The inheritance bug)
    2. Force opaque palette and solid background
    3. Apply theme colors to native Windows dialog title bars via DWM
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show:
            if isinstance(obj, QDialog):
                try:
                    theme = getattr(obj, 'current_theme', None)
                    if not theme:
                        for top_level in QApplication.topLevelWidgets():
                            if hasattr(top_level, 'current_theme') and not isinstance(top_level, QDialog):
                                theme = getattr(top_level, 'current_theme', 'dark')
                                break
                    apply_window_theme_frame(obj, theme or 'dark')
                except Exception:
                    pass
            elif isinstance(obj, QMenu):
                try:
                    # 1. Disable translucency inherited from parent
                    obj.setAttribute(Qt.WA_TranslucentBackground, False)
                    obj.setAttribute(Qt.WA_NoSystemBackground, False)
                    obj.setAutoFillBackground(True)
                    
                    # 2. Logic to find the current active theme globally
                    main_win = None
                    for top_level in QApplication.topLevelWidgets():
                        if hasattr(top_level, 'current_theme') and not isinstance(top_level, QDialog):
                            main_win = top_level
                            break
                    theme = getattr(main_win, 'current_theme', 'dark') if main_win else 'dark'
                    spec = get_theme_spec(theme)
                    
                    # 3. Apply solid palette based on theme
                    palette = obj.palette()
                    bg_color = QColor(spec['dialog_bg'])
                    text_color = QColor(spec['text_main'])
                    
                    palette.setColor(obj.backgroundRole(), bg_color)
                    palette.setColor(obj.foregroundRole(), text_color)
                    obj.setPalette(palette)
                    
                    # 4. Final CSS reinforcement
                    border_color = spec['input_border']
                    obj.setStyleSheet(
                        f"QMenu {{ background-color: {bg_color.name()}; color: {text_color.name()}; "
                        f"border: 1px solid {border_color}; border-radius: 8px; padding: 4px; }} "
                        f"QMenu::item {{ padding: 6px 20px; border-radius: 6px; }} "
                        f"QMenu::item:selected {{ background-color: {spec['accent_primary']}; color: #FFFFFF; }}"
                    )
                except Exception:
                    pass
                
        return False

def _install_resilient_excepthook():
    """Install a non-fatal exception hook so transient callback errors are logged without killing the tray app."""
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        try:
            import traceback
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            log_dir = os.path.join(appdata, 'DailyTasks')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'crash_recovery.log')
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n--- {datetime.now().isoformat()} ---\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass
    sys.excepthook = _hook


def run_qt_app():
    """Entry point for the Qt version of the app"""
    _install_resilient_excepthook()
    
    # -------------------------------------------------------------
    # Dynamic Extreme Resolution Scaling Engine
    # -------------------------------------------------------------
    try:
        user32 = ctypes.windll.user32
        # Bypass Windows DPI virtualization to get raw hardware pixels
        user32.SetProcessDPIAware() 
        screen_h = user32.GetSystemMetrics(1)
        
        scale = screen_h / 1080.0
        scale = max(0.65, min(3.0, scale))
        
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(round(scale, 2))
    except Exception as e:
        print(f"Dynamic Scaling failed: {e}")

    # -------------------------------------------------------------
    # Win32: Set AUMID to ensure Taskbar Icon & Grouping work correctly
    # MUST BE DONE BEFORE QAPPLICATION LOADS
    # -------------------------------------------------------------
    try:
        myappid = f'DailyTasks.App.v{APP_VERSION}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"AUMID setup failed: {e}")
        
    # Ensure all menus are rendered by Qt (not native) for full styling control
    QCoreApplication.setAttribute(Qt.AA_DontUseNativeMenuBar)
    
    app = QApplication(sys.argv)
    
    # -------------------------------------------------------------
    # Single Instance IPC Server (Win32 Named Pipe, zero QtNetwork dependency)
    # -------------------------------------------------------------
    ipc_server = _Win32PipeServer(parent=app)
    ipc_server.listen()
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # NUCLEAR UI FIX: Install Global Menu Filter
    # -------------------------------------------------------------
    menu_filter = GlobalMenuFilter(app)
    app.installEventFilter(menu_filter)
    
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Set app-wide font
    app.setFont(QFont("Segoe UI", 10))
    
    # Create and show window
    window = DailyTasksWindow(base_path=base_path)
    if not window.windowIcon().isNull():
        app.setWindowIcon(window.windowIcon())
    window._ipc_server = ipc_server
    ipc_server.activated.connect(window._handle_ipc_activation)
    if ipc_server._pending:
        window._handle_ipc_activation()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run_qt_app()

