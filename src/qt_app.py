"""
Daily Tasks App - PySide6 Version
Full window transparency with particles behind all UI elements
Complete feature parity with original CustomTkinter version
"""

import sys
import os
import json
import ctypes
from ctypes import wintypes
import threading
import math
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QScrollArea, QGridLayout, QFrame, QLabel,
    QSystemTrayIcon, QMenu, QSizePolicy, QGraphicsOpacityEffect
)
from . import share_handler
from PySide6.QtCore import Qt, QTimer, Signal, QCoreApplication, QEvent, QPoint, QObject
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QPainter, QColor, QAction, QCursor, QPen, QBrush
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PIL import Image, ImageDraw, ImageFont
import io

# Windows notification support
try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

from .qt_effects import ParticleBackground
from .qt_components import TaskCard, Sidebar, AddTaskDialog, SettingsPanel, CustomTitleBar, ModernDialogs
from .task_manager import TaskManager
from .sound_manager import SoundManager
from .constants import ICON_CATEGORIES

DARK_THEME_CSS = """
    QWidget {
        color: #ffffff;
        background-color: #0d0d0d;
        font-family: "Roboto";
    }
    
    QComboBox {
        color: #ffffff;
        background-color: #333333;
        border: 1px solid #555555;
        padding: 6px;
        border-radius: 4px;
    }
    QComboBox:hover { border: 1px solid #777777; }
    QComboBox::down-arrow {
        image: none;
        width: 0px; height: 0px;
        margin: 0px;
        border: none;
    }
    QComboBox::drop-down { border: none; width: 0px; }
    QComboBox QAbstractItemView {
        color: #ffffff;
        background-color: #333333;
        border: 1px solid #555555;
        selection-background-color: #555555;
        selection-color: #ffffff;
        outline: none;
    }
    
    QLineEdit {
        color: #ffffff;
        background-color: #333333;
        border: 1px solid #555555;
        padding: 6px;
        border-radius: 4px;
    }
    QLineEdit:focus { border: 1px solid #00BCD4; }
    
    QLabel { color: #ffffff; background-color: transparent; }
    
    QToolTip {
        background-color: #1e1e1e;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 10px;
    }

    
    QScrollBar:vertical {
        background: #2b2b2b; width: 10px; border: none;
    }
    QScrollBar::handle:vertical {
        background: #555555; border-radius: 5px; min-height: 20px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    
    QMenu {
        background-color: #2b2b2b !important;
        color: #ffffff !important;
        border: 1px solid #555555 !important;
        padding: 5px !important;
        border-radius: 6px !important;
    }
    QMenu::item {
        padding: 6px 24px !important;
        background: transparent !important;
        border-radius: 4px !important;
    }
    QMenu::item:selected {
        background-color: #3b3b3b !important;
        color: #ffffff !important;
    }
    QMenu::separator {
        height: 1px !important;
        background: #555555 !important;
        margin: 4px 8px !important;
    }
"""

LIGHT_THEME_CSS = """
    QWidget {
        color: #000000;
        background-color: #F5F5F7;
        font-family: "Roboto";
    }
    
    QComboBox {
        color: #000000;
        background-color: #ffffff;
        border: 1px solid #cccccc;
        padding: 6px;
        border-radius: 4px;
    }
    QComboBox:hover { border: 1px solid #aaaaaa; }
    QComboBox::down-arrow {
        image: none;
        width: 0px; height: 0px;
        margin: 0px;
        border: none;
    }
    QComboBox::drop-down { border: none; width: 0px; }
    QComboBox QAbstractItemView {
        color: #000000;
        background-color: #ffffff;
        border: 1px solid #cccccc;
        selection-background-color: #e0e0e0;
        selection-color: #000000;
        outline: none;
    }
    
    QLineEdit {
        color: #000000;
        background-color: #ffffff;
        border: 1px solid #cccccc;
        padding: 6px;
        border-radius: 4px;
    }
    QLineEdit:focus { border: 1px solid #00BCD4; }
    
    QLabel { color: #000000; background-color: transparent; }
    
    QMenu {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #cccccc !important;
        padding: 5px !important;
        border-radius: 6px !important;
    }
    QMenu::item {
        padding: 6px 24px !important;
        background: transparent !important;
        border-radius: 4px !important;
    }
    QMenu::item:selected {
        background-color: #f0f0f0 !important;
        color: #000000 !important;
    }
    QMenu::separator {
        height: 1px !important;
        background: #cccccc !important;
        margin: 4px 8px !important;
    }
    
    QToolTip {
        background-color: #ffffff;
        color: #000000;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 10px;
    }
    
    QScrollBar:vertical {
        background: #f0f0f0; width: 10px; border: none;
    }
    QScrollBar::handle:vertical {
        background: #bbbbbb; border-radius: 5px; min-height: 20px;
    }
    QScrollBar::handle:vertical:hover { background: #999999; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""

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
        self.hardcore_mode_enabled = False
        self.current_theme = "dark"  # dark or light
        self.task_cards = {}
        self.cols = 4
        self.current_date_str = datetime.now().strftime("%Y-%m-%d")
        self.last_badge_count = -1
        self.active_page_id = self.task_manager.get_default_page_id()
        
        # Settings Storage Paths
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.settings_dir = os.path.join(appdata, 'DailyTasks')
        self.settings_path = os.path.join(self.settings_dir, "settings.json")
        
        # Connect signals
        self.prayer_sync_finished.connect(self._post_prayer_sync)
        
        # Icon path
        self.icon_path = os.path.join(self.base_path, "assets", "icon.png")
        
        # Tray Support
        self.tray_icon = None
        
        self._setup_window()
        self._setup_ui()
        self._load_tasks(animate=False, first_load=True)
        self._update_app_icon()
        
        # Defer non-critical startup operations so main window displays instantly
        QTimer.singleShot(10, self._deferred_startup)
        
    def _deferred_startup(self):
        """Asynchronously initialize system tray, settings, IPC server, and timers after window display"""
        if self.tray_icon is None:
            self._setup_tray()
            
        self._loading_settings = True
        self.load_settings()
        self._loading_settings = False
        
        if not hasattr(self, '_ipc_server') or self._ipc_server is None:
            self._ipc_server = QLocalServer(self)
            self._ipc_server.removeServer("DailyTasksAppIPCV2_5")
            self._ipc_server.listen("DailyTasksAppIPCV2_5")
            self._ipc_server.newConnection.connect(self._handle_ipc_activation)
            
        if not hasattr(self, 'update_timer') or self.update_timer is None:
            self.update_timer = QTimer(self)
            self.update_timer.timeout.connect(self._update_loop)
            self.update_timer.start(1000)
        
    def _handle_ipc_activation(self):
        """Handle activation request from another instance"""
        socket = self._ipc_server.nextPendingConnection()
        socket.close()
        self._restore_window()

        
    def _setup_window(self):
        """Configure the main window"""
        self.setWindowTitle("Daily Tasks (V2.5 - New Engine)")
        
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))
            
        # Dimensions will be dynamically set by _update_window_size during _load_tasks
        # or by user settings later.
        self.cols = 3
        
        # Frameless window for custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        # Enable transparency
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        
        # Set window icon
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))
        
    def _setup_ui(self):
        """Build the UI structure"""
        # Central widget with custom background
        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet("""
            #CentralWidget {
                background-color: #2B2B2B;
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
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        main_layout.addWidget(container)
        
        # Particle Background (behind everything)
        self.particles = ParticleBackground(container)
        self.particles.setGeometry(0, 0, 1000, 600)
        self.particles.spawn_ambient(50)  # Initial particle count
        self.particles.start(fps=30) # Capped at 30 FPS to reduce CPU/GPU load
        
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
                background: #2B2B2B;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 25px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777777;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }

            QScrollBar:horizontal {
                background: #2B2B2B;
                height: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #555555;
                min-width: 25px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #777777;
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
        self.empty_state_label.setStyleSheet("color: #888888; font-size: 16px;")
        self.empty_state_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.empty_state_label.hide()
        container_layout.addWidget(self.empty_state_label)
        
        # Settings Panel (overlay, initially hidden)
        self.settings_panel = SettingsPanel(central)
        self.settings_panel.hide()
        self.settings_panel.close_clicked.connect(self._toggle_settings_panel)
        self.settings_panel.dnd_toggled.connect(self._toggle_dnd)
        self.settings_panel.prayer_mode_toggled.connect(self._toggle_prayer_mode)
        self.settings_panel.simple_mode_toggled.connect(self._toggle_simple_mode)
        self.settings_panel.hardcore_mode_toggled.connect(self._toggle_hardcore_mode)
        self.settings_panel.theme_changed.connect(self._apply_theme)
        
        # System Tray Icon (Moved to init)
        # self._setup_tray()
        
    def resizeEvent(self, event):
        """Handle window resize - update particle layer and grid columns"""
        super().resizeEvent(event)
        
        # Update particle layer size
        if hasattr(self, 'particles'):
            self.particles.setGeometry(0, 0, self.width(), self.height())
            
        # Keep settings panel anchored if visible
        if hasattr(self, 'settings_panel') and self.settings_panel.isVisible():
            self._update_settings_pos()
            
    def _toggle_maximize_restore(self):
        """Toggle window maximized and restored states"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        if hasattr(self, 'title_bar'):
            self.title_bar.update_max_button_icon(self.isMaximized())


    def hideEvent(self, event):
        """Pause particle animation timer when window is hidden to tray"""
        if hasattr(self, 'particles'):
            self.particles.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Resume particle animation timer when window becomes visible"""
        if hasattr(self, 'particles') and not self.isMinimized():
            self.particles.start(fps=30)
        super().showEvent(event)

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

    def eventFilter(self, obj, event):
        """Handle border hover cursor and startSystemResize on mouse press"""
        if event.type() == QEvent.MouseMove:
            if not self.isMaximized():
                pos = self.mapFromGlobal(QCursor.pos())
                self._update_resize_cursor(pos)
                if hasattr(self, 'particles'):
                    self.particles.on_mouse_move(pos.x(), pos.y())

        elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if not self.isMaximized():
                pos = self.mapFromGlobal(QCursor.pos())
                edge = self._update_resize_cursor(pos)
                if edge is not None:
                    handle = self.windowHandle()
                    if handle:
                        handle.startSystemResize(edge)
                        return True

        return super().eventFilter(obj, event)
            
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
        import math
        
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
        self.setMinimumSize(700, 500)
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
            
    def _load_tasks(self, animate=False, first_load=False):
        """Load and display tasks for the active page with Partial Refresh support"""
        tasks = self.task_manager.get_tasks(page_id=self.active_page_id)
        tasks.sort(key=lambda x: x.get('start_time', ''))
        
        # 1. CLEANUP: Find and remove cards that are no longer in our task list
        current_ids = set(t['id'] for t in tasks)
        cards_to_remove = [tid for tid in self.task_cards if tid not in current_ids]
        for tid in cards_to_remove:
            card = self.task_cards.pop(tid)
            card.stop_flashing()
            card.stop_pulse()
            card.deleteLater()
            
        # 2. UPDATE OR CREATE: Efficiently refresh the grid
        # Clear layout first (widgets are preserved in self.task_cards)
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget() and item.widget().objectName() == "AddTaskCard":
                item.widget().deleteLater()
        
        # Always show scroll area
        self.empty_state_label.hide()
        self.scroll.show()
        
        # Restore scroll if saved
        if hasattr(self, '_initial_scroll_pos'):
            pos = self._initial_scroll_pos
            del self._initial_scroll_pos
            QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(pos))
        
        # 3. Dynamic Resizing (Only if count changed)
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
                # BUG-05 FIX: Connect using task_id, always re-fetch from task_manager on click
                task_id = tid
                card.clicked.connect(lambda checked=False, _id=task_id: self._on_task_clicked_by_id(_id))
                card.delete_requested.connect(lambda checked=False, _id=task_id: self._delete_task_by_id(_id))
                card.edit_requested.connect(lambda checked=False, _id=task_id: self._edit_task_by_id(_id))
                self.task_cards[tid] = card
            
            row = i // self.cols
            col = i % self.cols
            
            # Re-add to layout (widgets are already created or updated)
            self.task_layout.addWidget(card, row, col)
            
            # Apply initial pulse if just created/starting
            if task.get('status') == 'active' and not card.is_pulsing:
                card.start_active_pulse()
        
        # ── ADD TASK CARD (+) ──
        # Always the last card in the grid, same dimensions as TaskCard
        add_card = QFrame()
        add_card.setObjectName("AddTaskCard")
        add_card.setMinimumSize(240, 250)
        add_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_card.setCursor(Qt.PointingHandCursor)
        
        is_light = self.current_theme == 'light'
        add_card.setStyleSheet(f"""
            #AddTaskCard {{
                background-color: {'rgba(0,0,0,15)' if is_light else 'rgba(255,255,255,8)'};
                border: 2px dashed {'#888888' if is_light else '#666666'};
                border-radius: 12px;
            }}
            #AddTaskCard:hover {{
                background-color: {'rgba(0,0,0,25)' if is_light else 'rgba(255,255,255,15)'};
                border-color: {'#1F6AA5' if True else '#1F6AA5'};
            }}
        """)
        
        add_card_layout = QVBoxLayout(add_card)
        add_card_layout.setContentsMargins(0, 0, 0, 0)
        add_card_layout.setAlignment(Qt.AlignCenter)
        
        plus_label = QLabel("+")
        plus_label.setFont(QFont("Roboto", 36, QFont.Light))
        plus_label.setStyleSheet(f"color: {'#555555' if is_light else '#888888'}; border: none;")
        plus_label.setAlignment(Qt.AlignCenter)
        add_card_layout.addWidget(plus_label)
        
        # BUG-12 FIX: Proper left-button check + call super() for correct Qt event propagation
        def _add_card_press(event, _widget=add_card):
            if event.button() == Qt.LeftButton:
                self._open_add_dialog()
            QFrame.mousePressEvent(_widget, event)
        add_card.mousePressEvent = _add_card_press
        
        total_items = len(tasks)
        add_row = total_items // self.cols
        add_col = total_items % self.cols
        self.task_layout.addWidget(add_card, add_row, add_col)
                
        self._update_app_icon()
        # State consistency is now handled by:
        # 1. add_task() on creation
        # 2. _update_loop() every second
        # NOT here to prevent recursion and race conditions
            
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
        today_str = now.strftime("%Y-%m-%d")

        # Ghost Check: If not scheduled for today, no action
        repeat_days = task.get('repeat_days', [0,1,2,3,4,5,6])
        if now.weekday() not in repeat_days:
            return  # Ghost task - no action
        
        # Parse task times
        start_str = task.get('start_time', '00:00')
        end_str = task.get('end_time', '23:59')
        
        try:
            start_dt = datetime.strptime(f"{today_str} {start_str}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{today_str} {end_str}", "%Y-%m-%d %H:%M")
            
            # Midnight handling (e.g., 23:00 to 01:00)
            if end_dt < start_dt:
                if now.hour < 12:
                    start_dt -= timedelta(days=1)
                else:
                    end_dt += timedelta(days=1)
        except ValueError:
            start_dt = now
            end_dt = now
        
        # Determine time state
        is_within_time = start_dt <= now <= end_dt
        
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
        
        # Play sound for completing task
        if new_status == 'done':
            self.sound_manager.play_done()
            
            # Trigger confetti burst
            if not self.simple_mode_enabled:
                card = self.task_cards.get(task['id'])
                if card:
                    pos = card.mapTo(self, card.rect().center())
                    self.particles.burst_confetti(pos.x(), pos.y())
        
        # Update task status
        self.task_manager.update_task_status(task['id'], new_status)
        task['status'] = new_status
        
        # Update card visuals
        if task['id'] in self.task_cards:
            self.task_cards[task['id']].update_task(task)
            
        self._update_app_icon()
        # Removed _force_refresh_next_tick=True because we just updated the card in-place. 
        # Forcing a full UI rebuild (destroying and recreating all widgets) causes a frame drop right as confetti starts.
            
    def _open_add_dialog(self):
        """Open dialog to add new task"""
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
        self.active_page_id = page_id
        self.sidebar.set_active_page(page_id)
        self._load_tasks()
        self.save_settings()
    
    def _on_page_add(self):
        """Show dialog to create new page or import a share ID"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget, QWidget, QTextEdit
        
        # Custom dialog with Name + Import option
        dialog = QDialog(self)
        dialog.setWindowTitle("New Page")
        dialog.setFixedSize(360, 220)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {'#F5F5F5' if self.current_theme == 'light' else '#2B2B2B'};
                color: {'#333' if self.current_theme == 'light' else 'white'};
            }}
            QLineEdit, QTextEdit {{
                background-color: {'white' if self.current_theme == 'light' else '#3B3B3B'};
                color: {'#333' if self.current_theme == 'light' else 'white'};
                border: 1px solid {'#CCC' if self.current_theme == 'light' else '#555'};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }}
            QPushButton {{
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
            }}
        """)
        
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
        name_label.setFont(QFont("Roboto", 10))
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
        
        primary_btn_style = """
            QPushButton {
                background-color: #1F6AA5;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
            QPushButton:disabled {
                background-color: #1F6AA5;
                color: rgba(255, 255, 255, 0.4);
            }
        """
        secondary_btn_style = f"""
            QPushButton {{
                background-color: {'#E0E0E0' if self.current_theme == 'light' else '#3B3B3B'};
                color: {'#555' if self.current_theme == 'light' else '#AAA'};
                border: none;
            }}
            QPushButton:hover {{
                background-color: {'#D0D0D0' if self.current_theme == 'light' else '#4B4B4B'};
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
        import_label.setFont(QFont("Roboto", 10))
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
        
        if dialog.exec() != QDialog.Accepted:
            return
            
        action = result_state["action"]
        
        if action == "import":
            share_id_text = import_input.toPlainText().strip()
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
            page_name = name_input.text().strip()
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
            
            if HAS_PLYER:
                notification.notify(
                    title="Daily Tasks",
                    message=f"Share ID for '{page_name}' copied!",
                    app_name="Daily Tasks",
                    timeout=3
                )
        except Exception as e:
            ModernDialogs.show_message(self, "Export Error", f"Failed to encode: {e}", theme=self.current_theme)
    
    def _on_page_mute_toggle(self, page_id):
        """Toggle mute for a page"""
        new_mute = self.task_manager.toggle_mute(page_id)
        self.sidebar.update_page_mute(page_id, new_mute)
        self._update_app_icon()
            
    def _edit_task(self, task):
        """Open dialog to edit task"""
        dialog = AddTaskDialog(self, task_data=task, icon_categories=ICON_CATEGORIES)
        result = dialog.exec()
        if result == 1:  # Accepted (Save)
            data = dialog.get_task_data()
            self._on_task_save(
                data['name'], data['start_time'], data['end_time'], 
                data.get('repeat_days'), data.get('image_path'), task['id']
            )
        elif result == 2:  # Delete
            self._delete_task(task)
            
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
        self.dnd_enabled = enabled
        self.sound_manager.set_dnd(enabled)
        
        if enabled:
            self._stop_flashing()
            
        self._update_app_icon()
        self.save_settings()
        
    def _toggle_prayer_mode(self, enabled):
        """Toggle prayer times feature"""
        if enabled:
            # Sync prayer times
            self.settings_panel.set_prayer_loading(True)
            self.save_settings()
            
            def sync():
                try:
                    success = self.task_manager.sync_prayer_times()
                    self.prayer_sync_finished.emit(success)
                except Exception as e:
                    print(f"Prayer sync failed: {e}")
                    self.prayer_sync_finished.emit(False)
                    
            threading.Thread(target=sync, daemon=True).start()
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
        self.settings_panel.set_prayer_loading(False)
        
        # Check if user disabled it while we were syncing
        if not self.settings_panel.prayer_checkbox.checkbox.isChecked():
            # Ensure they are gone (in case sync re-added them)
            self.task_manager.remove_synced_tasks()
            self._load_tasks()
            return
            
        if success:
            # Sync succeeded! Recalculate statuses (Pending/Active) and show them
            self.task_manager.synchronize_task_statuses()
            self._load_tasks()
            # Show a subtle success if it was the first time
            if not getattr(self, '_prayer_synced_once', False):
                self._send_notification("Daily Tasks", "Prayer Timers synced successfully!")
                self._prayer_synced_once = True
        else:
            # Sync failed (Network or Location issue)
            # DO NOT uncheck the box - let the user keep the intent enabled
            # The TaskManager will use it's fallback/cached data if available
            self._send_notification("Sync Issue", "Could not update prayer times. Using cached data.")
            # Still refresh UI in case cached ones can now be shown
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

            if old_status == 'pending' and new_status == 'active':
                self._send_notification(f"Task Started: {task['name']}", "It's time!")
                self.sound_manager.play_start()
            elif old_status == 'active' and new_status == 'failed':
                self.sound_manager.play_fail()

        # 2. Scan current monitoring tasks for active/urgent state (read-only)
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

            try:
                start_dt = datetime.combine(now.date(), datetime.strptime(task['start_time'], "%H:%M").time())
                end_dt = datetime.combine(now.date(), datetime.strptime(task['end_time'], "%H:%M").time())
                # OPT-10 / shared midnight handling
                if end_dt < start_dt:
                    if now.hour < 12:
                        start_dt -= timedelta(days=1)
                    else:
                        end_dt += timedelta(days=1)

                remaining = end_dt - now
                if timedelta(seconds=0) < remaining < timedelta(minutes=30):
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
            except (ValueError, KeyError):
                pass

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
        task_map = {str(t['id']): t for t in all_tasks}

        for tid in changed_ids:
            if tid in self.task_cards:
                if tid in task_map:
                    self.task_cards[tid].update_content(task_map[tid])
                else:
                    # Task disappeared from active page (e.g. prayer removed) — full reload
                    self._load_tasks()
                    return

        self._update_app_icon()

    def _update_loop(self):
        """Periodic update for task statuses (every second)"""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # 1. Daily Reset Check
        if today_str != self.current_date_str:
            self.current_date_str = today_str
            self._flashed_urgent_tasks.clear()
            self.task_manager.reset_daily_tasks()
            self._load_tasks()
            return

        # 2. BUG-01 / OPT-01 FIX: Single-pass sync — replaces the previous
        # double-scan (synchronize_task_statuses + _check_upcoming_tasks).
        # synchronize_task_statuses now returns the exact transitions so
        # _monitor_task_states can act on them without re-computing statuses.
        sync_modified, changes = self.task_manager.synchronize_task_statuses()

        # 3. Handle sound / notification / flash side-effects for transitions
        self._monitor_task_states(changes)

        # 4. BUG-04 / OPT-04 FIX: Incremental card refresh — only rebuild grid
        # when tasks are structurally added/removed (handled in _load_tasks callers).
        # Status-only changes are reflected via card.update_content() exclusively.
        if sync_modified:
            changed_ids = {str(t['id']) for t, _, _ in changes}
            self._update_cards_incremental(changed_ids)

    def _send_notification(self, title, message):
        """Send Windows notification"""
        if self.dnd_enabled:
            return
            
        # Flash taskbar
        self._flash_window()
        
        if HAS_PLYER:
            try:
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
        """Detect window activation to stop flashing and pause animations when unfocused"""
        if event.type() == QEvent.ActivationChange:
            if self.isActiveWindow():
                self._stop_flashing()
                # Consider user 'notified' if they viewed the app
                self._has_flashed_batch = True
                # Restart particles on focus
                if hasattr(self, 'particles'):
                    self.particles.start(fps=30)
            else:
                # OPTIMIZATION: Stop particles completely when window is unfocused (clicking elsewhere)
                if hasattr(self, 'particles'):
                    self.particles.stop()
        
        elif event.type() == QEvent.WindowStateChange:
            if hasattr(self, 'title_bar'):
                self.title_bar.update_max_button_icon(self.isMaximized())
            if self.isMinimized():
                # Stop particles to save CPU when minimized
                if hasattr(self, 'particles'):
                    self.particles.stop()
            else:
                # Restart particles when restored
                if hasattr(self, 'particles'):
                    # Only restart if not already running (start() handles restart safely)
                    self.particles.start(fps=30)
        super().changeEvent(event)
            
    def _update_app_icon(self):
        """Update app icon with badge count (debounced)"""
        if self._icon_update_scheduled:
            return
        self._icon_update_scheduled = True
        QTimer.singleShot(200, self._perform_icon_update)
        
    def _perform_icon_update(self):
        """Actually update the app icon"""
        self._icon_update_scheduled = False
        
        try:
            if not os.path.exists(self.icon_path):
                return
                
            # Count active tasks
            # Count active tasks
            active_count = 0
            now = datetime.now()
            if not self.dnd_enabled:
                for t in self.task_manager.get_tasks_for_monitoring():
                    # Skip Ghost Tasks
                    if now.weekday() not in t.get('repeat_days', [0,1,2,3,4,5,6]):
                        continue
                        
                    if t.get('status') == 'active':
                        active_count += 1
                        
            # BUG-14 / OPT-02 FIX: Restored early-exit guard — skip full icon
            # rebuild when active count and DND state haven't changed.
            # Previously commented out; re-enabled to avoid 5 QPainter renders/second.
            cache_key = (active_count, self.dnd_enabled)
            if getattr(self, '_last_badge_cache_key', None) == cache_key:
                return
            self._last_badge_cache_key = cache_key
            self.last_badge_count = active_count
            
            # Load base icon via Qt natively
            pixmap = QPixmap(self.icon_path)
            
            if active_count > 0:
                # Use hardware-accelerated QPainter instead of slow PIL
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                
                w = pixmap.width()
                h = pixmap.height()
                badge_size = int(w * 0.45)
                x0 = w - badge_size
                y0 = h - badge_size
                
                # Draw red circle
                painter.setBrush(QColor("#D32F2F"))
                painter.setPen(QPen(Qt.white, int(w*0.02)))
                painter.drawEllipse(x0, y0, badge_size, badge_size)
                
                # Draw text
                painter.setPen(Qt.white)
                font = QFont("Arial", int(badge_size * 0.55), QFont.Bold)
                painter.setFont(font)
                
                from PySide6.QtCore import QRectF
                painter.drawText(QRectF(x0, y0, badge_size, badge_size), Qt.AlignCenter, str(active_count))
                painter.end()
                        
                # Update Window Title with Count
                self.setWindowTitle(f"({active_count}) Daily Tasks (V2.5 - New Engine)")
            else:
                self.setWindowTitle("Daily Tasks (V2.5 - New Engine)")
        
            icon = QIcon(pixmap)
            
            self.setWindowIcon(icon)
            # Force update Taskbar icon via QApplication
            QApplication.instance().setWindowIcon(icon)
            
            # Update tray icon too
            if self.tray_icon:
                self.tray_icon.setIcon(icon)
                self.tray_icon.setToolTip(f"Daily Tasks ({active_count} active)" if active_count > 0 else "Daily Tasks")
            
        except Exception as e:
            print(f"Badge update failed: {e}")
            
    def load_settings(self):
        """Load user preferences"""
        # Use AppData for persistent storage (not MEIPASS which is a temp dir)
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.settings_dir = os.path.join(appdata, 'DailyTasks')
        self.settings_path = os.path.join(self.settings_dir, "settings.json")
        
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
                
            # Apply settings to panel checkboxes (block signals to prevent triggering during load)
            dnd = settings.get('dnd_enabled', False)
            prayer = settings.get('prayer_mode_enabled', False)
            simple = settings.get('simple_mode_enabled', False)
            hardcore = settings.get('hardcore_mode_enabled', False)
            theme = settings.get('theme', 'dark')
            
            # Set theme toggle
            self.settings_panel._set_theme(theme)
            self.current_theme = theme
            self._apply_theme(theme)
            
            # Set checkbox states
            self.settings_panel.set_values(dnd, prayer, simple, hardcore)
            
            # Store initial scroll position to be applied after tasks load
            self._initial_scroll_pos = settings.get('scroll_position', 0)
            
            # Restore active page
            saved_page = settings.get('active_page_id')
            if saved_page and self.task_manager._find_page(saved_page):
                self.active_page_id = saved_page
            
            # Check for date change (Reset Logic for persistent tasks)
            today_str = datetime.now().strftime("%Y-%m-%d")
            last_date = settings.get('last_opened_date', today_str) 
            
            # If we opened on a new day, reset tasks
            if last_date != today_str:
                print(f"New day detected ({last_date} -> {today_str}). Resetting daily tasks.")
                self.task_manager.reset_daily_tasks()
                
            # Always sync statuses to handle time passed while closed
            self.task_manager.synchronize_task_statuses()
                
            self._last_opened_date = today_str
            self.save_settings()  # Important: Persist "last opened" immediately to prevent accidental resets on crash
            
            # Apply actual logic
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
                
        except (FileNotFoundError, json.JSONDecodeError):
            pass
            
    def _update_settings_pos(self):
        """Anchor settings panel above the settings button (Robust Global Mapping)"""
        try:
            if not hasattr(self, 'sidebar') or not hasattr(self.sidebar, 'settings_btn'):
                return
                
            # 1. Get Button's Global Position
            btn_global = self.sidebar.settings_btn.mapToGlobal(QPoint(0, 0))
            
            # 2. Convert to Panel's Parent Coordinates (central widget)
            # This ensures 'move(x,y)' works correctly regardless of window nesting/margins
            parent = self.settings_panel.parent()
            if not parent:
                parent = self # Fallback
                
            target_pos = parent.mapFromGlobal(btn_global)
            
            # 3. Calculate Target X,Y
            # Left aligned with button, slightly offset
            x = target_pos.x() + 10
            
            # Bottom aligned with button top
            y = target_pos.y() - self.settings_panel.height() - 10
            
            # 4. Clamp to safe area (Title bar ~40px)
            if y < 40: y = 40
            
            self.settings_panel.move(x, y)
        except Exception as e:
            print(f"Error positioning settings: {e}")
            # Fallback to center if positioning fails
            x = (self.width() - self.settings_panel.width()) // 2
            y = (self.height() - self.settings_panel.height()) // 2
            self.settings_panel.move(x, y)

    def _toggle_settings_panel(self):
        """Show/hide settings panel"""
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            self._update_settings_pos()
            self.settings_panel.show()
            self.settings_panel.raise_()
            
    def _apply_theme(self, theme):
        """Apply theme globally"""
        self.current_theme = theme
        self.save_settings()
        
        if theme == "light":
            # Light theme colors
            bg_color = "#FAFAFA"
            scroll_bg = "#2B2B2B"
            scroll_handle = "#888888"
            QApplication.instance().setStyleSheet(LIGHT_THEME_CSS)
        else:
            # Dark theme colors (default)
            bg_color = "#2B2B2B"
            scroll_bg = "#2B2B2B"
            scroll_handle = "#555555"
            QApplication.instance().setStyleSheet(DARK_THEME_CSS)
            
        # Update central widget
        self.centralWidget().setStyleSheet(f"""
            #CentralWidget {{
                background-color: {bg_color};
            }}
        """)
        
        # Update sidebar
        self.sidebar.apply_theme(theme)
        self.settings_panel.apply_theme(theme)
        
        # Update scroll area for light mode
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
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                border-radius: 5px;
            }}
        """)
        
        # Update task cards
        for card in self.task_cards.values():
            card.apply_theme(theme)
        
        # Update title bar
        self.title_bar.apply_theme(theme)

    def _ensure_startup(self):
        """Enforce startup registry key"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            
            app_name = "Daily Tasks"
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
                cmd = f'"{exe_path}"'
            else:
                # During dev: pythonw.exe start.py
                # Use sys.argv[0] to find script
                script = os.path.abspath(sys.argv[0])
                # Ensure we use pythonw if running via python (though pythonw is preferred for GUI)
                py_exe = sys.executable.replace("python.exe", "pythonw.exe")
                if not os.path.exists(py_exe): py_exe = sys.executable
                cmd = f'"{py_exe}" "{script}"'
                
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Startup registration failed: {e}")

    def save_settings(self):
        """Save user preferences (OPT-06: writes asynchronously to avoid disk I/O on main thread)"""
        if getattr(self, '_loading_settings', False):
            return

        try:
            # Gather all values on the main thread (UI access must stay on main thread)
            settings = {
                'dnd_enabled': self.dnd_enabled,
                'simple_mode_enabled': self.simple_mode_enabled,
                'prayer_mode_enabled': self.settings_panel.prayer_checkbox.checkbox.isChecked(),
                'hardcore_mode_enabled': self.hardcore_mode_enabled,
                'theme': self.current_theme,
                'scroll_position': self.scroll.verticalScrollBar().value(),
                'last_opened_date': getattr(self, '_last_opened_date', datetime.now().strftime("%Y-%m-%d")),
                'active_page_id': self.active_page_id
            }
            settings_dir = self.settings_dir
            settings_path = self.settings_path

            # Write in background to avoid blocking the UI thread
            def _write():
                try:
                    os.makedirs(settings_dir, exist_ok=True)
                    with open(settings_path, 'w') as f:
                        json.dump(settings, f)
                except Exception as e:
                    print(f"Failed to save settings: {e}")

            threading.Thread(target=_write, daemon=True).start()
        except Exception as e:
            print(f"Failed to prepare settings: {e}")
            
    def _setup_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Set tray icon
        if os.path.exists(self.icon_path):
            self.tray_icon.setIcon(QIcon(self.icon_path))
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
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #2B2B2B;
                color: white;
                border: 1px solid #555;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #1F6AA5;
            }
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
        """Robust restore from tray"""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
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
        """Clean shutdown"""
        if hasattr(self, 'particles'):
            self.particles.stop()  # Stop particle timer to prevent background CPU burn
        if self.tray_icon:
            self.tray_icon.hide() # Remove icon from tray
        QApplication.quit()


# ═══════════════════════════════════════════════════════════
# NUCLEAR UI FIX: GLOBAL MENU FILTER
# ═══════════════════════════════════════════════════════════
class GlobalMenuFilter(QObject):
    """
    Intercepts every QMenu as it is created/shown to:
    1. Force-disable WA_TranslucentBackground (The inheritance bug)
    2. Force opaque palette and solid background
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QMenu):
            try:
                # 1. Disable translucency inherited from parent
                obj.setAttribute(Qt.WA_TranslucentBackground, False)
                obj.setAttribute(Qt.WA_NoSystemBackground, False)
                obj.setAutoFillBackground(True)
                
                # 2. Logic to find the current active theme globally
                main_win = None
                for top_level in QApplication.topLevelWidgets():
                    if hasattr(top_level, 'current_theme'):
                        main_win = top_level
                        break
                theme = getattr(main_win, 'current_theme', 'dark') if main_win else 'dark'
                
                # 3. Apply solid palette based on theme
                palette = obj.palette()
                if theme == 'light':
                    bg_color = QColor("#FFFFFF")
                    text_color = QColor("#000000")
                else:
                    bg_color = QColor("#1E1E1E")
                    text_color = QColor("#FFFFFF")
                
                palette.setColor(obj.backgroundRole(), bg_color)
                palette.setColor(obj.foregroundRole(), text_color)
                obj.setPalette(palette)
                
                # 4. Final CSS reinforcement
                border_color = "#CCCCCC" if theme == 'light' else "#555555"
                obj.setStyleSheet(f"QMenu {{ background-color: {bg_color.name()}; color: {text_color.name()}; border: 1px solid {border_color}; }}")
            except:
                pass
                
        return False

def run_qt_app():
    """Entry point for the Qt version of the app"""
    
    # -------------------------------------------------------------
    # Dynamic Extreme Resolution Scaling Engine
    # -------------------------------------------------------------
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # Bypass Windows DPI virtualization to get raw hardware pixels
        user32.SetProcessDPIAware() 
        screen_h = user32.GetSystemMetrics(1)
        
        # Calculate optimal scale mapping against a standard 1080p baseline
        # 1366x768  -> ~0.71x (Prevents tiny laptops from clipping)
        # 1920x1080 -> 1.00x (Standard)
        # 3840x2160 -> 2.00x (Prevents 4K screens from looking tiny)
        scale = screen_h / 1080.0
        
        # Clamp to prevent totally broken bounds
        scale = max(0.65, min(3.0, scale))
        
        # Override Qt's automatic OS DPI mapping and enforce mathematical resolution scaling
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(round(scale, 2))
    except Exception as e:
        print(f"Dynamic Scaling failed: {e}")

    # -------------------------------------------------------------
    # Win32: Set AUMID to ensure Taskbar Icon & Grouping work correctly
    # MUST BE DONE BEFORE QAPPLICATION LOADS
    # -------------------------------------------------------------
    try:
        import ctypes
        myappid = 'DailyTasks.App.v1.2.5'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception as e:
        print(f"AUMID setup failed: {e}")
        
    # Ensure all menus are rendered by Qt (not native) for full styling control
    QCoreApplication.setAttribute(Qt.AA_DontUseNativeMenuBar)
    
    app = QApplication(sys.argv)
    
    # -------------------------------------------------------------
    # NUCLEAR UI FIX: Install Global Menu Filter
    # -------------------------------------------------------------
    menu_filter = GlobalMenuFilter(app)
    app.installEventFilter(menu_filter)
    
    # -------------------------------------------------------------
    # App-Wide Icon (Taskbar FIX)
    # -------------------------------------------------------------
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        # Resolve from current file location (.\src\qt_app.py)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
    icon_path = os.path.join(base_path, "assets", "icon.png")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    
    # -------------------------------------------------------------
    # Single Instance Lock (Enforce Only One Instance)
    # -------------------------------------------------------------
    socket = QLocalSocket()
    socket.connectToServer("DailyTasksAppIPCV2_5")
    if socket.waitForConnected(300):
        # Connected to a live instance! Send activation signal and exit.
        socket.write(b"ACTIVATE")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        sys.exit(0)

    # No live instance running — clean up any stale pipe name
    QLocalServer.removeServer("DailyTasksAppIPCV2_5")
    # -------------------------------------------------------------
    
    # Set app-wide font
    app.setFont(QFont("Roboto", 10))
    
    # Create and show window
    window = DailyTasksWindow(base_path=base_path)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run_qt_app()
