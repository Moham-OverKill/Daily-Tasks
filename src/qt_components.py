"""
Qt-based UI Components for Daily Tasks
Full feature parity with original CustomTkinter version
"""

from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, 
    QPushButton, QGraphicsDropShadowEffect, QScrollArea,
    QWidget, QGridLayout, QLineEdit, QTimeEdit, QDialog,
    QDialogButtonBox, QComboBox, QGraphicsOpacityEffect,
    QToolTip, QCheckBox, QSizePolicy, QFileDialog
)
from PySide6.QtGui import QFont, QColor, QIntValidator, QPixmap, QCursor, QDrag, QPainter
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTime, QTimer, Property, QMimeData, QByteArray, QObject, QEvent, QPoint, QSize
from datetime import datetime, timedelta
import os
import shutil
import uuid


class ModernDialogs:
    """Standardized modern UI popups replacing legacy QInputDialog and QMessageBox"""
    
    class _EnterKeyFilter(QObject):
        def __init__(self, target_btn, parent=None):
            super().__init__(parent)
            self.target_btn = target_btn

        def eventFilter(self, obj, event):
            if event.type() == QEvent.KeyPress:
                if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    if not self.target_btn.isEnabled():
                        return True # Consume/Ignore the event
            return super().eventFilter(obj, event)

    @staticmethod
    def _apply_style(dialog, theme):
        is_light = theme == "light"
        bg = "#F5F5F5" if is_light else "#2B2B2B"
        fg = "#333333" if is_light else "white"
        input_bg = "white" if is_light else "#3B3B3B"
        input_border = "#CCCCCC" if is_light else "#555555"
        
        dialog.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {fg}; }}
            QLabel {{ color: {fg}; font-size: 13px; }}
            QLineEdit, QTextEdit {{
                background-color: {input_bg}; color: {fg};
                border: 1px solid {input_border};
                border-radius: 6px; padding: 8px; font-size: 13px;
            }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-size: 12px; font-weight: bold; border: none; }}
        """)
        
    @staticmethod
    def _style_btn(btn, mode, theme):
        is_light = theme == "light"
        if mode == "primary":
            bg, hover = "#1F6AA5", "#2980B9"
            fg = "white"
        elif mode == "danger":
            bg, hover = "#D32F2F", "#E53935"
            fg = "white"
        else:
            bg = "#E0E0E0" if is_light else "#3B3B3B"
            hover = "#D0D0D0" if is_light else "#4B4B4B"
            fg = "#555555" if is_light else "#AAAAAA"
            
        btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {bg}; 
                color: {fg}; 
            }} 
            QPushButton:hover {{ 
                background-color: {hover}; 
            }}
            QPushButton:disabled {{
                background-color: {bg};
                color: {fg};
                opacity: 0.5;
            }}
        """)
        # Specific transparency for disabled state
        if btn.isEnabled() == False:
            effect = QGraphicsOpacityEffect(btn)
            effect.setOpacity(0.4)
            btn.setGraphicsEffect(effect)
        else:
            btn.setGraphicsEffect(None)

    @staticmethod
    def get_text(parent, title, label_text, default_text="", theme="dark"):
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(340, 160)
        ModernDialogs._apply_style(dialog, theme)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel(label_text))
        inp = QLineEdit(default_text)
        layout.addWidget(inp)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        ok_btn = QPushButton("OK")
        
        ModernDialogs._style_btn(cancel_btn, "secondary", theme)
        ModernDialogs._style_btn(ok_btn, "primary", theme)
        # RELIABITY FIX: Disable autoDefault to prevent Enter from triggering buttons unexpectedly
        cancel_btn.setAutoDefault(False)
        ok_btn.setAutoDefault(False)
        
        # SECURITY HOOK: Install event filter to strictly guard Enter key
        filter = ModernDialogs._EnterKeyFilter(ok_btn, dialog)
        dialog.installEventFilter(filter)
        
        # Reactive validation: Disable OK button if empty
        def validate():
            is_valid = bool(inp.text().strip())
            ok_btn.setEnabled(is_valid)
            ok_btn.setDefault(is_valid) # DYNAMIC DEFAULT
            ModernDialogs._style_btn(ok_btn, "primary", theme) # Refresh effect
            
        inp.textChanged.connect(validate)
        validate() # Initial check

        def on_return():
            if ok_btn.isEnabled():
                dialog.accept()
                
        inp.returnPressed.connect(on_return)
        
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            return inp.text().strip(), True
        return "", False

    @staticmethod
    def ask_yes_no(parent, title, message, theme="dark", is_danger=False):
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(340)
        ModernDialogs._apply_style(dialog, theme)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("No")
        ok_btn = QPushButton("Yes")
        
        ModernDialogs._style_btn(cancel_btn, "secondary", theme)
        ModernDialogs._style_btn(ok_btn, "danger" if is_danger else "primary", theme)
        
        ok_btn.setDefault(True)
        cancel_btn.setAutoDefault(False)
        
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        return dialog.exec() == QDialog.Accepted

    @staticmethod
    def confirm(parent, title, message, theme="dark", is_danger=False):
        """User-requested alias for ask_yes_no to support existing code paths"""
        return ModernDialogs.ask_yes_no(parent, title, message, theme, is_danger)

    @staticmethod
    def show_message(parent, title, message, theme="dark"):
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(320)
        ModernDialogs._apply_style(dialog, theme)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ModernDialogs._style_btn(ok_btn, "primary", theme)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dialog.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()


class CustomTitleBar(QFrame):
    """
    Custom title bar to replace the native Windows title bar.
    Features: App icon, title, minimize and close buttons, draggable.
    """
    
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, title="Daily Tasks", icon_path=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setObjectName("CustomTitleBar")
        self._drag_pos = None

        self.setStyleSheet("""
            #CustomTitleBar {
                background-color: #1E1E1E;
                border-bottom: 1px solid #333333;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # App title on the left
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Roboto", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #AAAAAA; padding-left: 4px;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Minimize button
        self.min_btn = QPushButton("─")
        self.min_btn.setFixedSize(40, 30)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #AAAAAA;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333333;
                color: white;
            }
        """)
        self.min_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.min_btn)

        # Maximize / Restore button
        self.max_btn = QPushButton("🗖")
        self.max_btn.setFixedSize(40, 30)
        self.max_btn.setCursor(Qt.PointingHandCursor)
        self.max_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #AAAAAA;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #333333;
                color: white;
            }
        """)
        self.max_btn.clicked.connect(self.maximize_clicked.emit)
        layout.addWidget(self.max_btn)

        # Close button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(40, 30)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #AAAAAA;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E81123;
                color: white;
            }
        """)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)

    def update_max_button_icon(self, is_maximized):
        """Update Maximize/Restore button icon depending on state"""
        self.max_btn.setText("🗗" if is_maximized else "🗖")
        
        # Store reference for theming
        # self.title_label = title_label  # Removed title label
    
    def mouseDoubleClickEvent(self, event):
        """Double click title bar to toggle maximize / restore"""
        if event.button() == Qt.LeftButton:
            self.maximize_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
        
    def mousePressEvent(self, event):
        """Start native window move on mouse press"""
        if event.button() == Qt.LeftButton:
            win = self.window()
            handle = win.windowHandle() if win else None
            if handle:
                handle.startSystemMove()
                event.accept()
                return
            self._drag_pos = event.globalPosition().toPoint()
            
    def mouseMoveEvent(self, event):
        """Drag window when moving mouse"""
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._drag_pos = event.globalPosition().toPoint()
            self.window().move(self.window().pos() + delta)
            
    def mouseReleaseEvent(self, event):
        """End drag on mouse release"""
        self._drag_pos = None
        
    def apply_theme(self, theme):
        """Apply theme to title bar"""
        if theme == "light":
            self.setStyleSheet("""
                #CustomTitleBar {
                    background-color: #E8E8E8;
                    border-bottom: 1px solid #CCCCCC;
                }
            """)
            self.min_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #555555;
                    border: none;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #DDDDDD;
                    color: black;
                }
            """)
            self.max_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #555555;
                    border: none;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #DDDDDD;
                    color: black;
                }
            """)
            self.close_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #555555;
                    border: none;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #E81123;
                    color: white;
                }
            """)
            self.title_label.setStyleSheet("color: #555555; padding-left: 4px;")
        else:
            self.setStyleSheet("""
                #CustomTitleBar {
                    background-color: #1E1E1E;
                    border-bottom: 1px solid #333333;
                }
            """)
            self.min_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #AAAAAA;
                    border: none;
                    font-size: 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #333333;
                    color: white;
                }
            """)
            self.max_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #AAAAAA;
                    border: none;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #333333;
                    color: white;
                }
            """)
            self.close_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #AAAAAA;
                    border: none;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #E81123;
                    color: white;
                }
            """)
            self.title_label.setStyleSheet("color: #AAAAAA; padding-left: 4px;")


class TaskCard(QFrame):
    """
    A single task card widget with status display and click interaction.
    Styled with semi-transparent background to show particles behind.
    Full feature parity: hover effects, pulse animation, urgent flashing.
    """
    
    clicked = Signal()
    delete_requested = Signal()
    edit_requested = Signal()
    
    # Status colors (matching original)
    # Status colors
    STATUS_COLORS = {
        'done': '#2E7D32',      # Green
        'failed': '#D32F2F',    # Red
        'active': '#2196F3',    # Blue
        'pending': '#2B2B2B'    # Dark gray (Default)
    }
    
    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.id = task_data['id']
        self.status = task_data.get('status', 'pending')
        
        # Animation state
        self.is_flashing = False
        self.is_pulsing = False
        self.animations_enabled = True
        self._flash_state = False
        self._pulse_value = 1.0
        self.current_theme = 'dark'
        
        # Timers
        self.flash_timer = QTimer(self)
        self.flash_timer.timeout.connect(self._flash_loop)
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_loop)
        
        # Color interpolation state
        self._current_bg = QColor(0,0,0,0)
        self._current_border = QColor(0,0,0,0)
        self._animating_color = False
        
        # Color Animation
        self.color_anim = None # Initialized on demand
        
        self.setMinimumSize(240, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        # BUG-07 / OPT-05 FIX: Create ghost opacity effect once and reuse it.
        # Previously a new QGraphicsOpacityEffect was instantiated on every
        # _apply_styles_manually call, leaking the old objects continuously.
        self._ghost_opacity_effect = QGraphicsOpacityEffect(self)

        self._setup_ui()
        self._update_visuals(animate=False)  # Initial load is instant
        
    def update_content(self, task_data):
        """Partial Refresh: Update card data and visuals without rebuilding"""
        old_status = self.status
        self.task_data = task_data
        self.status = task_data.get('status', 'pending')
        
        # Update Labels
        self.name_label.setText(task_data['name'])
        start = task_data.get('start_time', '00:00')
        end = task_data.get('end_time', '00:00')
        self.time_label.setText(f"{self._format_time(start)} — {self._format_time(end)}")
        
        # Update Icon (Handle Emoji vs Path)
        self._set_task_icon(task_data.get('image_path', '📝'))
        
        # Trigger Visual Update (with animation if status changed)
        animate = (old_status != self.status) and self.animations_enabled
        self._update_visuals(animate=animate)
        
        # Update extra states
        if self.status == 'active' and not self.is_pulsing and self.animations_enabled:
            self.start_active_pulse()
        elif self.status != 'active' and self.is_pulsing:
            self.stop_pulse()
        
    def _setup_ui(self):
        """Create the card layout"""
        self.setObjectName("TaskCard")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Status label (top)
        self.status_label = QLabel()
        self.status_label.setFont(QFont("Roboto", 9, QFont.Bold))
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Icon (center) - Use Segoe UI Emoji for Windows emoji support
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setMinimumHeight(80)
        self.icon_label.setStyleSheet("background: transparent;")
        
        self._set_task_icon(self.task_data.get('image_path', '📝'))
        layout.addWidget(self.icon_label)
        
        layout.addStretch()
        
        # Task name
        self.name_label = QLabel(self.task_data['name'])
        self.name_label.setFont(QFont("Roboto", 14, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)
        
        # Time range
        start = self.task_data.get('start_time', '00:00')
        end = self.task_data.get('end_time', '00:00')
        self.time_label = QLabel(f"{self._format_time(start)} — {self._format_time(end)}")
        self.time_label.setFont(QFont("Roboto", 10))
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)
        
    def _set_task_icon(self, icon_val):
        """Internal helper to render either emoji text or high-quality pixmap"""
        try:
            if not icon_val: icon_val = '📝'
            if not isinstance(icon_val, str): icon_val = str(icon_val)
            
            # Identify if this is a path (contains slashes, image extensions, or internal cache keywords)
            is_path = any(s in icon_val.lower() for s in ['\\', '/', '.png', '.jpg', '.jpeg', '.webp', 'cache', 'custom'])
            
            if is_path:
                # Resolve relative cache paths to absolute AppData
                if not os.path.isabs(icon_val) and 'cache' in icon_val:
                    appdata = os.getenv('APPDATA', os.path.expanduser('~'))
                    resolved_path = os.path.normpath(os.path.join(appdata, 'DailyTasks', icon_val))
                else:
                    resolved_path = icon_val

                pixmap = QPixmap(resolved_path)
                if not pixmap.isNull():
                    self.icon_label.setText("")
                    self.icon_label.setPixmap(pixmap.scaled(
                        70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ))
                    return
                else:
                    # STRICT FALLBACK: Never show path string as text
                    icon_val = '❓'
                    
            # Render as Emoji (Only reached if not a path, or if path was invalid and fell back to ❓)
            self.icon_label.setPixmap(QPixmap()) 
            self.icon_label.setFont(QFont("Segoe UI Emoji", 42))
            self.icon_label.setText(icon_val)
        except Exception as e:
            print(f"Error rendering task icon: {e}")
            self.icon_label.setPixmap(QPixmap())
            self.icon_label.setFont(QFont("Segoe UI Emoji", 42))
            self.icon_label.setText('❓')

    def _format_time(self, time_str):
        """Format 24h time to 12h format"""
        try:
            t = datetime.strptime(time_str, "%H:%M")
            return t.strftime("%I:%M %p").lstrip("0")
        except:
            return time_str
            
    def _update_visuals(self, animate=False):
        """Update card appearance based on status"""
        # 1. Determine Target Colors
        target_base = QColor(self.STATUS_COLORS.get(self.status, '#888888'))
        is_light = getattr(self, 'current_theme', 'dark') == 'light'
        
        if is_light:
            target_bg = QColor(target_base)
            if self.status == 'pending':
                target_bg.setAlpha(30)
            else:
                target_bg = target_bg.lighter(160)
                target_bg.setAlpha(180)
            
            if self.status in ['active', 'done', 'failed']:
                 target_border = QColor(target_base)
            else:
                 target_border = QColor("#CCCCCC")
        else:
            target_bg = QColor(target_base)
            if self.status == 'pending':
                target_bg.setAlpha(200)
            else:
                target_bg.setAlpha(150)
            
            if self.status == 'active':
                target_border = QColor("#2196F3")
            elif self.is_flashing:
                target_border = QColor("#FF5722")
            else:
                target_border = QColor("#444444")

        # 2. Apply Animation if requested
        if animate and self.animations_enabled:
            from PySide6.QtCore import QVariantAnimation
            if self.color_anim:
                self.color_anim.stop()
            
            self.color_anim = QVariantAnimation(self)
            self.color_anim.setDuration(400)
            self.color_anim.setStartValue(0.0)
            self.color_anim.setEndValue(1.0)
            self.color_anim.setEasingCurve(QEasingCurve.OutCubic)
            
            start_bg = self._current_bg if self._current_bg.alpha() > 0 else target_bg
            start_border = self._current_border if self._current_border.alpha() > 0 else target_border
            
            def animate_step(v):
                r = int(start_bg.red() + (target_bg.red() - start_bg.red()) * v)
                g = int(start_bg.green() + (target_bg.green() - start_bg.green()) * v)
                b = int(start_bg.blue() + (target_bg.blue() - start_bg.blue()) * v)
                a = int(start_bg.alpha() + (target_bg.alpha() - start_bg.alpha()) * v)
                self._current_bg = QColor(r, g, b, a)
                
                r_b = int(start_border.red() + (target_border.red() - start_border.red()) * v)
                g_b = int(start_border.green() + (target_border.green() - start_border.green()) * v)
                b_b = int(start_border.blue() + (target_border.blue() - start_border.blue()) * v)
                a_b = int(start_border.alpha() + (target_border.alpha() - start_border.alpha()) * v)
                self._current_border = QColor(r_b, g_b, b_b, a_b)
                self._apply_styles_manually()
            
            self.color_anim.valueChanged.connect(animate_step)
            self.color_anim.start()
        else:
            self._current_bg = target_bg
            self._current_border = target_border
            self._apply_styles_manually()

    def _apply_styles_manually(self):
        """Final CSS application and label updates"""
        is_light = getattr(self, 'current_theme', 'dark') == 'light'
        bg_rgba = f"rgba({self._current_bg.red()}, {self._current_bg.green()}, {self._current_bg.blue()}, {self._current_bg.alpha()})"
        border_rgba = f"rgba({self._current_border.red()}, {self._current_border.green()}, {self._current_border.blue()}, {self._current_border.alpha()})"
        
        # Cursor & Status Text
        status_text_map = {'done': '✓ DONE', 'failed': '✗ FAILED', 'active': '● ACTIVE', 'pending': 'PENDING', 'disabled': 'DISABLED'}
        text = status_text_map.get(self.status, 'PENDING')
        
        if is_light:
            text_color = "#333333"
            time_color = "#555555"
        else:
            text_color = "white" if self.status in ['done', 'failed', 'active'] else "#CCCCCC"
            time_color = "white" if self.status in ['done', 'failed', 'active'] else "#888888"

        self.status_label.setText(text)
        
        # Ghost / Disabled Mode Check
        repeat_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6])
        today_weekday = datetime.now().weekday()
        if len(repeat_days) == 0 or self.status == 'disabled':
            self.setCursor(Qt.ArrowCursor)
            self._ghost_opacity_effect.setOpacity(0.50 if is_light else 0.35)
            self.setGraphicsEffect(self._ghost_opacity_effect)
            self.status_label.setText("DISABLED")
            self.time_label.setText("Disabled (No Days)")
            
            ghost_color = "#555555" if is_light else "#888888"
            self.status_label.setStyleSheet(f"color: {ghost_color};")
            self.name_label.setStyleSheet(f"color: {ghost_color};")
            self.icon_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.time_label.setStyleSheet(f"color: {ghost_color};")
            self.setStyleSheet(f"#TaskCard {{ background-color: transparent; border-radius: 15px; border: none; }}")
        elif today_weekday not in repeat_days:
            # Ghost specific
            self.setCursor(Qt.ArrowCursor)
            self._ghost_opacity_effect.setOpacity(0.50 if is_light else 0.35)
            self.setGraphicsEffect(self._ghost_opacity_effect)
            self.status_label.setText("LATER")
            
            # Calculate relative string
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            days_until = next((i for i in range(1, 8) if (today_weekday + i) % 7 in repeat_days), None)
            if days_until:
                day_name = day_names[(today_weekday + days_until) % 7]
                relative_str = f"{day_name} ({'tomorrow' if days_until==1 else f'in {days_until} days'})"
            else:
                relative_str = "Not scheduled"
            self.time_label.setText(relative_str)
            
            # Styles
            ghost_color = "#555555" if is_light else "#888888"
            self.status_label.setStyleSheet(f"color: {ghost_color};")
            self.name_label.setStyleSheet(f"color: {ghost_color};")
            self.icon_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.time_label.setStyleSheet(f"color: {ghost_color};")
            self.setStyleSheet(f"#TaskCard {{ background-color: transparent; border-radius: 15px; border: none; }}")
        else:
            # Normal Mode
            self.setGraphicsEffect(None)
            self.setCursor(Qt.PointingHandCursor if self.status != 'pending' else Qt.ArrowCursor)
            self.status_label.setStyleSheet(f"color: {text_color};")
            self.name_label.setStyleSheet(f"color: {text_color};")
            self.icon_label.setStyleSheet(f"color: {text_color}; background: transparent;")
            self.time_label.setStyleSheet(f"color: {time_color}; margin-top: 4px;")
            
            self.setStyleSheet(f"""
                #TaskCard {{
                    background-color: {bg_rgba};
                    border-radius: 15px;
                    border: 2px solid {border_rgba};
                }}
            """)
        
    def enterEvent(self, event):
        """Handle mouse enter - hover effect"""
        if not self.animations_enabled or self.is_flashing:
            return
            
        # Don't hover if ghost
        repeat_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6])
        if datetime.now().weekday() not in repeat_days:
            return
            
        self._set_hover(True)
        
    def leaveEvent(self, event):
        """Handle mouse leave - remove hover effect"""
        if not self.animations_enabled or self.is_flashing:
            return
        
        # Don't hover if ghost
        repeat_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6])
        if datetime.now().weekday() not in repeat_days:
            return
            
        self._set_hover(False)
        
    def _set_hover(self, hovered):
        """Apply or remove hover styling"""
        if self.is_flashing:
            return
            
        # Check if we're in light mode
        is_light = getattr(self, 'current_theme', 'dark') == 'light'
        
        if is_light:
            # Re-calculate base colors using exact same logic as _update_visuals to ensure consistency
            # This prevents "glitching" between different hardcoded colors
            base_color = QColor(self.STATUS_COLORS.get(self.status, '#888888'))
            
            # Background logic matching _update_visuals
            bg_col = QColor(base_color)
            if self.status == 'pending':
                bg_col.setAlpha(30) # Very faint grey
            else:
                bg_col = bg_col.lighter(160) # Lighten significantly
                bg_col.setAlpha(180) # Semi-transparent
            
            bg = f"rgba({bg_col.red()}, {bg_col.green()}, {bg_col.blue()}, {bg_col.alpha()})"
            
            if hovered:
                # Hovered: Darker border for feedback
                if self.status in ['active', 'done', 'failed']:
                    # Use a slightly darker version of the base color for hover border
                    border_col = base_color.darker(120).name() # 20% darker
                    border = f"2px solid {border_col}"
                else:
                    border = "2px solid #888888"
            else:
                # Not hovered: Match _update_visuals EXACTLY
                if self.status in ['active', 'done', 'failed']:
                    border = f"2px solid {base_color.name()}"
                else:
                    border = "2px solid #CCCCCC"
        else:
            # Dark mode colors
            c = QColor(self.STATUS_COLORS.get(self.status, '#2B2B2B'))
            alpha_val = 150 if self.status in ['done', 'failed', 'active'] else 200
            bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha_val})"
            
            if hovered:
                border = "2px solid #00E5FF"
            elif self.status == 'active':
                border = "2px solid #2196F3"
            else:
                border = "2px solid #444444"  # Subtle border for all tasks
            
        self.setStyleSheet(f"""
            #TaskCard {{
                background-color: {bg};
                border-radius: 15px;
                border: {border};
            }}
        """)
        
    def mousePressEvent(self, event):
        """Handle click to toggle task status"""
        if event.button() == Qt.LeftButton:
            # Only toggle if not pending
            if self.status != 'pending':
                self.clicked.emit()
                self._animate_press()
                
        elif event.button() == Qt.RightButton:
            # Explicitly trigger context menu on Right Click
            # This is a fallback in case contextMenuEvent is blocked
            self._show_context_menu(event.globalPos())
            event.accept()
            return
        
        # Always call super to allow standard processing
        super().mousePressEvent(event)
            
    def contextMenuEvent(self, event):
        """Right-click for edit/delete (Standard)"""
        self._show_context_menu(event.globalPos())
        
    def _show_context_menu(self, global_pos):
        """Show the context menu"""
        # Prevent editing synced tasks (like prayers)
        if self.task_data.get('is_synced', False):
            return
            
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #3B3B3B;
                color: white;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #1F6AA5;
            }
        """)
        edit_action = menu.addAction("✏️ Edit")
        delete_action = menu.addAction("🗑️ Delete")
        
        action = menu.exec(global_pos)
        if action == edit_action:
            self.edit_requested.emit()
        elif action == delete_action:
            self.delete_requested.emit()
            
    def _animate_press(self):
        """Brief flash effect on press"""
        if not self.animations_enabled:
            return
        # BUG-06 FIX: Apply a targeted border-only style change instead of the
        # fragile str.replace('}', ...) which corrupts all nested CSS rules.
        self.setStyleSheet(self.styleSheet() + "\n#TaskCard { border: 3px solid white; }")
        QTimer.singleShot(100, lambda: self._update_visuals())
        
    def update_task(self, task_data):
        """Update the card with new task data (Legacy alias, redirecting to update_content)"""
        self.update_content(task_data)
        
        # Additional Pulse management if needed for status changes
        if self.status == 'active':
            self.start_active_pulse()
        else:
            self.stop_pulse()
            self.stop_flashing()
            
    def set_animations_enabled(self, enabled):
        """Enable/disable animations"""
        self.animations_enabled = enabled
        if not enabled:
            self.stop_flashing()
            self.stop_pulse()
            
    def start_urgent_flashing(self):
        """Start urgent red/yellow flashing"""
        if self.is_flashing or not self.animations_enabled:
            return
        self.is_flashing = True
        self.flash_timer.start(500)  # 500ms per flash
        self._flash_loop() # Trigger immediately so no blue gap
        
    def _flash_loop(self):
        """Toggle flash state"""
        self._flash_state = not self._flash_state
        
        # Colors: Red (255,0,0) / Yellow (255,235,59)
        rgb = "255, 0, 0" if self._flash_state else "255, 235, 59"
        
        # Border: White / Red
        border_col = "white" if self._flash_state else "rgb(255, 0, 0)"
        
        self.setStyleSheet(f"""
            #TaskCard {{
                background-color: rgba({rgb}, 130);
                border-radius: 15px;
                border: 2px solid {border_col};
            }}
        """)
        
    def stop_flashing(self):
        """Stop flashing animation"""
        self.is_flashing = False
        self.flash_timer.stop()
        self._update_visuals()
        
    def start_active_pulse(self):
        """Start subtle breathing pulse for active tasks"""
        if self.is_pulsing or not self.animations_enabled:
            return
        # Pulse disabled to prevent flickering/distraction
        return
        
        # self.is_pulsing = True
        # self._pulse_direction = -1
        # self._pulse_value = 1.0
        # self.pulse_timer.start(50)  # 50ms for smooth animation
        
    def _pulse_loop(self):
        """Animate pulse effect"""
        self._pulse_value += self._pulse_direction * 0.02
        if self._pulse_value <= 0.85:
            self._pulse_direction = 1
        elif self._pulse_value >= 1.0:
            self._pulse_direction = -1
            
        # Apply slight opacity change (visual pulse)
        opacity = int(208 * self._pulse_value)  # D0 = 208
        
        # Blue #2196F3 (R=33, G=150, B=243)
        bg_rgba = f"rgba(33, 150, 243, {opacity})"
        border_rgba = "#2196F3"
        
        self.setStyleSheet(f"""
            #TaskCard {{
                background-color: {bg_rgba};
                border-radius: 15px;
                border: 2px solid {border_rgba};
            }}
        """)
        
    def stop_pulse(self):
        """Stop pulse animation"""
        self.is_pulsing = False
        self.pulse_timer.stop()
        
    def apply_theme(self, theme):
        """Apply theme to card"""
        self.current_theme = theme
        
        if theme == "light":
            # Light mode: cards need borders/shadows, softer colors
            self.name_label.setStyleSheet("color: #333333;")
            self.time_label.setStyleSheet("color: #555555; margin-top: 4px;")
            
            # Update status colors for light mode
            # No need to duplicate logic, simply call update_visuals which now handles it
            
        else:
            # Dark mode: restore original styling
            self.name_label.setStyleSheet("color: white;")
            self.time_label.setStyleSheet("color: #CCCCCC; margin-top: 4px;")
            
        self._update_visuals()


class DraggablePageListWidget(QWidget):
    order_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.drop_indicator = QFrame(self)
        self.drop_indicator.setFixedHeight(40)
        self.drop_indicator.setStyleSheet("background-color: rgba(100, 100, 100, 50); border: 2px dashed #888888; border-radius: 6px;")
        self.drop_indicator.hide()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-page-id'):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat('application/x-page-id'):
            layout = self.layout()
            insert_idx = 0
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if hasattr(w, 'page_id') and w.isVisible():
                    if event.position().y() < w.y() + w.height() / 2:
                        break
                    insert_idx = i + 1
            
            layout.insertWidget(insert_idx, self.drop_indicator)
            self.drop_indicator.show()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_indicator.hide()

    def dropEvent(self, event):
        self.drop_indicator.hide()
        if event.mimeData().hasFormat('application/x-page-id'):
            layout = self.layout()
            page_id = event.mimeData().data('application/x-page-id').data().decode('utf-8')
            
            pages = []
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if hasattr(w, 'page_id'):
                    pages.append(w)
            
            source_widget = next((w for w in pages if w.page_id == page_id), None)
            if not source_widget:
                return
                
            pages.remove(source_widget)
            
            insert_idx = len(pages)
            for i, p in enumerate(pages):
                if event.position().y() < p.y() + p.height() / 2:
                    insert_idx = i
                    break
                    
            pages.insert(insert_idx, source_widget)
            new_order = [p.page_id for p in pages]
            self.order_changed.emit(new_order)
            event.acceptProposedAction()


class PageButton(QFrame):
    """
    A single page entry in the sidebar.
    Click to switch pages. Hover to reveal 3-dot menu.
    """
    
    page_clicked = Signal(str)       # page_id
    rename_requested = Signal(str)   # page_id
    delete_requested = Signal(str)   # page_id
    export_requested = Signal(str)   # page_id
    mute_requested = Signal(str)     # page_id
    
    def __init__(self, page_id, page_name, muted=False, selected=False, parent=None):
        super().__init__(parent)
        self.page_id = page_id
        self.page_name = page_name
        self.muted = muted
        self.selected = selected
        self.current_theme = 'dark'
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("PageButton")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(6)
        
        # Page name label
        self.name_label = QLabel(page_name)
        self.name_label.setFont(QFont("Roboto", 11, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.name_label, 1)
        
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._apply_style()
        
    def _apply_style(self):
        is_light = self.current_theme == 'light'
        
        if self.selected:
            if is_light:
                bg = "rgba(0, 0, 0, 25)" # Slightly darker for better visibility against light sidebars
                text_color = "#111111"
            else:
                bg = "rgba(255, 255, 255, 12)"
                text_color = "white"
        else:
            bg = "transparent"
            text_color = "#888888" if not is_light else "#666666"
        
        self.setStyleSheet(f"""
            #PageButton {{
                background-color: {bg};
                border-radius: 6px;
            }}
            #PageButton:hover {{
                background-color: {'rgba(0,0,0,20)' if is_light else 'rgba(255,255,255,15)'};
                border-radius: 6px;
            }}
        """)
        self.name_label.setStyleSheet(f"color: {text_color};")
        
        # Muted state: reuse cached opacity effect
        if self.muted:
            self._opacity_effect.setOpacity(0.45)
            self.setGraphicsEffect(self._opacity_effect)
        else:
            self.setGraphicsEffect(None)
    
    def set_selected(self, selected):
        self.selected = selected
        self._apply_style()
        
    def set_muted(self, muted):
        self.muted = muted
        self._apply_style()
        
    def apply_theme(self, theme):
        self.current_theme = theme
        self._apply_style()
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self.page_clicked.emit(self.page_id)
        elif event.button() == Qt.RightButton:
            self._show_menu_at(event.globalPos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not hasattr(self, '_drag_start_pos'):
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 5:
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData('application/x-page-id', self.page_id.encode('utf-8'))
        drag.setMimeData(mime_data)
        
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        # Lift effect handling
        from PySide6.QtWidgets import QGraphicsOpacityEffect
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.5)
        self.setGraphicsEffect(effect)
        
        drag.exec(Qt.MoveAction)
        
        # Reset effect after dropping
        self._apply_style()
    
    def contextMenuEvent(self, event):
        """Right-click context menu"""
        self._show_menu_at(event.globalPos())
        event.accept()
    def _show_menu_at(self, global_pos):
        """Show context menu at given global position"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        is_light = self.current_theme == 'light'
        
        if is_light:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #F5F5F5;
                    color: #333333;
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    padding: 4px 0;
                }
                QMenu::item {
                    padding: 6px 20px;
                }
                QMenu::item:selected {
                    background-color: #E0E0E0;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #3B3B3B;
                    color: white;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 4px 0;
                }
                QMenu::item {
                    padding: 6px 20px;
                }
                QMenu::item:selected {
                    background-color: #1F6AA5;
                }
            """)
        
        rename_action = menu.addAction("✏️  Rename")
        export_action = menu.addAction("📤  Export")
        mute_text = "🔊  Unmute" if self.muted else "🔇  Mute"
        mute_action = menu.addAction(mute_text)
        menu.addSeparator()
        delete_action = menu.addAction("🗑️  Delete")
        
        action = menu.exec(global_pos)
        if action == rename_action:
            self.rename_requested.emit(self.page_id)
        elif action == delete_action:
            self.delete_requested.emit(self.page_id)
        elif action == export_action:
            self.export_requested.emit(self.page_id)
        elif action == mute_action:
            self.mute_requested.emit(self.page_id)


class Sidebar(QFrame):
    """
    Semi-transparent sidebar with page navigation and controls.
    """
    
    add_task_clicked = Signal()  # Still needed — now triggered by the grid add-card
    settings_clicked = Signal()
    
    # Page signals
    page_selected = Signal(str)       # page_id
    page_add_clicked = Signal()
    page_rename = Signal(str, str)    # page_id, new_name  (handled in qt_app)
    page_delete = Signal(str)         # page_id
    page_export = Signal(str)         # page_id
    page_mute_toggle = Signal(str)    # page_id
    page_reordered = Signal(list)     # new_order_list
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.current_theme = 'dark'
        self._page_buttons = {}  # page_id -> PageButton
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)
        
        self.setStyleSheet("""
            #Sidebar {
                background-color: rgba(30, 30, 30, 200);
                border-right: 1px solid transparent;
            }
        """)
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Scrollable page list (takes up all available space)
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.page_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        self.page_list_widget = DraggablePageListWidget()
        self.page_list_widget.setStyleSheet("background: transparent;")
        self.page_list_widget.order_changed.connect(self.page_reordered.emit)
        self.page_list_layout = QVBoxLayout(self.page_list_widget)
        self.page_list_layout.setSpacing(10)
        self.page_list_layout.setContentsMargins(4, 4, 4, 4)
        self.page_list_layout.addStretch()
        
        self.page_scroll.setWidget(self.page_list_widget)
        layout.addWidget(self.page_scroll, 1)  # stretch=1 fills space
        
        # Settings button at bottom
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setFont(QFont("Roboto", 11))
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                text-align: left;
                padding: 8px 0;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

        # ── COPY FEEDBACK (absolute positioned) ──
        self.copy_feedback = QLabel("Share ID Copied!", self)
        self.copy_feedback.setAlignment(Qt.AlignCenter)
        self.copy_feedback.setFont(QFont("Roboto", 9, QFont.Bold))
        self.copy_feedback.setStyleSheet("color: #66BB6A;")
        
        self._feedback_w = 140
        self._feedback_h = 25
        self._feedback_x = (250 - self._feedback_w) // 2
        self._feedback_y = 60
        self.copy_feedback.setGeometry(
            self._feedback_x, self._feedback_y,
            self._feedback_w, self._feedback_h
        )
        self.copy_feedback.hide()
        
        # + New Page button (lives inside the scroll area, managed in set_pages)
        self._add_page_btn = None

    def set_pages(self, pages, active_page_id=None):
        """Populate the page list from page metadata list + add New Page button"""
        # Clear existing buttons
        for btn in self._page_buttons.values():
            btn.deleteLater()
        self._page_buttons.clear()
        
        if self._add_page_btn:
            self._add_page_btn.deleteLater()
            self._add_page_btn = None
        
        # Ensure drop_indicator is removed safely
        if hasattr(self.page_list_widget, 'drop_indicator'):
            self.page_list_layout.removeWidget(self.page_list_widget.drop_indicator)
            self.page_list_widget.drop_indicator.setParent(self.page_list_widget)
            
        # Remove all items from layout
        while self.page_list_layout.count():
            item = self.page_list_layout.takeAt(0)
        
        # Add page buttons
        for page_info in pages:
            pid = page_info['id']
            btn = PageButton(
                page_id=pid,
                page_name=page_info['name'],
                muted=page_info.get('muted', False),
                selected=(pid == active_page_id)
            )
            btn.apply_theme(self.current_theme)
            btn.page_clicked.connect(self.page_selected.emit)
            btn.rename_requested.connect(lambda p_id: self.page_rename.emit(p_id, ""))
            btn.delete_requested.connect(self.page_delete.emit)
            btn.export_requested.connect(self.page_export.emit)
            btn.mute_requested.connect(self.page_mute_toggle.emit)
            
            self.page_list_layout.addWidget(btn)
            self._page_buttons[pid] = btn
        
        self.page_list_layout.addSpacing(16)
        
        # + New Page button (directly below last page)
        self._add_page_btn = QPushButton("+")
        self._add_page_btn.setFont(QFont("Roboto", 24, QFont.Bold))
        self._add_page_btn.setFixedHeight(40)
        self._add_page_btn.setCursor(Qt.PointingHandCursor)
        self._apply_add_page_theme()
        self._add_page_btn.clicked.connect(self.page_add_clicked.emit)
        self.page_list_layout.addWidget(self._add_page_btn)
        
        self.page_list_layout.addStretch()
    
    def set_active_page(self, page_id):
        """Update visual selection state"""
        for pid, btn in self._page_buttons.items():
            btn.set_selected(pid == page_id)
            
    def update_page_mute(self, page_id, muted):
        """Update mute visual for a specific page"""
        if page_id in self._page_buttons:
            self._page_buttons[page_id].set_muted(muted)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'copy_feedback'):
            new_x = (self.width() - self._feedback_w) // 2
            self.copy_feedback.setGeometry(
                new_x, self._feedback_y,
                self._feedback_w, self._feedback_h
            )

    def _apply_add_page_theme(self):
        """Apply styling to the + New Page button based on current theme"""
        if self._add_page_btn is None:
            return
        is_light = self.current_theme == 'light'
        if is_light:
            self._add_page_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #444444;
                    border: 2px dashed #777777;
                    border-radius: 6px;
                    padding: 0px 0px 4px 0px;
                }
                QPushButton:hover {
                    color: #111111;
                    border-color: #444444;
                    background-color: rgba(0, 0, 0, 15);
                }
            """)
        else:
            self._add_page_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #AAAAAA;
                    border: 2px dashed #666666;
                    border-radius: 6px;
                    padding: 0px 0px 4px 0px;
                }
                QPushButton:hover {
                    color: white;
                    border-color: #888888;
                }
            """)

    def apply_theme(self, theme):
        self.current_theme = theme
        
        if theme == "light":
            self.setStyleSheet("""
                #Sidebar {
                    background-color: rgba(235, 235, 235, 250);
                    border-right: 1px solid #CCCCCC;
                }
            """)
            self.settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #555555;
                    border: none;
                    text-align: left;
                    padding: 8px 0;
                }
                QPushButton:hover {
                    color: black;
                }
            """)
            self.copy_feedback.setStyleSheet("background-color: rgba(240, 240, 240, 240); color: #2E7D32; border: 1px solid #CCCCCC; padding: 5px 10px; border-radius: 5px;")
        else:
            self.setStyleSheet("""
                #Sidebar {
                    background-color: rgba(30, 30, 30, 200);
                    border-right: 1px solid transparent;
                }
            """)
            self.settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #888888;
                    border: none;
                    text-align: left;
                    padding: 8px 0;
                }
                QPushButton:hover {
                    color: white;
                }
            """)
            self.copy_feedback.setStyleSheet("background-color: rgba(30, 30, 30, 240); color: #66BB6A; padding: 5px 10px; border-radius: 5px;")
        
        # Update all page buttons and add page btn
        for btn in self._page_buttons.values():
            btn.apply_theme(theme)
        self._apply_add_page_theme()

    def show_copy_feedback(self, page_id=None):
        """Show temporary 'Copied!' message positioned under the specific page button"""
        if hasattr(self, '_fade_timer') and self._fade_timer is not None:
            self._fade_timer.stop()
            
        # Dynamic positioning
        if page_id and page_id in self._page_buttons:
            btn = self._page_buttons[page_id]
            # Center vertically in the 10px gap between buttons
            # btn_bottom is the Y coordinate of the target button's bottom edge (in Sidebar coords)
            # Label height is 25, so (bottom - 8) puts the label's center roughly at (bottom + 4.5)
            # which is the midpoint of the 10px spacing
            btn_bottom = btn.mapTo(self, QPoint(0, btn.height()))
            self._feedback_y = btn_bottom.y() - 8
        else:
            # Fallback to default position if no ID or button not found
            self._feedback_y = 60
            
        self.copy_feedback.setGeometry(
            self._feedback_x, self._feedback_y,
            self._feedback_w, self._feedback_h
        )
        self.copy_feedback.setStyleSheet("color: rgba(102, 187, 106, 255);")
        self.copy_feedback.setVisible(True)
        self.copy_feedback.raise_()

        # BUG-10 FIX: Stop any existing delay timer before replacing it,
        # and give the timer a parent so Qt manages its lifetime.
        if hasattr(self, '_fade_timer') and self._fade_timer is not None:
            self._fade_timer.stop()
        # Also stop the fade-step timer if it was running mid-fade
        if hasattr(self, '_fade_interval') and self._fade_interval is not None:
            self._fade_interval.stop()

        self._fade_timer = QTimer(self)  # parent=self for proper lifetime management
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._start_stylesheet_fade)
        self._fade_timer.start(1500)
    
    def _start_stylesheet_fade(self):
        self._fade_step = 255
        # BUG-10 FIX: Stop any previous fade-interval and give a parent widget
        if hasattr(self, '_fade_interval') and self._fade_interval is not None:
            self._fade_interval.stop()
        self._fade_interval = QTimer(self)  # parent=self for proper lifetime management
        self._fade_interval.timeout.connect(self._fade_step_update)
        self._fade_interval.start(30)
    
    def _fade_step_update(self):
        self._fade_step -= 10
        if self._fade_step <= 0:
            self._fade_interval.stop()
            self.copy_feedback.hide()
            return
        self.copy_feedback.setStyleSheet(f"color: rgba(102, 187, 106, {self._fade_step});")



class InfoBadge(QLabel):
    """
    Custom 'i' icon with instant, snappy tooltip and better hitbox.
    """
    def __init__(self, tooltip, parent=None):
        super().__init__("ⓘ", parent)
        self.setToolTip(tooltip)
        self.setFont(QFont("Roboto", 12))
        self.setCursor(Qt.WhatsThisCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(24, 24)  # Larger consistent hitbox
        
        # Default to dark theme style
        self.apply_theme('dark')

    def apply_theme(self, theme):
        """Update style for theme, specifically QToolTip"""
        if theme == 'light':
            # Light Mode: Dark Icon, White Tooltip
            text_color = "#888888"
            hover_color = "#333333"
            hover_bg = "#E0E0E0"
            tt_bg = "#FFFFFF"
            tt_text = "#000000"
            tt_border = "#CCCCCC"
        else:
            # Dark Mode: Light Icon, Dark Tooltip
            text_color = "#888888"
            hover_color = "white"
            hover_bg = "#555555"
            tt_bg = "#1E1E1E"
            tt_text = "#FFFFFF"
            tt_border = "#555555"
            
        self.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                border-radius: 12px;
                background-color: transparent;
                padding: 0px;
            }}
            QLabel:hover {{
                color: {hover_color};
                background-color: {hover_bg};
            }}
            QToolTip {{
                background-color: {tt_bg};
                color: {tt_text};
                border: 1px solid {tt_border};
                padding: 5px;
                border-radius: 4px;
            }}
        """)

    def enterEvent(self, event):
        # showText(pos, text, widget) - shows instantly with no delay
        QToolTip.showText(QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        # Hide instantly on leave
        QToolTip.hideText()
        super().leaveEvent(event)


class SettingsPanel(QFrame):
    """
    Settings overlay panel with checkboxes for app modes.
    """
    
    close_clicked = Signal()
    dnd_toggled = Signal(bool)
    prayer_mode_toggled = Signal(bool)
    simple_mode_toggled = Signal(bool)
    hardcore_mode_toggled = Signal(bool)
    theme_changed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = 'dark'
        self.setObjectName("SettingsPanel")
        self.setFixedSize(300, 420)  # Compact size
        
        self.setStyleSheet("""
            #SettingsPanel {
                background-color: rgba(40, 40, 40, 245);
                border-radius: 10px;
                border: 1px solid #555555;
            }
        """)
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Header with close button
        header = QHBoxLayout()
        
        self.title_label = QLabel("Settings")
        self.title_label.setFont(QFont("Roboto", 16, QFont.Bold))
        self.title_label.setStyleSheet("color: white;")
        header.addWidget(self.title_label)
        
        header.addStretch()
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFont(QFont("Roboto", 14, QFont.Bold))
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
            }
        """)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        header.addWidget(self.close_btn)
        
        layout.addLayout(header)
        
        # ─────────────────────────────────────────
        # Theme Section
        # ─────────────────────────────────────────
        self.theme_label_ui = QLabel("Theme")
        self.theme_label_ui.setFont(QFont("Roboto", 12, QFont.Bold))
        self.theme_label_ui.setStyleSheet("color: #AAAAAA; margin-top: 10px;")
        layout.addWidget(self.theme_label_ui)
        
        # Theme toggle (segmented control)
        theme_container = QFrame()
        theme_container.setStyleSheet("background: transparent;")
        theme_layout = QHBoxLayout(theme_container)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.setSpacing(0)
        
        self.dark_btn = QPushButton("🌙 Dark")
        self.dark_btn.setCheckable(True)
        self.dark_btn.setChecked(True)  # Default
        self.dark_btn.setFont(QFont("Roboto", 10))
        self.dark_btn.setCursor(Qt.PointingHandCursor)
        
        self.light_btn = QPushButton("☀️ Light")
        self.light_btn.setCheckable(True)
        self.light_btn.setFont(QFont("Roboto", 10))
        self.light_btn.setCursor(Qt.PointingHandCursor)
        
        # Segmented control styling
        segment_style = """
            QPushButton {
                background-color: #3B3B3B;
                color: #888888;
                border: none;
                padding: 8px 16px;
            }
            QPushButton:checked {
                background-color: #1F6AA5;
                color: white;
            }
            QPushButton:hover {
                background-color: #4B4B4B;
            }
            QPushButton:checked:hover {
                background-color: #2980B9;
            }
        """
        self.dark_btn.setStyleSheet(segment_style + "QPushButton { border-radius: 6px 0 0 6px; }")
        self.light_btn.setStyleSheet(segment_style + "QPushButton { border-radius: 0 6px 6px 0; }")
        
        self.dark_btn.clicked.connect(lambda: self._set_theme("dark"))
        self.light_btn.clicked.connect(lambda: self._set_theme("light"))
        
        theme_layout.addWidget(self.dark_btn)
        theme_layout.addWidget(self.light_btn)
        theme_layout.addStretch()
        layout.addWidget(theme_container)
        
        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #555555;")
        layout.addWidget(sep)
        
        # ─────────────────────────────────────────
        # Settings Checkboxes
        # ─────────────────────────────────────────
        self.dnd_checkbox = self._create_checkbox(
            "Do Not Disturb", 
            "Mutes all audio, suppresses notifications, and disables taskbar flashing."
        )
        self.dnd_checkbox.toggled.connect(self.dnd_toggled.emit)
        layout.addWidget(self.dnd_checkbox)
        
        self.prayer_checkbox = self._create_checkbox(
            "Prayer Times", 
            "Enables automatic alerts for daily prayer intervals based on local time."
        )
        self.prayer_checkbox.toggled.connect(self.prayer_mode_toggled.emit)
        layout.addWidget(self.prayer_checkbox)
        
        self.simple_checkbox = self._create_checkbox(
            "Simple View", 
            "Cleans up the UI by hiding particles and animations for a minimalist focus."
        )
        self.simple_checkbox.toggled.connect(self.simple_mode_toggled.emit)
        layout.addWidget(self.simple_checkbox)
        
        self.hardcore_checkbox = self._create_checkbox(
            "Hardcore Mode", 
            "Locks tasks if marked as failed, making them impossible to check as done."
        )
        self.hardcore_checkbox.toggled.connect(self.hardcore_mode_toggled.emit)
        layout.addWidget(self.hardcore_checkbox)
        
        layout.addStretch()
        
    def _set_theme(self, theme):
        """Handle theme toggle"""
        if theme == "dark":
            self.dark_btn.setChecked(True)
            self.light_btn.setChecked(False)
        else:
            self.dark_btn.setChecked(False)
            self.light_btn.setChecked(True)
        self.theme_changed.emit(theme)
        
    def _create_checkbox(self, label, description):
        container = QFrame()
        container.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(12)
        
        # Checkbox button (styled as square)
        checkbox = QPushButton()
        checkbox.setCheckable(True)
        checkbox.setFixedSize(24, 24)
        checkbox.setCursor(Qt.PointingHandCursor)
        checkbox.setStyleSheet("""
            QPushButton {
                background-color: #3B3B3B;
                border: 2px solid #555555;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #1F6AA5;
                border-color: #1F6AA5;
            }
            QPushButton:hover {
                border-color: #00E5FF;
            }
        """)
        
        # Connect to main visual updater to ensure theme respect
        checkbox.toggled.connect(lambda checked: self._update_checkbox_visual(checkbox, checked))
        layout.addWidget(checkbox)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setFont(QFont("Roboto", 11))
        label_widget.setStyleSheet("color: white;")
        layout.addWidget(label_widget)
        
        # Info icon with tooltip (Using custom InfoBadge)
        info_btn = InfoBadge(description)
        layout.addWidget(info_btn)
        
        layout.addStretch()
        
        # Store checkbox reference on container for external access
        container.checkbox = checkbox
        container.toggled = checkbox.toggled
        container.label_widget = label_widget
        container.info_btn = info_btn
        
        return container
        
    def set_values(self, dnd, prayer, simple, hardcore):
        """Set checkbox states without triggering signals"""
        # Block signals to prevent toggle callbacks during load
        self.dnd_checkbox.checkbox.blockSignals(True)
        self.prayer_checkbox.checkbox.blockSignals(True)
        self.simple_checkbox.checkbox.blockSignals(True)
        self.hardcore_checkbox.checkbox.blockSignals(True)
        
        self.dnd_checkbox.checkbox.setChecked(dnd)
        self.prayer_checkbox.checkbox.setChecked(prayer)
        self.simple_checkbox.checkbox.setChecked(simple)
        self.hardcore_checkbox.checkbox.setChecked(hardcore)
        
        # Unblock signals
        self.dnd_checkbox.checkbox.blockSignals(False)
        self.prayer_checkbox.checkbox.blockSignals(False)
        self.simple_checkbox.checkbox.blockSignals(False)
        self.hardcore_checkbox.checkbox.blockSignals(False)
        
        # Manually update checkmark visuals (since signals were blocked)
        self._update_checkbox_visual(self.dnd_checkbox.checkbox, dnd)
        self._update_checkbox_visual(self.prayer_checkbox.checkbox, prayer)
        self._update_checkbox_visual(self.simple_checkbox.checkbox, simple)
        self._update_checkbox_visual(self.hardcore_checkbox.checkbox, hardcore)
        
        
    def set_prayer_loading(self, loading):
        """Show loading state on prayer checkbox"""
        # Don't disable input, allow user to cancel/uncheck even if loading
        # self.prayer_checkbox.checkbox.setEnabled(not loading)
        pass

    def apply_theme(self, theme):
        """Apply theme to settings panel"""
        self.current_theme = theme
        if theme == 'light':
            self.setStyleSheet("""
                #SettingsPanel {
                    background-color: #FFFFFF;
                    border-radius: 10px;
                    border: 1px solid #CCCCCC;
                }
                QToolTip {
                    background-color: #FFFFFF;
                    color: #000000;
                    border: 1px solid #CCCCCC;
                    padding: 5px;
                    border-radius: 4px;
                }
            """)
            self.title_label.setStyleSheet("color: #333333;")
            self.theme_label_ui.setStyleSheet("color: #555555; margin-top: 10px;")
            
            # Close button
            self.close_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #555555;
                    border: none;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    background-color: #EEEEEE;
                    color: black;
                }
            """)
            
            # Checkbox styles
            for cb_container in [self.dnd_checkbox, self.prayer_checkbox, self.simple_checkbox, self.hardcore_checkbox]:
                # Update Label
                cb_container.label_widget.setStyleSheet("color: #333333;")
                
                # Update Info Badge
                if hasattr(cb_container, 'info_btn'):
                    cb_container.info_btn.apply_theme('light')
                
                # Update Checkbox visual (force update based on current check state)
                is_checked = cb_container.checkbox.isChecked()
                self._update_checkbox_visual(cb_container.checkbox, is_checked)
                
            # Theme Toggle Buttons (Light Mode)
            segment_style = """
                QPushButton {
                    background-color: #E0E0E0;
                    color: #555555;
                    border: none;
                    padding: 8px 16px;
                }
                QPushButton:checked {
                    background-color: #1F6AA5;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #D0D0D0;
                }
                QPushButton:checked:hover {
                    background-color: #2980B9;
                }
            """
            self.dark_btn.setStyleSheet(segment_style + "QPushButton { border-radius: 6px 0 0 6px; }")
            self.light_btn.setStyleSheet(segment_style + "QPushButton { border-radius: 0 6px 6px 0; }")
                
        else:
            # Dark Mode
            self.setStyleSheet("""
                #SettingsPanel {
                    background-color: rgba(40, 40, 40, 245);
                    border-radius: 10px;
                    border: 1px solid #555555;
                }
                QToolTip {
                    background-color: #1E1E1E;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 4px;
                }
            """)
            self.title_label.setStyleSheet("color: white;")
            self.theme_label_ui.setStyleSheet("color: #AAAAAA; margin-top: 10px;")
            
            self.close_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #888888;
                    border: none;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.1);
                    color: white;
                }
            """)
            
            # Checkbox styles
            for cb_container in [self.dnd_checkbox, self.prayer_checkbox, self.simple_checkbox, self.hardcore_checkbox]:
                cb_container.label_widget.setStyleSheet("color: white;")
                
                if hasattr(cb_container, 'info_btn'):
                    cb_container.info_btn.apply_theme('dark')
                    
                is_checked = cb_container.checkbox.isChecked()
                self._update_checkbox_visual(cb_container.checkbox, is_checked)

            # Theme Toggle Buttons (Dark Mode)
            segment_style = """
                QPushButton {
                    background-color: #3B3B3B;
                    color: #888888;
                    border: none;
                    padding: 8px 16px;
                }
                QPushButton:checked {
                    background-color: #1F6AA5;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #4B4B4B;
                }
                QPushButton:checked:hover {
                    background-color: #2980B9;
                }
            """
            self.dark_btn.setStyleSheet(segment_style + "QPushButton { border-radius: 6px 0 0 6px; }")
            self.light_btn.setStyleSheet(segment_style + "QPushButton { border-radius: 0 6px 6px 0; }")

    def _update_checkbox_visual(self, checkbox, checked):
        """Update checkbox text and style to match checked state AND theme"""
        # Use current_theme to determine unchecked colors
        is_light = self.current_theme == 'light'
        
        unchecked_bg = "#EEEEEE" if is_light else "#3B3B3B"
        unchecked_border = "#CCCCCC" if is_light else "#555555"
        unchecked_hover = "#999999" if is_light else "#00E5FF"
        
        checkbox.setText("✓" if checked else "")
        
        if checked:
            bg = "#1F6AA5"
            border = "#1F6AA5"
            color = "white"
        else:
            bg = unchecked_bg
            border = unchecked_border
            color = "transparent"
            
        checkbox.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 4px;
                color: {color};
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                border-color: {unchecked_hover if not checked else 'white'};
            }}
        """)



class AddTaskDialog(QDialog):
    """Dialog for adding/editing a task with full icon picker"""
    
    def __init__(self, parent=None, task_data=None, icon_categories=None):
        super().__init__(parent)
        self.task_data = task_data
        self.icon_categories = icon_categories or {}
        # Default to None if new task, else keep valid icon
        self.selected_icon = task_data.get('image_path') if task_data else None
        
        self.setWindowTitle("Add Task" if not task_data else "Edit Task")
        self.setFixedSize(450, 550)
        self.setStyleSheet("""
            QDialog {
                background-color: #2B2B2B;
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTimeEdit, QComboBox {
                background-color: #3B3B3B;
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 8px;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            /* Fix for Dropdown Menu */
            QComboBox QAbstractItemView {
                background-color: #3B3B3B;
                color: white;
                selection-background-color: #1F6AA5;
                selection-color: white;
                border: 1px solid #555555;
                outline: none;
                min-width: 50px;
            }
        """)
        
        self._setup_ui()
        

        
    def _setup_time_picker(self, default_time_str):
        """Create a composite time picker (HH:MM AM/PM)"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Parse default
        try:
            dt = datetime.strptime(default_time_str, "%H:%M")
            h_val = int(dt.strftime("%I"))
            m_val = dt.minute
            p_val = dt.strftime("%p")
        except:
            h_val = 9
            m_val = 0
            p_val = "AM"
            
        # Hour
        hour = QLineEdit()
        hour.setValidator(QIntValidator(1, 12))
        hour.setMaxLength(2)
        hour.setText(f"{h_val:02d}")
        hour.setPlaceholderText("HH")
        hour.setFixedWidth(40)
        hour.setAlignment(Qt.AlignCenter)
        hour.textChanged.connect(self._validate_form)
        
        # Minute
        minute = QLineEdit()
        minute.setValidator(QIntValidator(0, 59))
        minute.setMaxLength(2)
        minute.setText(f"{m_val:02d}")
        minute.setPlaceholderText("MM")
        minute.setFixedWidth(40)
        minute.setAlignment(Qt.AlignCenter)
        minute.textChanged.connect(self._validate_form)
        
        # AM/PM Toggle
        ampm = QPushButton(p_val)
        ampm.setFixedWidth(50)
        ampm.setCursor(Qt.PointingHandCursor)
        
        # Style like QLineEdit but clickable
        ampm.setStyleSheet("""
            QPushButton {
                background-color: #3B3B3B; /* Match input bg */
                color: white;
                border: 1px solid #555555;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4B4B4B;
                border: 1px solid #00BCD4; /* Cyan highlight */
            }
        """)
        
        def toggle_ampm():
            new_text = "PM" if ampm.text() == "AM" else "AM"
            ampm.setText(new_text)
            self._validate_form()
            
        ampm.clicked.connect(toggle_ampm)
        
        layout.addWidget(hour)
        # User requested NO separator
        layout.addWidget(minute)
        layout.addWidget(ampm)
        
        return container, hour, minute, ampm
        
    def _get_time_from_picker(self, h_box, m_box, p_box):
        """Convert picker values to 24h string"""
        try:
            h = int(h_box.text())
            m = int(m_box.text())
        except ValueError:
            h, m = 0, 0
            
        p = p_box.text() # Changed from currentText() to text() for QPushButton
        
        # Validate logic
        if h < 1: h = 1
        if h > 12: h = 12
        if m < 0: m = 0
        if m > 59: m = 59
        
        if p == "PM" and h != 12:
            h += 12
        elif p == "AM" and h == 12:
            h = 0
            
        return f"{h:02d}:{m:02d}"


    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        
        # Stacked frames for form/icon picker
        self.form_frame = QWidget()
        self.icons_frame = QWidget()
        
        self._setup_form()
        self._setup_icon_picker()
        
        self.main_layout.addWidget(self.form_frame)
        self.main_layout.addWidget(self.icons_frame)
        self.icons_frame.hide()
        
    def _setup_form(self):
        layout = QVBoxLayout(self.form_frame)
        layout.setSpacing(15)
        
        # Task name
        layout.addWidget(QLabel("Task Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter task name...")
        if self.task_data:
            self.name_input.setText(self.task_data.get('name', ''))
        self.name_input.textChanged.connect(self._validate_form)
        layout.addWidget(self.name_input)
        
        # Icon section
        layout.addWidget(QLabel("Icon:"))
        icon_row = QHBoxLayout()
        icon_row.setSpacing(10)
        
        # Show placeholder if no icon
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(60, 60)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setStyleSheet("background-color: #3B3B3B; border-radius: 10px;")
        self._update_icon_preview() # Initial state
        icon_row.addWidget(self.icon_preview)
        
        # Plain text buttons as requested
        self.change_btn = QPushButton("Select Icon")
        self.change_btn.setCursor(Qt.PointingHandCursor)
        self.change_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 15px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        self.change_btn.clicked.connect(self._show_icon_picker)
        icon_row.addWidget(self.change_btn)
        
        # Connector
        or_label = QLabel(" or ")
        or_label.setStyleSheet("color: #888888;")
        icon_row.addWidget(or_label)
        
        # New Custom Image button
        self.custom_img_btn = QPushButton("Custom Image")
        self.custom_img_btn.setCursor(Qt.PointingHandCursor)
        self.custom_img_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 15px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        self.custom_img_btn.clicked.connect(self._on_custom_image)
        icon_row.addWidget(self.custom_img_btn)
        
        icon_row.addStretch()
        layout.addLayout(icon_row)
        
        # Time inputs
        time_layout = QHBoxLayout()
        
        # Start Time
        time_layout.addWidget(QLabel("Start:"))
        start_default = self.task_data.get('start_time', '09:00') if self.task_data else datetime.now().strftime("%H:%M")
        s_widget, self.start_hour, self.start_min, self.start_ampm = self._setup_time_picker(start_default)
        time_layout.addWidget(s_widget)
        
        # End Time
        time_layout.addWidget(QLabel("End:"))
        end_default = self.task_data.get('end_time', '10:00') if self.task_data else (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        e_widget, self.end_hour, self.end_min, self.end_ampm = self._setup_time_picker(end_default)
        time_layout.addWidget(e_widget)
        
        layout.addLayout(time_layout)
        
        # Recurrence Section
        layout.addWidget(QLabel("Repeat Every:"))
        recurrence_layout = QHBoxLayout()
        recurrence_layout.setSpacing(10) # More spacing between days
        
        day_labels = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
        day_vals = [5, 6, 0, 1, 2, 3, 4]
        
        existing_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6]) if self.task_data else [0,1,2,3,4,5,6]
        
        self.day_buttons = {} # Map val -> button
        
        for label, val in zip(day_labels, day_vals):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(val in existing_days)
            btn.setFixedSize(40, 40)
            
            # Dynamic Styling driven by state
            # Blue (#1F6AA5) for Active, Dark Grey (#333333) for Inactive
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#1F6AA5' if btn.isChecked() else '#333333'};
                    color: {'white' if btn.isChecked() else '#888888'};
                    border: {'1px solid #1F6AA5' if btn.isChecked() else '1px solid #555555'};
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border-color: #00BCD4;
                }}
            """)
            
            # Toggle Logic
            def toggle_day(b=btn, v=val):
                is_checked = b.isChecked()
                # Update visual state immediately
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {'#1F6AA5' if is_checked else '#333333'};
                        color: {'white' if is_checked else '#888888'};
                        border: {'1px solid #1F6AA5' if is_checked else '1px solid #555555'};
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        border-color: #00BCD4;
                    }}
                """)
                self._validate_form()
                
            btn.clicked.connect(lambda checked, b=btn, v=val: toggle_day(b, v))
            
            recurrence_layout.addWidget(btn)
            self.day_buttons[val] = btn
            
        recurrence_layout.addStretch()
        layout.addLayout(recurrence_layout)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        if self.task_data:
            self.delete_btn = QPushButton("Delete")
            self.delete_btn.setStyleSheet("""
                QPushButton {
                    background-color: #D32F2F;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 10px 20px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
            """)
            self.delete_btn.clicked.connect(self._on_delete)
            btn_layout.addWidget(self.delete_btn)
            
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1F6AA5;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        
        # Initial validation
        # Initial validation
        self._validate_form()

    def _on_custom_image(self):
        """Open file dialog and copy selection to app cache"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Custom Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)"
        )
        
        if file_path:
            # 1. Update State to selected desktop file
            self.selected_icon = file_path
            self.forceRefresh()
            self._validate_form()

    def forceRefresh(self):
        """User-requested immediate preview redraw"""
        self._update_icon_preview()
        self.update() # Qt repaint

    def _update_icon_preview(self):
        """Intelligently display emoji or cached image in the preview box"""
        if not hasattr(self, 'icon_preview'): return
        
        try:
            icon_val = self.selected_icon if self.selected_icon else "❓"
            if not isinstance(icon_val, str): icon_val = str(icon_val)

            # Identify if this is a path
            is_path = any(s in icon_val.lower() for s in ['\\', '/', '.png', '.jpg', '.jpeg', '.webp'])
            
            if is_path:
                if not os.path.isabs(icon_val) and 'cache' in icon_val:
                    appdata = os.getenv('APPDATA', os.path.expanduser('~'))
                    resolved_path = os.path.normpath(os.path.join(appdata, 'DailyTasks', icon_val))
                else:
                    resolved_path = icon_val

                pixmap = QPixmap(resolved_path)
                if not pixmap.isNull():
                    self.icon_preview.setText("") 
                    self.icon_preview.setPixmap(pixmap.scaled(
                        45, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    ))
                    return
                else:
                    icon_val = '❓'
            
            # Render as Emoji
            self.icon_preview.setPixmap(QPixmap()) 
            self.icon_preview.setFont(QFont("Segoe UI Emoji", 32))
            self.icon_preview.setText(icon_val)
        except Exception as e:
            print(f"Error updating icon preview: {e}")
            self.icon_preview.setText('❓')

    def apply_theme(self, theme):
        """Apply light/dark theme to dialog"""
        self.current_theme = theme
        is_light = theme == "light"
        
        bg = "#F5F5F5" if is_light else "#2B2B2B"
        fg = "#333333" if is_light else "#FFFFFF"
        input_bg = "#FFFFFF" if is_light else "#333333"
        input_border = "#CCCCCC" if is_light else "#555555"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {fg};
            }}
            QLabel {{
                color: {fg};
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {input_border};
                border-radius: 5px;
                padding: 10px;
            }}
        """)
        
        # Determine Chevron Color (White for Dark, Black for Light)
        if is_light:
            # Black Chevron
            chevron_b64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImJsYWNrIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTYgOWw2IDYgNi02Ii8+PC9zdmc+"
        else:
            # White Chevron
            chevron_b64 = "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTYgOWw2IDYgNi02Ii8+PC9zdmc+"

        # Apply to Time Picker inputs if they exist
        inputs = [self.start_hour, self.start_min, self.end_hour, self.end_min]
        combos = [self.start_ampm, self.end_ampm]
        
        # Safety check if elements are initialized
        if all(hasattr(self, name) for name in ['start_hour', 'start_ampm']):
            input_style = f"""
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {input_border};
                border-radius: 5px;
                padding: 5px;
            """
            
            for inp in inputs:
                inp.setStyleSheet(f"QLineEdit {{ {input_style} }}")
                

        # Apply theme to Icon Preview and Buttons
        if hasattr(self, 'icon_preview'):
            preview_bg = "#FFFFFF" if is_light else "#3B3B3B"
            preview_border = f"1px solid {input_border}" if is_light else "none"
            self.icon_preview.setStyleSheet(f"background-color: {preview_bg}; border-radius: 10px; border: {preview_border};")

        # Helper for button styling
        def style_btn(btn, bg, fg, hover_bg):
            if hasattr(self, btn):
                getattr(self, btn).setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        color: {fg};
                        border: none;
                        border-radius: 5px;
                        padding: 10px {'20px' if 'change' not in btn else '15px'};
                    }}
                    QPushButton:hover {{
                        background-color: {hover_bg};
                    }}
                    QPushButton:disabled {{
                        background-color: {'#E0E0E0' if is_light else '#555555'};
                        color: {'#AAAAAA' if is_light else '#888888'};
                    }}
                """)

        # Button Colors
        if is_light:
            # Light Mode Buttons
            # Neutral (Cancel, Change): Light Grey
            neutral_bg = "#E0E0E0"
            neutral_fg = "#333333"
            neutral_hover = "#D0D0D0"
            
            # Primary (Save): Blue
            primary_bg = "#1F6AA5" 
            primary_fg = "white"
            primary_hover = "#2980B9"
            
            # Delete: Red
            delete_bg = "#D32F2F"
            delete_fg = "white"
            delete_hover = "#E53935"
        else:
            # Dark Mode Buttons
            neutral_bg = "#555555"
            neutral_fg = "white"
            neutral_hover = "#666666"
            
            primary_bg = "#1F6AA5"
            primary_fg = "white"
            primary_hover = "#2980B9"
            
            delete_bg = "#D32F2F"
            delete_fg = "white"
            delete_hover = "#E53935"
            
        style_btn('change_btn', neutral_bg, neutral_fg, neutral_hover)
        style_btn('custom_img_btn', neutral_bg, neutral_fg, neutral_hover)
        style_btn('cancel_btn', neutral_bg, neutral_fg, neutral_hover)
        style_btn('save_btn', primary_bg, primary_fg, primary_hover)
        style_btn('delete_btn', delete_bg, delete_fg, delete_hover)

        
        # Recurrence Buttons Theme
        # We need to refresh their style based on current theme + checked state
        if hasattr(self, 'day_buttons'):
            unchecked_bg = "#E0E0E0" if is_light else "#333333"
            unchecked_fg = "#333333" if is_light else "#888888"
            unchecked_border = "#CCCCCC" if is_light else "#555555"
            
            for val, btn in self.day_buttons.items():
                is_checked = btn.isChecked()
                # If checked, keep blue. If unchecked, use theme colors.
                bg = "#1F6AA5" if is_checked else unchecked_bg
                fg = "white" if is_checked else unchecked_fg
                border = "#1F6AA5" if is_checked else unchecked_border
                
                # Update the dynamic style for this button
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        color: {fg};
                        border: 1px solid {border};
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        border-color: #00BCD4;
                    }}
                """)


    def _setup_icon_picker(self):
        layout = QVBoxLayout(self.icons_frame)
        
        # Header
        header = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00E5FF;
                border: 1px solid #00E5FF;
                border-radius: 5px;
                padding: 5px 10px;
            }
        """)
        back_btn.clicked.connect(self._show_form)
        header.addWidget(back_btn)
        
        title = QLabel("Select Icon")
        title.setFont(QFont("Roboto", 16, QFont.Bold))
        header.addWidget(title)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Scrollable icon grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        cols = 8
        for category, icons in self.icon_categories.items():
            # Category header
            cat_label = QLabel(category)
            cat_label.setFont(QFont("Roboto", 12, QFont.Bold))
            cat_label.setStyleSheet("color: #888888;")
            scroll_layout.addWidget(cat_label)
            
            # Icon grid
            grid = QGridLayout()
            grid.setSpacing(5)
            for i, icon in enumerate(icons):
                btn = QPushButton(icon)
                btn.setFont(QFont("Segoe UI Emoji", 18))
                btn.setFixedSize(40, 40)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #1F6AA5;
                    }
                """)
                btn.clicked.connect(lambda checked, ic=icon: self._select_icon(ic))
                grid.addWidget(btn, i // cols, i % cols)
                
            scroll_layout.addLayout(grid)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
    def _show_icon_picker(self):
        self.form_frame.hide()
        self.icons_frame.show()
        
    def _show_form(self):
        self.icons_frame.hide()
        self.form_frame.show()
        
    def _select_icon(self, icon):
        self.selected_icon = icon
        self._update_icon_preview()
        self._show_form()
        
    def _on_delete(self):
        # Signal parent to delete
        self.done(2)  # Custom result code for delete

    def accept(self):
        """Validate input before saving"""
        if not self.name_input.text().strip():
            ModernDialogs.show_message(self, "Required", "Please enter a task name.", theme=self.current_theme)
            return
            
        # Icon is now optional
        
        super().accept()
        
    def _validate_form(self):
        """Enable save button only if inputs are valid"""
        if not hasattr(self, 'save_btn'):
            return
            
        valid = True
        
        # Name required
        if not self.name_input.text().strip():
            valid = False
            
        # Time validation
        try:
            sh = int(self.start_hour.text())
            sm = int(self.start_min.text())
            eh = int(self.end_hour.text())
            em = int(self.end_min.text())
            
            if not (1 <= sh <= 12 and 0 <= sm <= 59): valid = False
            if not (1 <= eh <= 12 and 0 <= em <= 59): valid = False
            
            # Validate start time is before end time
            if valid:
                # Convert to 24h for comparison
                start_period = self.start_ampm.text()
                end_period = self.end_ampm.text()
                
                # Convert to 24h format
                if start_period == 'AM':
                    start_24h = 0 if sh == 12 else sh
                else:  # PM
                    start_24h = 12 if sh == 12 else sh + 12
                
                if end_period == 'AM':
                    end_24h = 0 if eh == 12 else eh
                else:  # PM
                    end_24h = 12 if eh == 12 else eh + 12
                
                # Compare times (hour * 60 + min)
                start_mins = start_24h * 60 + sm
                end_mins = end_24h * 60 + em
                
                # Start must be before end (allow overnight tasks like 11PM to 1AM)
                # Only block if SAME DAY and start >= end
                # Allow overnight: e.g., 11PM (start_mins=1380) to 1AM (end_mins=60) is OK
                if start_mins >= end_mins and not (start_period == 'PM' and end_period == 'AM'):
                    valid = False
                    
        except ValueError:
            valid = False
            
        self.save_btn.setEnabled(valid)
        
    def get_task_data(self):
        """Return the entered task data"""
        # Recurrence
        repeat_days = []
        for val, btn in self.day_buttons.items():
            if btn.isChecked():
                repeat_days.append(val)
        repeat_days.sort()
            
        # Handle Save & Copy Logic for Custom Images
        final_icon_path = self.selected_icon
        if final_icon_path:
            is_path = any(s in final_icon_path.lower() for s in ['\\', '/', '.png', '.jpg', '.jpeg', '.webp'])
            if is_path and os.path.isabs(final_icon_path) and 'cache' not in final_icon_path:
                # It's an absolute path from the user's disk; we need to cache it NOW (on Save)
                appdata = os.getenv('APPDATA', os.path.expanduser('~'))
                cache_dir = os.path.join(appdata, 'DailyTasks', 'cache')
                os.makedirs(cache_dir, exist_ok=True)
                
                ext = os.path.splitext(final_icon_path)[1]
                unique_name = f"custom_{uuid.uuid4().hex}{ext}"
                absolute_cache_path = os.path.join(cache_dir, unique_name)
                
                try:
                    shutil.copy2(final_icon_path, absolute_cache_path)
                    # The Default Path is now the RELATIVE cache path!
                    final_icon_path = os.path.join('cache', unique_name)
                except Exception as e:
                    print(f"Failed to cache image on save: {e}")
                    final_icon_path = '❓'

        return {
            'name': self.name_input.text(),
            'image_path': final_icon_path,
            'start_time': self._get_time_from_picker(self.start_hour, self.start_min, self.start_ampm),
            'end_time': self._get_time_from_picker(self.end_hour, self.end_min, self.end_ampm),
            'repeat_days': repeat_days
        }
