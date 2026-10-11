"""
Qt-based UI Components for Daily Tasks
Full feature parity with original CustomTkinter version
"""

from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, 
    QPushButton as _QtPushButton, QGraphicsDropShadowEffect, QScrollArea,
    QWidget, QGridLayout, QLineEdit, QTimeEdit, QDialog,
    QDialogButtonBox, QComboBox, QGraphicsOpacityEffect,
    QToolTip, QCheckBox, QSizePolicy, QFileDialog, QSlider,
    QStyle, QStyleOptionButton, QStyledItemDelegate, QProgressBar
)
from PySide6.QtGui import (
    QFont, QColor, QIntValidator, QPixmap, QCursor, QDrag, QPainter,
    QLinearGradient, QPen, QPainterPath
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QVariantAnimation, QEasingCurve,
    QTime, QTimer, Property, QMimeData, QByteArray, QObject, QEvent,
    QPoint, QPointF, QSize, QRectF
)
from datetime import datetime, timedelta
import math
import os
import sys
import shutil
import uuid
from .constants import APP_VERSION

_TIME_FMT_CACHE = {}



def _draw_dashed_rounded_rect(
    painter: QPainter,
    rect: QRectF,
    radius: float,
    brush,
    border_col: QColor,
    pen_w: float,
    target_cycle_px: float = 12.0,
    solid: bool = False,
):
    """
    Draws a rounded rectangle with a seamless, continuous antialiased dashed (or solid) border.
    Eliminates Qt stylesheet's QStyleSheetStyle dashed border bug, which splits rounded rects into
    8 separate half-corner arcs and 4 straight segments that overlap at 45-degree corner midpoints
    and create extra dots/pixelation.
    """
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.setBrush(brush)
    if solid:
        painter.setPen(QPen(border_col, pen_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        return
    perim = path.length()
    n_dashes = max(8, int(round(perim / max(4.0, target_cycle_px))))
    cycle_u = (perim / max(0.5, pen_w)) / n_dashes
    dash_u = cycle_u * 0.46
    gap_u = cycle_u - dash_u
    pen = QPen(border_col, pen_w, Qt.CustomDashLine, Qt.RoundCap, Qt.RoundJoin)
    pen.setDashPattern([dash_u, gap_u])
    pen.setDashOffset(gap_u * 0.5)
    painter.setPen(pen)
    painter.drawPath(path)



class AnimatedPushButton(_QtPushButton):
    """
    Global interactive button with smooth 60fps hover and click micro-animations.
    - Hover State: 145ms OutCubic scale/elevation (~1.02x) + smooth brightness/glow cross-fade.
    - Active/Click State: 70ms OutQuad tactile compression (~0.965x + depth shift) on press,
      135ms OutCubic release on mouse up.
    - Layout Stability: Renders entirely via QPainter transforms inside paintEvent so widget
      geometry and neighboring layouts never shift or reflow.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover_t = 0.0
        self._press_t = 0.0
        self._hover_anim = None
        self._press_anim = None
        self.setAttribute(Qt.WA_Hover, True)

    def _animate_hover(self, target: float):
        if not self.isEnabled():
            self._hover_t = 0.0
            self.update()
            return
        if self._hover_anim is None:
            self._hover_anim = QVariantAnimation(self)
            self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._hover_anim.valueChanged.connect(self._on_hover_step)
        self._hover_anim.stop()
        self._hover_anim.setDuration(145)
        self._hover_anim.setStartValue(float(self._hover_t))
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    def _animate_press(self, target: float, duration: int = 70, curve=QEasingCurve.OutQuad):
        if self._press_anim is None:
            self._press_anim = QVariantAnimation(self)
            self._press_anim.valueChanged.connect(self._on_press_step)
        self._press_anim.stop()
        self._press_anim.setDuration(duration)
        self._press_anim.setEasingCurve(curve)
        self._press_anim.setStartValue(float(self._press_t))
        self._press_anim.setEndValue(float(target))
        self._press_anim.start()

    def _on_hover_step(self, val):
        self._hover_t = float(val)
        self.update()

    def _on_press_step(self, val):
        self._press_t = float(val)
        self.update()

    def enterEvent(self, event):
        if self.isEnabled():
            self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        if self._press_t > 0.0:
            self._animate_press(0.0, duration=135, curve=QEasingCurve.OutCubic)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._animate_press(1.0, duration=70, curve=QEasingCurve.OutQuad)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press_t > 0.0:
            self._animate_press(0.0, duration=135, curve=QEasingCurve.OutCubic)
        super().mouseReleaseEvent(event)

    def hideEvent(self, event):
        if self._hover_anim is not None:
            self._hover_anim.stop()
        if self._press_anim is not None:
            self._press_anim.stop()
        self._hover_t = 0.0
        self._press_t = 0.0
        super().hideEvent(event)

    def sizeHint(self):
        s = super().sizeHint()
        if self.property("no_inset"):
            return s
        return QSize(s.width() + 4, s.height() + 4)

    def minimumSizeHint(self):
        s = super().minimumSizeHint()
        if self.property("no_inset"):
            return s
        return QSize(s.width() + 4, s.height() + 4)

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        if w <= 4 or h <= 4:
            super().paintEvent(event)
            return

        enabled = self.isEnabled()
        ht = self._hover_t if enabled else 0.0
        pt = self._press_t if enabled else 0.0

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Constant 2px inset rect per button + clip-bounded uniform scale:
        # Guarantees 0% border clipping on hover while keeping opt.rect invariant across enabled/disabled states.
        if w < 28 or h < 28 or self.property("no_inset"):
            pad_x = 1 if w >= 20 else 0
            pad_y = 1 if h >= 20 else 0
            hover_grow = 0.0
            y_lift = 0.0
        else:
            pad_x = 2
            pad_y = 2
            rx = max(1.0, (w * 0.5) - pad_x)
            ry = max(1.0, (h * 0.5) - pad_y)
            y_lift = 0.4
            hover_grow = min(0.018, (pad_x - 0.8) / rx, max(0.005, (pad_y - 0.8 - y_lift) / ry))

        scale = 1.0 + (hover_grow * ht) - (0.035 * pt)
        y_off = (-y_lift * ht) + (0.7 * pt)

        if abs(scale - 1.0) > 0.0005 or abs(y_off) > 0.01:
            cx = w * 0.5
            cy = h * 0.5
            painter.translate(cx, cy + y_off)
            painter.scale(scale, scale)
            painter.translate(-cx, -cy)

        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        if pad_x > 0 or pad_y > 0:
            opt.rect = self.rect().adjusted(pad_x, pad_y, -pad_x, -pad_y)

        # Draw bevel (background + border) and label separately so CSS padding never clips bold text glyphs
        self.style().drawControl(QStyle.CE_PushButtonBevel, opt, painter, self)
        label_opt = QStyleOptionButton(opt)
        label_opt.rect = opt.rect.adjusted(2, 0, -2, 0)
        self.style().drawControl(QStyle.CE_PushButtonLabel, label_opt, painter, self)

        draw_rect = QRectF(opt.rect).adjusted(1.0, 1.0, -1.0, -1.0)
        radius = min(8.0, draw_rect.height() * 0.45)

        if ht > 0.01 and pt < 0.8:
            glow_alpha = int(16 * ht * (1.0 - 0.5 * pt))
            if glow_alpha > 0:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, glow_alpha))
                painter.drawRoundedRect(draw_rect, radius, radius)

        if pt > 0.01:
            press_alpha = int(28 * pt)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, press_alpha))
            painter.drawRoundedRect(draw_rect, radius, radius)

        painter.end()


QPushButton = AnimatedPushButton


# Ordered list of (theme_key, display_name) for the Settings dropdown
THEME_OPTIONS = [
    ("dark", "Classic Dark"),
    ("midnight", "Midnight Blue"),
    ("nord", "Frost Blue"),
    ("cyberpunk", "Neon Cyan"),
    ("emerald", "Emerald Green"),
    ("obsidian", "Obsidian Black"),
    ("nebula", "Cosmic Purple"),
    ("crimson", "Crimson Red"),
    ("sunset_light", "Solar Light"),
    ("light", "Aurora Light"),
]

THEME_DEFINITIONS = {
    "dark": {
        "name": "Classic Dark",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0D0D0D, stop:0.5 #141414, stop:1 #1A1A1A)",
        "titlebar_bg": "#1A1A1A",
        "titlebar_border": "#333333",
        "title_fg": "#E0E0E0",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(26, 26, 26, 238), stop:1 rgba(34, 34, 34, 242))",
        "sidebar_border": "rgba(255, 255, 255, 24)",
        "panel_bg": "rgba(30, 30, 30, 248)",
        "panel_border": "#444444",
        "dialog_bg": "#1E1E1E",
        "input_bg": "#2B2B2B",
        "input_border": "#484848",
        "text_main": "#F5F5F5",
        "text_muted": "#9E9E9E",
        "accent": "#2196F3",
        "accent_rgb": (33, 150, 243),
        "accent_primary": "#1976D2",
        "accent_hover": "#42A5F5",
        "card_bg1": (45, 45, 45, 225),
        "card_bg2": (30, 30, 30, 235),
        "card_hover_bg1": (58, 58, 58, 235),
        "card_border": (120, 120, 120, 75),
        "card_hover_border": (33, 150, 243, 185),
        "active_bg1": (21, 101, 192, 220),
        "active_bg2": (26, 35, 60, 235),
        "active_border": (66, 165, 245, 230),
        "done_bg1": (46, 125, 50, 220),
        "done_bg2": (24, 48, 28, 235),
        "done_border": (102, 187, 106, 225),
        "failed_bg1": (198, 40, 40, 220),
        "failed_bg2": (52, 20, 24, 235),
        "failed_border": (239, 83, 80, 225),
    },
    "midnight": {
        "name": "Midnight Blue",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #080C14, stop:0.5 #0D1424, stop:1 #0F172A)",
        "titlebar_bg": "#080C14",
        "titlebar_border": "rgba(148, 163, 184, 28)",
        "title_fg": "#CBD5E1",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(11, 15, 25, 225), stop:1 rgba(15, 23, 42, 235))",
        "sidebar_border": "rgba(148, 163, 184, 28)",
        "panel_bg": "rgba(15, 23, 42, 248)",
        "panel_border": "rgba(56, 189, 248, 80)",
        "dialog_bg": "#0F172A",
        "input_bg": "#1E293B",
        "input_border": "#334155",
        "text_main": "#F8FAFC",
        "text_muted": "#94A3B8",
        "accent": "#38BDF8",
        "accent_rgb": (56, 189, 248),
        "accent_primary": "#0284C7",
        "accent_hover": "#0EA5E9",
        "card_bg1": (30, 41, 59, 195),
        "card_bg2": (15, 23, 42, 225),
        "card_hover_bg1": (39, 52, 73, 215),
        "card_border": (148, 163, 184, 52),
        "card_hover_border": (56, 189, 248, 155),
        "active_bg1": (12, 74, 110, 205),
        "active_bg2": (30, 27, 75, 235),
        "active_border": (56, 189, 248, 220),
        "done_bg1": (6, 78, 59, 200),
        "done_bg2": (15, 23, 42, 235),
        "done_border": (52, 211, 153, 195),
        "failed_bg1": (136, 19, 55, 200),
        "failed_bg2": (24, 16, 36, 235),
        "failed_border": (251, 113, 133, 195),
    },
    "obsidian": {
        "name": "Obsidian Black",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #000000, stop:0.55 #040407, stop:1 #09090F)",
        "titlebar_bg": "#000000",
        "titlebar_border": "rgba(129, 140, 248, 34)",
        "title_fg": "#E2E8F0",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(3, 3, 5, 242), stop:1 rgba(10, 10, 16, 246))",
        "sidebar_border": "rgba(129, 140, 248, 30)",
        "panel_bg": "rgba(8, 8, 14, 250)",
        "panel_border": "rgba(129, 140, 248, 90)",
        "dialog_bg": "#07070C",
        "input_bg": "#11111A",
        "input_border": "#27273A",
        "text_main": "#F8FAFC",
        "text_muted": "#94A3B8",
        "accent": "#818CF8",
        "accent_rgb": (129, 140, 248),
        "accent_primary": "#4F46E5",
        "accent_hover": "#6366F1",
        "card_bg1": (16, 16, 24, 225),
        "card_bg2": (7, 7, 11, 242),
        "card_hover_bg1": (26, 26, 38, 235),
        "card_border": (148, 163, 184, 42),
        "card_hover_border": (129, 140, 248, 175),
        "active_bg1": (49, 46, 129, 215),
        "active_bg2": (10, 10, 22, 242),
        "active_border": (129, 140, 248, 230),
        "done_bg1": (6, 78, 59, 210),
        "done_bg2": (8, 14, 14, 242),
        "done_border": (52, 211, 153, 210),
        "failed_bg1": (136, 19, 55, 210),
        "failed_bg2": (16, 8, 14, 242),
        "failed_border": (251, 113, 133, 210),
    },
    "light": {
        "name": "Aurora Light",
        "is_light": True,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #DBEAFE, stop:0.5 #E2E8F0, stop:1 #D1FAE5)",
        "titlebar_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #DBEAFE, stop:0.5 #E2E8F0, stop:1 #D1FAE5)",
        "titlebar_border": "#94A3B8",
        "title_fg": "#0F172A",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(219, 234, 254, 175), stop:1 rgba(203, 213, 225, 190))",
        "sidebar_border": "rgba(100, 116, 139, 135)",
        "panel_bg": "rgba(255, 255, 255, 252)",
        "panel_border": "#CBD5E1",
        "dialog_bg": "#F8FAFC",
        "input_bg": "#FFFFFF",
        "input_border": "#CBD5E1",
        "text_main": "#0F172A",
        "text_muted": "#475569",
        "accent": "#0284C7",
        "accent_rgb": (2, 132, 199),
        "accent_primary": "#0284C7",
        "accent_hover": "#0EA5E9",
        "card_bg1": (226, 232, 240, 165),
        "card_bg2": (203, 213, 225, 180),
        "card_hover_bg1": (203, 213, 225, 195),
        "card_border": (100, 116, 139, 185),
        "card_hover_border": (2, 132, 199, 235),
        "active_bg1": (186, 230, 253, 180),
        "active_bg2": (125, 211, 252, 192),
        "active_border": (2, 132, 199, 245),
        "done_bg1": (167, 243, 208, 175),
        "done_bg2": (110, 231, 183, 188),
        "done_border": (5, 150, 105, 240),
        "failed_bg1": (254, 205, 211, 178),
        "failed_bg2": (253, 164, 175, 190),
        "failed_border": (225, 29, 72, 240),
    },
    "nebula": {
        "name": "Cosmic Purple",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0F071E, stop:0.5 #1A0B2E, stop:1 #120924)",
        "titlebar_bg": "#0C0517",
        "titlebar_border": "rgba(232, 121, 249, 38)",
        "title_fg": "#F5D0FE",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(18, 8, 34, 232), stop:1 rgba(28, 12, 50, 238))",
        "sidebar_border": "rgba(232, 121, 249, 35)",
        "panel_bg": "rgba(24, 11, 44, 248)",
        "panel_border": "rgba(232, 121, 249, 95)",
        "dialog_bg": "#160A29",
        "input_bg": "#241242",
        "input_border": "#4C1D95",
        "text_main": "#FAF5FF",
        "text_muted": "#D8B4FE",
        "accent": "#E879F9",
        "accent_rgb": (232, 121, 249),
        "accent_primary": "#9333EA",
        "accent_hover": "#A855F7",
        "card_bg1": (46, 22, 84, 205),
        "card_bg2": (24, 11, 44, 230),
        "card_hover_bg1": (62, 30, 110, 220),
        "card_border": (192, 132, 252, 62),
        "card_hover_border": (232, 121, 249, 180),
        "active_bg1": (107, 33, 168, 215),
        "active_bg2": (36, 14, 68, 235),
        "active_border": (232, 121, 249, 235),
        "done_bg1": (6, 95, 70, 205),
        "done_bg2": (20, 14, 42, 235),
        "done_border": (52, 211, 153, 210),
        "failed_bg1": (159, 18, 57, 210),
        "failed_bg2": (28, 10, 38, 235),
        "failed_border": (251, 113, 133, 210),
    },
    "emerald": {
        "name": "Emerald Green",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #04130E, stop:0.5 #062018, stop:1 #071914)",
        "titlebar_bg": "#030F0B",
        "titlebar_border": "rgba(52, 211, 153, 38)",
        "title_fg": "#D1FAE5",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(5, 22, 16, 232), stop:1 rgba(8, 32, 24, 238))",
        "sidebar_border": "rgba(52, 211, 153, 35)",
        "panel_bg": "rgba(6, 28, 21, 248)",
        "panel_border": "rgba(52, 211, 153, 90)",
        "dialog_bg": "#061C15",
        "input_bg": "#0D3327",
        "input_border": "#115E59",
        "text_main": "#ECFDF5",
        "text_muted": "#6EE7B7",
        "accent": "#34D399",
        "accent_rgb": (52, 211, 153),
        "accent_primary": "#059669",
        "accent_hover": "#10B981",
        "card_bg1": (13, 51, 39, 205),
        "card_bg2": (6, 26, 20, 230),
        "card_hover_bg1": (19, 70, 54, 220),
        "card_border": (52, 211, 153, 62),
        "card_hover_border": (52, 211, 153, 180),
        "active_bg1": (13, 148, 136, 215),
        "active_bg2": (6, 36, 32, 235),
        "active_border": (45, 212, 191, 235),
        "done_bg1": (5, 122, 85, 215),
        "done_bg2": (4, 32, 24, 235),
        "done_border": (110, 231, 183, 230),
        "failed_bg1": (159, 18, 57, 210),
        "failed_bg2": (24, 12, 20, 235),
        "failed_border": (251, 113, 133, 210),
    },
    "crimson": {
        "name": "Crimson Red",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #16070B, stop:0.5 #240B13, stop:1 #1A090E)",
        "titlebar_bg": "#110508",
        "titlebar_border": "rgba(251, 113, 133, 38)",
        "title_fg": "#FFE4E6",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(24, 8, 13, 232), stop:1 rgba(36, 11, 19, 238))",
        "sidebar_border": "rgba(251, 113, 133, 35)",
        "panel_bg": "rgba(31, 10, 17, 248)",
        "panel_border": "rgba(251, 113, 133, 90)",
        "dialog_bg": "#1C080E",
        "input_bg": "#33101B",
        "input_border": "#881337",
        "text_main": "#FFF1F2",
        "text_muted": "#FDA4AF",
        "accent": "#FB7185",
        "accent_rgb": (251, 113, 133),
        "accent_primary": "#E11D48",
        "accent_hover": "#F43F5E",
        "card_bg1": (54, 17, 29, 205),
        "card_bg2": (26, 8, 14, 230),
        "card_hover_bg1": (74, 23, 39, 220),
        "card_border": (251, 113, 133, 62),
        "card_hover_border": (251, 113, 133, 185),
        "active_bg1": (180, 83, 9, 215),
        "active_bg2": (38, 14, 14, 235),
        "active_border": (251, 191, 36, 235),
        "done_bg1": (6, 95, 70, 210),
        "done_bg2": (18, 22, 20, 235),
        "done_border": (52, 211, 153, 215),
        "failed_bg1": (190, 18, 60, 220),
        "failed_bg2": (38, 8, 18, 235),
        "failed_border": (253, 164, 175, 230),
    },
    "nord": {
        "name": "Frost Blue",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1E222A, stop:0.5 #242933, stop:1 #2E3440)",
        "titlebar_bg": "#191D24",
        "titlebar_border": "#3B4252",
        "title_fg": "#ECEFF4",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(30, 34, 42, 235), stop:1 rgba(46, 52, 64, 240))",
        "sidebar_border": "rgba(136, 192, 208, 35)",
        "panel_bg": "rgba(46, 52, 64, 248)",
        "panel_border": "#88C0D0",
        "dialog_bg": "#2E3440",
        "input_bg": "#3B4252",
        "input_border": "#4C566A",
        "text_main": "#ECEFF4",
        "text_muted": "#D8DEE9",
        "accent": "#88C0D0",
        "accent_rgb": (136, 192, 208),
        "accent_primary": "#5E81AC",
        "accent_hover": "#81A1C1",
        "card_bg1": (59, 66, 82, 215),
        "card_bg2": (46, 52, 64, 235),
        "card_hover_bg1": (67, 76, 94, 228),
        "card_border": (136, 192, 208, 65),
        "card_hover_border": (136, 192, 208, 190),
        "active_bg1": (94, 129, 172, 220),
        "active_bg2": (46, 52, 64, 235),
        "active_border": (136, 192, 208, 235),
        "done_bg1": (76, 116, 84, 215),
        "done_bg2": (42, 52, 48, 235),
        "done_border": (163, 190, 140, 225),
        "failed_bg1": (150, 62, 72, 215),
        "failed_bg2": (52, 38, 44, 235),
        "failed_border": (191, 97, 106, 225),
    },
    "cyberpunk": {
        "name": "Neon Cyan",
        "is_light": False,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0D0221, stop:0.5 #150734, stop:1 #1F093D)",
        "titlebar_bg": "#090117",
        "titlebar_border": "rgba(0, 240, 255, 55)",
        "title_fg": "#00F0FF",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(14, 3, 33, 235), stop:1 rgba(26, 7, 56, 240))",
        "sidebar_border": "rgba(255, 42, 133, 55)",
        "panel_bg": "rgba(18, 5, 42, 250)",
        "panel_border": "#00F0FF",
        "dialog_bg": "#12042B",
        "input_bg": "#220A4D",
        "input_border": "#FF2A85",
        "text_main": "#F8FAFC",
        "text_muted": "#F472B6",
        "accent": "#00F0FF",
        "accent_rgb": (0, 240, 255),
        "accent_primary": "#FF2A85",
        "accent_hover": "#FF55A3",
        "card_bg1": (38, 12, 82, 210),
        "card_bg2": (18, 4, 42, 235),
        "card_hover_bg1": (56, 18, 115, 225),
        "card_border": (255, 42, 133, 95),
        "card_hover_border": (0, 240, 255, 215),
        "active_bg1": (180, 18, 105, 220),
        "active_bg2": (24, 8, 58, 235),
        "active_border": (0, 240, 255, 245),
        "done_bg1": (6, 95, 70, 215),
        "done_bg2": (14, 18, 44, 235),
        "done_border": (52, 211, 153, 230),
        "failed_bg1": (190, 18, 60, 225),
        "failed_bg2": (32, 6, 36, 235),
        "failed_border": (255, 42, 133, 240),
    },
    "sunset_light": {
        "name": "Solar Light",
        "is_light": True,
        "window_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFEDD5, stop:0.5 #FCE7F3, stop:1 #FEF3C7)",
        "titlebar_bg": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFEDD5, stop:0.5 #FCE7F3, stop:1 #FEF3C7)",
        "titlebar_border": "#FDBA74",
        "title_fg": "#431407",
        "sidebar_bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255, 237, 213, 185), stop:1 rgba(252, 231, 243, 195))",
        "sidebar_border": "rgba(234, 88, 12, 95)",
        "panel_bg": "rgba(255, 251, 235, 252)",
        "panel_border": "#FDBA74",
        "dialog_bg": "#FFFBEB",
        "input_bg": "#FFFFFF",
        "input_border": "#FDBA74",
        "text_main": "#431407",
        "text_muted": "#9A3412",
        "accent": "#EA580C",
        "accent_rgb": (234, 88, 12),
        "accent_primary": "#EA580C",
        "accent_hover": "#F97316",
        "card_bg1": (255, 237, 213, 175),
        "card_bg2": (254, 215, 170, 185),
        "card_hover_bg1": (254, 215, 170, 210),
        "card_border": (234, 88, 12, 155),
        "card_hover_border": (225, 29, 72, 235),
        "active_bg1": (254, 215, 170, 200),
        "active_bg2": (253, 186, 116, 210),
        "active_border": (234, 88, 12, 245),
        "done_bg1": (167, 243, 208, 180),
        "done_bg2": (110, 231, 183, 195),
        "done_border": (5, 150, 105, 240),
        "failed_bg1": (254, 205, 211, 185),
        "failed_bg2": (253, 164, 175, 198),
        "failed_border": (225, 29, 72, 240),
    },
}


def get_theme_spec(theme: str) -> dict:
    """Return theme specification dictionary for a theme key (fallback to 'dark')."""
    return THEME_DEFINITIONS.get(theme, THEME_DEFINITIONS["dark"])


def is_light_theme(theme: str) -> bool:
    """Return True if the given theme key uses a light daylight palette."""
    return bool(get_theme_spec(theme).get("is_light", False))


def apply_window_theme_frame(widget, theme: str):
    """Apply active theme colors to a native Windows dialog/window title bar via DWM."""
    if sys.platform != "win32" or widget is None:
        return
    try:
        from PySide6.QtWidgets import QApplication
        if QApplication.platformName() != "windows":
            return
        if not widget.isVisible() and not widget.testAttribute(Qt.WA_WState_Created):
            return
        import ctypes
        from ctypes import wintypes

        spec = get_theme_spec(theme)
        is_light = bool(spec.get("is_light", False))
        hwnd = int(widget.winId())
        if not hwnd:
            return
        dwmapi = ctypes.windll.dwmapi

        # 1. Immersive dark mode flag (Windows 10 1809+ & Windows 11, attribute 20 / fallback 19)
        dark_mode = ctypes.c_int(0 if is_light else 1)
        res = dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            20,
            ctypes.byref(dark_mode),
            ctypes.sizeof(dark_mode),
        )
        if res != 0:
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                19,
                ctypes.byref(dark_mode),
                ctypes.sizeof(dark_mode),
            )

        # 2. Exact caption background color (Windows 11 Build 22000+, DWMWA_CAPTION_COLOR = 35)
        raw_caption = spec.get("titlebar_bg", "")
        caption_col = QColor(raw_caption) if str(raw_caption).startswith("#") else QColor(spec["dialog_bg"])
        if caption_col.isValid():
            colorref = ctypes.c_uint32(
                caption_col.red() | (caption_col.green() << 8) | (caption_col.blue() << 16)
            )
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                35,
                ctypes.byref(colorref),
                ctypes.sizeof(colorref),
            )

        # 3. Exact caption title text color (Windows 11 Build 22000+, DWMWA_TEXT_COLOR = 36)
        text_col = QColor(spec.get("title_fg", spec["text_main"]))
        if text_col.isValid():
            text_colorref = ctypes.c_uint32(
                text_col.red() | (text_col.green() << 8) | (text_col.blue() << 16)
            )
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                36,
                ctypes.byref(text_colorref),
                ctypes.sizeof(text_colorref),
            )
    except Exception:
        pass


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
        spec = get_theme_spec(theme)
        bg = spec["dialog_bg"]
        fg = spec["text_main"]
        input_bg = spec["input_bg"]
        input_border = spec["input_border"]
        focus_border = spec["accent"]

        dialog.current_theme = theme
        dialog.setAttribute(Qt.WA_StyledBackground, True)
        dialog.setAutoFillBackground(True)
        pal = dialog.palette()
        pal.setColor(dialog.backgroundRole(), QColor(bg))
        pal.setColor(dialog.foregroundRole(), QColor(fg))
        dialog.setPalette(pal)
        dialog.ensurePolished()
        dialog.setStyleSheet(f"""
            QDialog {{ background-color: {bg}; color: {fg}; }}
            QLabel {{ color: {fg}; font-family: 'Segoe UI'; font-size: 13px; background: transparent; }}
            QLineEdit, QTextEdit {{
                background-color: {input_bg}; color: {fg};
                border: 1px solid {input_border};
                border-radius: 8px; padding: 8px 10px; font-family: 'Segoe UI'; font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {focus_border};
            }}
            QPushButton {{ padding: 8px 18px; border-radius: 8px; font-family: 'Segoe UI'; font-size: 12px; font-weight: bold; border: none; }}
        """)
        dialog.style().unpolish(dialog)
        dialog.style().polish(dialog)
        apply_window_theme_frame(dialog, theme)
        
    @staticmethod
    def _style_btn(btn, mode, theme):
        spec = get_theme_spec(theme)
        is_light = spec["is_light"]
        if mode == "primary":
            bg, hover = spec["accent_primary"], spec["accent_hover"]
            fg = "#FFFFFF"
            border = f"1px solid {spec['accent']}"
        elif mode == "danger":
            bg, hover = "#E11D48", "#F43F5E"
            fg = "#FFFFFF"
            border = "1px solid rgba(251, 113, 133, 90)"
        else:
            bg = "#E2E8F0" if is_light else spec["input_bg"]
            hover = "#CBD5E1" if is_light else spec["input_border"]
            fg = spec["text_main"]
            border = f"1px solid {spec['input_border']}"
            
        btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: {bg}; 
                color: {fg}; 
                border: {border};
                border-radius: 8px;
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
                background-color: #080C14;
                border-bottom: 1px solid rgba(148, 163, 184, 28);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)

        # App title on the left
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.title_label.setStyleSheet("color: #CBD5E1; padding-left: 4px; letter-spacing: 0.4px;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Minimize button
        self.min_btn = QPushButton("─")
        self.min_btn.setFixedSize(40, 30)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94A3B8;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(148, 163, 184, 28);
                color: #F8FAFC;
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
                color: #94A3B8;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(148, 163, 184, 28);
                color: #F8FAFC;
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
                color: #94A3B8;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #E11D48;
                color: #FFFFFF;
            }
        """)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)

    def update_max_button_icon(self, is_maximized):
        """Update Maximize/Restore button icon depending on state"""
        self.max_btn.setText("🗗" if is_maximized else "🗖")
    
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
        spec = get_theme_spec(theme)
        is_light = spec["is_light"]
        self.setStyleSheet(f"""
            #CustomTitleBar {{
                background: {spec['titlebar_bg']};
                border-bottom: 1px solid {spec['titlebar_border']};
            }}
        """)
        btn_fg = spec["text_muted"]
        btn_hover_bg = "rgba(0, 0, 0, 18)" if is_light else "rgba(255, 255, 255, 22)"
        btn_hover_fg = spec["text_main"]
        self.min_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {btn_fg};
                border: none;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
                color: {btn_hover_fg};
            }}
        """)
        self.max_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {btn_fg};
                border: none;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
                color: {btn_hover_fg};
            }}
        """)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {btn_fg};
                border: none;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #E11D48;
                color: #FFFFFF;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {spec['title_fg']}; padding-left: 4px; letter-spacing: 0.4px;")


class TaskCard(QFrame):
    """
    A single task card widget with status display and click interaction.
    Styled with sleek translucent glass gradients and neon accents.
    Full feature parity: hover effects, breathing pulse animation, urgent flashing.
    """
    
    clicked = Signal()
    delete_requested = Signal()
    edit_requested = Signal()
    
    STATUS_COLORS = {
        'done': '#10B981',      # Neon Emerald
        'failed': '#F43F5E',    # Neon Rose
        'active': '#0EA5E9',    # Neon Sky Cyan
        'pending': '#1E293B'    # Obsidian Slate
    }
    _PIXMAP_CACHE = {}
    
    def __init__(self, task_data, parent=None):
        super().__init__(parent)
        self.task_data = task_data
        self.id = task_data['id']
        self.status = task_data.get('status', 'pending')
        
        # Animation state
        self.is_flashing = False
        self.is_pulsing = False
        self._is_hovered = False
        self._hover_t = 0.0
        self._press_t = 0.0
        self.animations_enabled = True
        self._flash_state = False
        self._pulse_phase = 0.0
        self.current_theme = 'dark'
        self._last_rendered_icon = None
        
        # Timers (initialized lazily on demand)
        self.flash_timer = None
        self.pulse_timer = None
        
        # Color interpolation state
        self._current_bg1 = QColor(0, 0, 0, 0)
        self._current_bg2 = QColor(0, 0, 0, 0)
        self._current_border = QColor(0, 0, 0, 0)
        self._animating_color = False
        
        # Color & Press Animations (initialized lazily on demand)
        self.color_anim = None
        self._press_anim = None
        
        self.setMinimumSize(240, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

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
        layout.setContentsMargins(18, 17, 18, 18)
        
        # Status pill badge (top-left)
        self.status_label = QLabel()
        self.status_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.status_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
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
        self.name_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)
        
        # Time range
        start = self.task_data.get('start_time', '00:00')
        end = self.task_data.get('end_time', '00:00')
        self.time_label = QLabel(f"{self._format_time(start)} — {self._format_time(end)}")
        self.time_label.setFont(QFont("Segoe UI", 10))
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)
        
    def _set_task_icon(self, icon_val):
        """Internal helper to render either emoji text or high-quality pixmap"""
        try:
            if not icon_val: icon_val = '📝'
            if not isinstance(icon_val, str): icon_val = str(icon_val)
            if icon_val == self._last_rendered_icon:
                return
            self._last_rendered_icon = icon_val
            
            # Identify if this is a path (contains slashes, image extensions, or internal cache keywords)
            is_path = any(s in icon_val.lower() for s in ['\\', '/', '.png', '.jpg', '.jpeg', '.webp', 'cache', 'custom'])
            
            if is_path:
                # Resolve relative cache paths to absolute AppData
                if not os.path.isabs(icon_val) and 'cache' in icon_val:
                    appdata = os.getenv('APPDATA', os.path.expanduser('~'))
                    resolved_path = os.path.normpath(os.path.join(appdata, 'DailyTasks', icon_val))
                else:
                    resolved_path = icon_val

                scaled_pixmap = TaskCard._PIXMAP_CACHE.get(resolved_path)
                if scaled_pixmap is None:
                    pixmap = QPixmap(resolved_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        )
                        if len(TaskCard._PIXMAP_CACHE) >= 32:
                            TaskCard._PIXMAP_CACHE.pop(next(iter(TaskCard._PIXMAP_CACHE)))
                        TaskCard._PIXMAP_CACHE[resolved_path] = scaled_pixmap

                if scaled_pixmap is not None and not scaled_pixmap.isNull():
                    self.icon_label.setText("")
                    self.icon_label.setPixmap(scaled_pixmap)
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
        """Format 24h time to 12h format using O(1) integer cache"""
        cached = _TIME_FMT_CACHE.get(time_str)
        if cached is not None:
            return cached
        try:
            parts = time_str.split(":")
            h = int(parts[0])
            m = int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return time_str
            period = "AM" if h < 12 else "PM"
            h12 = h % 12
            if h12 == 0:
                h12 = 12
            res = f"{h12}:{m:02d} {period}"
            if len(_TIME_FMT_CACHE) < 1500:
                _TIME_FMT_CACHE[time_str] = res
            return res
        except Exception:
            return time_str

    def _compute_target_colors(self, hovered=False):
        """Compute gradient stops (bg1, bg2) and border QColor for current status/theme/hover"""
        theme_key = getattr(self, 'current_theme', 'dark')
        spec = get_theme_spec(theme_key)
        is_light = spec["is_light"]

        if self.status == 'done':
            base_bg1 = QColor(*spec["done_bg1"])
            bg1 = base_bg1.darker(108) if (hovered and is_light) else (base_bg1.lighter(118) if hovered else base_bg1)
            bg2 = QColor(*spec["done_bg2"])
            base_border = QColor(*spec["done_border"])
            border = base_border.lighter(115) if hovered else base_border
        elif self.status == 'active':
            base_bg1 = QColor(*spec["active_bg1"])
            bg1 = base_bg1.darker(108) if (hovered and is_light) else (base_bg1.lighter(118) if hovered else base_bg1)
            bg2 = QColor(*spec["active_bg2"])
            base_border = QColor(*spec["active_border"])
            border = base_border.lighter(115) if hovered else base_border
        elif self.status == 'failed':
            base_bg1 = QColor(*spec["failed_bg1"])
            bg1 = base_bg1.darker(108) if (hovered and is_light) else (base_bg1.lighter(118) if hovered else base_bg1)
            bg2 = QColor(*spec["failed_bg2"])
            base_border = QColor(*spec["failed_border"])
            border = base_border.lighter(115) if hovered else base_border
        else:
            bg1 = QColor(*spec["card_hover_bg1"]) if hovered else QColor(*spec["card_bg1"])
            bg2 = QColor(*spec["card_bg2"])
            border = QColor(*spec["card_hover_border"]) if hovered else QColor(*spec["card_border"])

        if self.is_flashing:
            border = QColor("#E11D48" if is_light else "#F43F5E")

        return bg1, bg2, border
            
    def _update_visuals(self, animate=False, duration=280):
        """Update card appearance based on status and hover elevation"""
        target_bg1, target_bg2, target_border = self._compute_target_colors(hovered=self._is_hovered)
        target_hover_t = 1.0 if self._is_hovered else 0.0

        if animate and self.animations_enabled:
            if self.color_anim:
                self.color_anim.stop()
            
            self.color_anim = QVariantAnimation(self)
            self.color_anim.setDuration(duration)
            self.color_anim.setStartValue(0.0)
            self.color_anim.setEndValue(1.0)
            self.color_anim.setEasingCurve(QEasingCurve.OutCubic)
            
            start_bg1 = self._current_bg1 if self._current_bg1.alpha() > 0 else target_bg1
            start_bg2 = self._current_bg2 if self._current_bg2.alpha() > 0 else target_bg2
            start_border = self._current_border if self._current_border.alpha() > 0 else target_border
            start_hover_t = float(self._hover_t)
            
            def lerp_color(c1, c2, t):
                return QColor(
                    int(c1.red() + (c2.red() - c1.red()) * t),
                    int(c1.green() + (c2.green() - c1.green()) * t),
                    int(c1.blue() + (c2.blue() - c1.blue()) * t),
                    int(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
                )

            def animate_step(v):
                t = float(v)
                self._current_bg1 = lerp_color(start_bg1, target_bg1, t)
                self._current_bg2 = lerp_color(start_bg2, target_bg2, t)
                self._current_border = lerp_color(start_border, target_border, t)
                self._hover_t = start_hover_t + (target_hover_t - start_hover_t) * t
                self._update_card_transform()
            
            self.color_anim.valueChanged.connect(animate_step)
            self._apply_styles_manually()
            self.color_anim.start()
        else:
            self._current_bg1 = target_bg1
            self._current_bg2 = target_bg2
            self._current_border = target_border
            self._hover_t = target_hover_t
            self._apply_styles_manually()

    def _update_card_transform(self):
        """Schedule 60fps card surface repaint without triggering layout recalculations"""
        self.update()

    def _apply_styles_manually(self):
        """Update child label styles only when status, theme, or schedule state changes"""
        theme_key = getattr(self, 'current_theme', 'dark')
        repeat_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6])
        today_weekday = datetime.now().weekday()
        style_key = (self.status, theme_key, tuple(repeat_days), today_weekday)
        if getattr(self, '_last_style_key', None) == style_key:
            self._update_card_transform()
            return
        self._last_style_key = style_key

        spec = get_theme_spec(theme_key)
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]
        
        status_text_map = {'done': '✓ DONE', 'failed': '✗ FAILED', 'active': '● ACTIVE', 'pending': 'PENDING', 'disabled': 'DISABLED'}
        text = status_text_map.get(self.status, 'PENDING')
        
        if is_light:
            if self.status == 'done':
                text_color, time_color = "#064E3B", "#065F46"
                badge_css = "background-color: #059669; color: #FFFFFF; border: 1px solid #047857;"
            elif self.status == 'active':
                text_color, time_color = spec["text_main"], spec["text_muted"]
                badge_css = f"background-color: {spec['accent_primary']}; color: #FFFFFF; border: 1px solid {spec['accent']};"
            elif self.status == 'failed':
                text_color, time_color = "#881337", "#9F1239"
                badge_css = "background-color: #E11D48; color: #FFFFFF; border: 1px solid #BE123C;"
            else:
                text_color, time_color = spec["text_main"], spec["text_muted"]
                badge_css = f"background-color: rgba({ar}, {ag}, {ab}, 28); color: {spec['text_main']}; border: 1px solid {spec['text_muted']};"
        else:
            if self.status == 'done':
                text_color, time_color = "#ECFDF5", "#A7F3D0"
                badge_css = "background-color: rgba(16, 185, 129, 38); color: #6EE7B7; border: 1px solid rgba(52, 211, 153, 115);"
            elif self.status == 'active':
                text_color, time_color = spec["text_main"], spec["text_muted"]
                badge_css = f"background-color: rgba({ar}, {ag}, {ab}, 42); color: {spec['accent']}; border: 1px solid rgba({ar}, {ag}, {ab}, 145);"
            elif self.status == 'failed':
                text_color, time_color = "#FFF1F2", "#FECDD3"
                badge_css = "background-color: rgba(244, 63, 94, 40); color: #FDA4AF; border: 1px solid rgba(251, 113, 133, 115);"
            else:
                text_color, time_color = spec["text_main"], spec["text_muted"]
                badge_css = f"background-color: rgba(148, 163, 184, 22); color: {spec['text_muted']}; border: 1px solid rgba(148, 163, 184, 52);"

        self.status_label.setText(text)
        
        # Ghost / Disabled Mode Check
        self._is_ghost_mode = False
        if len(repeat_days) == 0 or self.status == 'disabled':
            self._is_ghost_mode = True
            self.setCursor(Qt.ArrowCursor)
            self.status_label.setText("DISABLED")
            self.time_label.setText("Disabled (No Days)")
            
            ghost_color = "#64748B" if is_light else "rgba(148, 163, 184, 105)"
            ghost_border = "#CBD5E1" if is_light else "rgba(148, 163, 184, 26)"
            self.status_label.setStyleSheet(
                f"color: {ghost_color}; background-color: rgba(148, 163, 184, 20); "
                f"border: 1px solid {ghost_border}; border-radius: 8px; padding: 3px 9px;"
            )
            self.name_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.icon_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.time_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.setStyleSheet("#TaskCard { background: transparent; border: none; }")
        elif today_weekday not in repeat_days:
            # Ghost specific
            self._is_ghost_mode = True
            self.setCursor(Qt.ArrowCursor)
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
            
            ghost_color = "#64748B" if is_light else "rgba(148, 163, 184, 105)"
            ghost_border = "#CBD5E1" if is_light else "rgba(148, 163, 184, 26)"
            self.status_label.setStyleSheet(
                f"color: {ghost_color}; background-color: rgba(148, 163, 184, 20); "
                f"border: 1px solid {ghost_border}; border-radius: 8px; padding: 3px 9px;"
            )
            self.name_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.icon_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.time_label.setStyleSheet(f"color: {ghost_color}; background: transparent;")
            self.setStyleSheet("#TaskCard { background: transparent; border: none; }")
        else:
            # Normal Mode
            self.setCursor(Qt.PointingHandCursor if self.status != 'pending' else Qt.ArrowCursor)
            self.status_label.setStyleSheet(f"{badge_css} border-radius: 8px; padding: 3px 10px;")
            self.name_label.setStyleSheet(f"color: {text_color}; background: transparent;")
            self.icon_label.setStyleSheet(f"color: {text_color}; background: transparent;")
            self.time_label.setStyleSheet(f"color: {time_color}; margin-top: 4px; background: transparent;")
            self.setStyleSheet("#TaskCard { background: transparent; border: none; }")
        self._update_card_transform()

    def paintEvent(self, event):
        """GPU/Painter-accelerated card surface rendering with 60fps hover elevation and press compression"""
        w = self.width()
        h = self.height()
        if w <= 4 or h <= 4:
            return

        is_light = is_light_theme(getattr(self, 'current_theme', 'dark'))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if getattr(self, '_is_ghost_mode', False):
            ghost_bg = QColor(241, 245, 249, 195) if is_light else QColor(18, 22, 32, 95)
            ghost_border = QColor("#CBD5E1") if is_light else QColor(148, 163, 184, 34)
            rect = QRectF(5.5, 5.5, w - 11.0, h - 11.0)
            _draw_dashed_rounded_rect(painter, rect, 16.0, ghost_bg, ghost_border, 1.2, target_cycle_px=13.0)
            painter.end()
            return

        # Smoothly interpolate card rect from resting inset (5.5px) to hover elevation (2.5px) and press compression
        # At full hover (_hover_t=1), outer 2px border sits at 1.5px inside [0, 0, w, h] on all sides, preventing clipping.
        mx = 5.5 - (3.0 * self._hover_t) + (3.5 * self._press_t)
        my_top = 5.5 - (3.0 * self._hover_t) + (3.5 * self._press_t)
        my_bot = 5.5 - (1.5 * self._hover_t) + (2.0 * self._press_t)

        rect = QRectF(mx, my_top, w - 2.0 * mx, h - my_top - my_bot)
        if self.is_flashing:
            if self._flash_state:
                bg1 = QColor(190, 18, 60, 220)
                bg2 = QColor(69, 10, 10, 235)
                border_col = QColor("#FB7185")
            else:
                bg1 = QColor(180, 83, 9, 210)
                bg2 = QColor(69, 26, 3, 235)
                border_col = QColor("#FBBF24")
            border_w = 2.0
        else:
            bg1 = self._current_bg1
            bg2 = self._current_bg2
            border_col = self._current_border
            border_w = 2.0 if (self.status in ['active', 'done', 'failed'] or self._hover_t > 0.2) else 1.2

        grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        grad.setColorAt(0.0, bg1)
        grad.setColorAt(1.0, bg2)

        painter.setBrush(grad)
        painter.setPen(QPen(border_col, border_w))
        painter.drawRoundedRect(rect, 16.0, 16.0)

        # Soft specular glow on hover
        if self._hover_t > 0.01 and not self.is_flashing:
            glow_alpha = int(18 * self._hover_t * (1.0 - 0.5 * self._press_t))
            if glow_alpha > 0:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, glow_alpha))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 15.0, 15.0)

        # Subtle depth shade on tactile press
        if self._press_t > 0.01:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(24 * self._press_t)))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 15.0, 15.0)

        painter.end()
        
    def enterEvent(self, event):
        """Handle mouse enter - hover effect"""
        if not self.animations_enabled or self.is_flashing:
            return
            
        repeat_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6])
        if datetime.now().weekday() not in repeat_days or len(repeat_days) == 0:
            return
            
        self._set_hover(True)
        
    def leaveEvent(self, event):
        """Handle mouse leave - remove hover effect"""
        if self._press_t > 0.0:
            self._start_press_anim(0.0, duration=135, curve=QEasingCurve.OutCubic)
        if not self.animations_enabled or self.is_flashing:
            return
        
        repeat_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6])
        if datetime.now().weekday() not in repeat_days or len(repeat_days) == 0:
            return
            
        self._set_hover(False)
        
    def _set_hover(self, hovered):
        """Smoothly transition hover state using QVariantAnimation (145ms OutCubic)"""
        if self.is_flashing:
            return
        self._is_hovered = hovered
        self._update_visuals(animate=self.animations_enabled, duration=145)
        
    def _start_press_anim(self, target: float, duration: int = 70, curve=QEasingCurve.OutQuad):
        if not self.animations_enabled:
            self._press_t = 0.0
            return
        if self._press_anim is None:
            self._press_anim = QVariantAnimation(self)
            self._press_anim.valueChanged.connect(self._on_press_step)
        self._press_anim.stop()
        self._press_anim.setDuration(duration)
        self._press_anim.setEasingCurve(curve)
        self._press_anim.setStartValue(float(self._press_t))
        self._press_anim.setEndValue(float(target))
        self._press_anim.start()

    def _on_press_step(self, val):
        self._press_t = float(val)
        self._update_card_transform()

    def mousePressEvent(self, event):
        """Handle click to toggle task status"""
        if event.button() == Qt.LeftButton:
            if self.status != 'pending':
                self._animate_press()
                self.clicked.emit()
                
        elif event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPos())
            event.accept()
            return
        
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Release tactile press compression smoothly"""
        if event.button() == Qt.LeftButton and self._press_t > 0.0:
            self._start_press_anim(0.0, duration=140, curve=QEasingCurve.OutCubic)
        super().mouseReleaseEvent(event)
            
    def contextMenuEvent(self, event):
        """Right-click for edit/delete (Standard)"""
        self._show_context_menu(event.globalPos())
        
    def _show_context_menu(self, global_pos):
        """Show the context menu"""
        if self.task_data.get('is_synced', False):
            return
            
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        spec = get_theme_spec(getattr(self, 'current_theme', 'dark'))
        ar, ag, ab = spec["accent_rgb"]
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {spec['dialog_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['input_border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{
                background-color: rgba({ar}, {ag}, {ab}, 45);
                color: {spec['accent']};
            }}
        """)
        edit_action = menu.addAction("✏️ Edit")
        delete_action = menu.addAction("🗑️ Delete")
        
        action = menu.exec(global_pos)
        if action == edit_action:
            self.edit_requested.emit()
        elif action == delete_action:
            self.delete_requested.emit()
            
    def _animate_press(self):
        """Crisp tactile compression + neon highlight feedback on card press"""
        if not self.animations_enabled:
            return
        self._current_border = QColor(167, 243, 208, 255)
        self._current_bg1 = self._current_bg1.lighter(125)
        self._start_press_anim(1.0, duration=70, curve=QEasingCurve.OutQuad)
        
    def update_task(self, task_data):
        """Update the card with new task data (Legacy alias, redirecting to update_content)"""
        self.update_content(task_data)
        
        if self.status == 'active':
            self.start_active_pulse()
        else:
            self.stop_pulse()
            self.stop_flashing()
            
    def set_animations_enabled(self, enabled):
        """Enable/disable animations"""
        self.animations_enabled = enabled
        if not enabled:
            self._hover_t = 0.0
            self._press_t = 0.0
            self.stop_flashing()
            self.stop_pulse()
            
    def start_urgent_flashing(self):
        """Start urgent neon crimson/amber flashing"""
        if self.is_flashing or not self.animations_enabled:
            return
        self.is_flashing = True
        if self.flash_timer is None:
            self.flash_timer = QTimer(self)
            self.flash_timer.timeout.connect(self._flash_loop)
        if self.isVisible():
            self.flash_timer.start(480)
        self._flash_loop()
        
    def _flash_loop(self):
        """Toggle urgent flash state (throttled when hidden or minimized)"""
        if not self.isVisible():
            return
        win = self.window()
        if win is not None and (win.isMinimized() or not win.isVisible()):
            return
        self._flash_state = not self._flash_state
        self.update()
        
    def stop_flashing(self):
        """Stop flashing animation"""
        self.is_flashing = False
        if self.flash_timer is not None:
            self.flash_timer.stop()
        self._update_visuals()
        
    def start_active_pulse(self):
        """Start smooth, low-CPU breathing neon border pulse for active tasks"""
        if self.is_pulsing or not self.animations_enabled:
            return
        self.is_pulsing = True
        self._pulse_phase = 0.0
        self._pulse_ticks = 0
        if self.pulse_timer is None:
            self.pulse_timer = QTimer(self)
            self.pulse_timer.timeout.connect(self._pulse_loop)
        if self.isVisible():
            self.pulse_timer.start(100)
        
    def _pulse_loop(self):
        """Animate subtle breathing neon border glow, then settle to 0% idle CPU"""
        if self.status != 'active' or self.is_flashing or self._is_hovered:
            return
        if not self.isVisible():
            return
        win = self.window()
        if win is not None and (win.isMinimized() or not win.isVisible() or not win.isActiveWindow()):
            return
        self._pulse_ticks = getattr(self, '_pulse_ticks', 0) + 1
        if self._pulse_ticks > 28:
            # Settle at full active neon border and stop timer for 0.0% idle CPU
            if self.pulse_timer is not None:
                self.pulse_timer.stop()
            spec = get_theme_spec(getattr(self, 'current_theme', 'dark'))
            self._current_bg1 = QColor(*spec["active_bg1"])
            self._current_border = QColor(*spec["active_border"])
            self.update()
            return
        self._pulse_phase = (self._pulse_phase + 0.22) % (2 * math.pi)
        wave = 0.5 + 0.5 * math.sin(self._pulse_phase)  # 0.0 -> 1.0
        spec = get_theme_spec(getattr(self, 'current_theme', 'dark'))
        r1, g1, b1, a1 = spec["active_bg1"]
        rb, gb, bb, _ = spec["active_border"]
        border_alpha = int(145 + 110 * wave)
        bg1_alpha = max(120, min(250, int(a1 - 15 + 30 * wave)))
        self._current_bg1 = QColor(r1, g1, b1, bg1_alpha)
        self._current_border = QColor(rb, gb, bb, border_alpha)
        self.update()
        
    def stop_pulse(self):
        """Stop pulse animation"""
        self.is_pulsing = False
        if self.pulse_timer is not None:
            self.pulse_timer.stop()

    def hideEvent(self, event):
        if self.pulse_timer is not None and self.pulse_timer.isActive():
            self.pulse_timer.stop()
        if self.flash_timer is not None and self.flash_timer.isActive():
            self.flash_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self.is_flashing and self.flash_timer is not None and not self.flash_timer.isActive():
            self.flash_timer.start(480)
        
    def apply_theme(self, theme):
        """Apply theme to card"""
        self.current_theme = theme
        self._update_visuals()


class DraggablePageListWidget(QWidget):
    order_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.drop_indicator = QFrame(self)
        self.drop_indicator.setFixedHeight(40)
        self.drop_indicator.setStyleSheet(
            "background-color: rgba(56, 189, 248, 28); border: 1px dashed #38BDF8; border-radius: 8px;"
        )
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
    A single page entry in the sidebar with 60fps hover & click micro-animations.
    Click to switch pages. Right-click to open page actions menu.
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
        self._hover_t = 0.0
        self._press_t = 0.0
        self._hover_anim = None
        self._press_anim = None
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("PageButton")
        self.setAttribute(Qt.WA_Hover, True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(6)
        
        # Page name label (kept for API compatibility; rendered smoothly via QPainter in paintEvent)
        self.name_label = QLabel(page_name)
        self.name_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.hide()
        layout.addWidget(self.name_label, 1)
        
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._apply_style()

    def _animate_hover(self, target: float):
        if self._hover_anim is None:
            self._hover_anim = QVariantAnimation(self)
            self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._hover_anim.valueChanged.connect(self._on_hover_step)
        self._hover_anim.stop()
        self._hover_anim.setDuration(145)
        self._hover_anim.setStartValue(float(self._hover_t))
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    def _animate_press(self, target: float, duration: int = 70, curve=QEasingCurve.OutQuad):
        if self._press_anim is None:
            self._press_anim = QVariantAnimation(self)
            self._press_anim.valueChanged.connect(self._on_press_step)
        self._press_anim.stop()
        self._press_anim.setDuration(duration)
        self._press_anim.setEasingCurve(curve)
        self._press_anim.setStartValue(float(self._press_t))
        self._press_anim.setEndValue(float(target))
        self._press_anim.start()

    def _on_hover_step(self, val):
        self._hover_t = float(val)
        self.update()

    def _on_press_step(self, val):
        self._press_t = float(val)
        self.update()

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        if self._press_t > 0.0:
            self._animate_press(0.0, duration=135, curve=QEasingCurve.OutCubic)
        super().leaveEvent(event)

    def _apply_style(self):
        # Muted state: reuse cached opacity effect
        if self.muted:
            self._opacity_effect.setOpacity(0.45)
            self.setGraphicsEffect(self._opacity_effect)
        else:
            self.setGraphicsEffect(None)
        self.update()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        if w <= 4 or h <= 4:
            return

        spec = get_theme_spec(self.current_theme)
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]
        t = self._hover_t

        def lerp_col(c1, c2, f):
            return QColor(
                int(c1.red() + (c2.red() - c1.red()) * f),
                int(c1.green() + (c2.green() - c1.green()) * f),
                int(c1.blue() + (c2.blue() - c1.blue()) * f),
                int(c1.alpha() + (c2.alpha() - c1.alpha()) * f),
            )

        if self.selected:
            if is_light:
                p_col = QColor(spec["accent_primary"])
                h_col = QColor(spec["accent_hover"])
                c_start = lerp_col(QColor(p_col.red(), p_col.green(), p_col.blue(), 225), QColor(h_col.red(), h_col.green(), h_col.blue(), 245), t)
                c_end = lerp_col(QColor(ar, ag, ab, 215), QColor(p_col.red(), p_col.green(), p_col.blue(), 240), t)
                border_col = lerp_col(QColor(spec["accent_primary"]), QColor(spec["accent"]), t)
                text_col = QColor("#FFFFFF")
            else:
                c_start = lerp_col(QColor(ar, ag, ab, 48), QColor(ar, ag, ab, 78), t)
                c_end = lerp_col(QColor(ar, ag, ab, 22), QColor(ar, ag, ab, 46), t)
                border_col = lerp_col(QColor(ar, ag, ab, 155), QColor(ar, ag, ab, 240), t)
                text_col = QColor(spec["text_main"])
        else:
            if is_light:
                c_start = lerp_col(QColor(255, 255, 255, 165), QColor(ar, ag, ab, 45), t)
                c_end = c_start
                border_col = lerp_col(QColor(spec["input_border"]), QColor(spec["accent"]), t)
                text_col = QColor(spec["text_main"])
            else:
                r1, g1, b1, _ = spec["card_bg1"]
                rh, gh, bh, _ = spec["card_hover_bg1"]
                c_start = lerp_col(QColor(r1, g1, b1, 95), QColor(rh, gh, bh, 165), t)
                c_end = c_start
                border_col = lerp_col(QColor(148, 163, 184, 30), QColor(ar, ag, ab, 130), t)
                text_col = lerp_col(QColor(spec["text_muted"]), QColor(spec["text_main"]), t)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Smoothly interpolate rect from resting inset (3.5, 2.5) to hover expansion (1.5, 1.5) and press compression
        mx = 3.5 - (2.0 * self._hover_t) + (2.5 * self._press_t)
        my_top = 2.5 - (1.0 * self._hover_t) + (1.5 * self._press_t)
        my_bot = 2.5 - (1.0 * self._hover_t) + (1.0 * self._press_t)

        rect = QRectF(mx, my_top, w - 2.0 * mx, h - my_top - my_bot)
        grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        grad.setColorAt(0.0, c_start)
        grad.setColorAt(1.0, c_end)

        painter.setBrush(grad)
        painter.setPen(QPen(border_col, 1.2))
        painter.drawRoundedRect(rect, 10.0, 10.0)

        if self._press_t > 0.01:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(26 * self._press_t)))
            painter.drawRoundedRect(rect, 10.0, 10.0)

        painter.setPen(text_col)
        painter.setFont(self.name_label.font())
        painter.drawText(rect, Qt.AlignCenter, self.name_label.text())
        painter.end()
    
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
            self._animate_press(1.0, duration=70, curve=QEasingCurve.OutQuad)
            self.page_clicked.emit(self.page_id)
        elif event.button() == Qt.RightButton:
            self._show_menu_at(event.globalPos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press_t > 0.0:
            self._animate_press(0.0, duration=135, curve=QEasingCurve.OutCubic)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if not hasattr(self, '_drag_start_pos'):
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < 5:
            return

        self._hover_t = 0.0
        self._press_t = 0.0
        self.update()

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
        spec = get_theme_spec(self.current_theme)
        ar, ag, ab = spec["accent_rgb"]
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {spec['dialog_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['input_border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 5px;
            }}
            QMenu::item:selected {{
                background-color: rgba({ar}, {ag}, {ab}, 45);
                color: {spec['accent']};
            }}
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


class AddPageButton(AnimatedPushButton):
    """
    Sidebar '+ New Page' button rendered via QPainter with a continuous,
    corner-seamless antialiased dashed border and crisp vector '+' symbol.
    """

    def __init__(self, parent=None):
        super().__init__("+", parent)
        self.current_theme = "dark"
        self.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)

    def apply_theme(self, theme: str):
        self.current_theme = theme
        self.update()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        if w <= 4 or h <= 4:
            return

        spec = get_theme_spec(self.current_theme)
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]
        t = self._hover_t

        def lerp_col(c1, c2, f):
            return QColor(
                int(c1.red() + (c2.red() - c1.red()) * f),
                int(c1.green() + (c2.green() - c1.green()) * f),
                int(c1.blue() + (c2.blue() - c1.blue()) * f),
                int(c1.alpha() + (c2.alpha() - c1.alpha()) * f),
            )

        c_muted = QColor(spec["text_muted"])
        c_acc = QColor(spec["accent"])
        if is_light:
            c_in_bdr = QColor(spec["input_border"])
            bg_col = lerp_col(QColor(255, 255, 255, 155), QColor(ar, ag, ab, 38), t)
            border_col = lerp_col(
                QColor(c_in_bdr.red(), c_in_bdr.green(), c_in_bdr.blue(), 225),
                QColor(c_acc.red(), c_acc.green(), c_acc.blue(), 255),
                t,
            )
            plus_col = lerp_col(c_muted, c_acc, t)
        else:
            r1, g1, b1, _ = spec["card_bg1"]
            bg_col = lerp_col(QColor(r1, g1, b1, 75), QColor(ar, ag, ab, 30), t)
            border_col = lerp_col(
                QColor(148, 163, 184, 85),
                QColor(ar, ag, ab, 195),
                t,
            )
            plus_col = lerp_col(c_muted, c_acc, t)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        mx = 3.5 - (1.5 * self._hover_t) + (2.0 * self._press_t)
        my_top = 3.0 - (1.0 * self._hover_t) + (1.5 * self._press_t)
        my_bot = 3.0 - (1.0 * self._hover_t) + (1.0 * self._press_t)
        rect = QRectF(mx, my_top, w - 2.0 * mx, h - my_top - my_bot)

        _draw_dashed_rounded_rect(
            painter,
            rect,
            10.0,
            bg_col,
            border_col,
            pen_w=1.4,
            target_cycle_px=11.0,
            solid=(self._hover_t > 0.65),
        )

        if self._press_t > 0.01:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(24 * self._press_t)))
            painter.drawRoundedRect(rect, 10.0, 10.0)

        # Crisp geometrically centered vector '+' symbol
        cx = rect.center().x()
        cy = rect.center().y()
        arm = 6.5
        plus_pen = QPen(plus_col, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(plus_pen)
        painter.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        painter.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
        painter.end()


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
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(250)
        self.current_theme = 'dark'
        self._page_buttons = {}  # page_id -> PageButton
        self._update_available = False
        self._update_version = ""
        
        self._setup_ui()
        self.apply_theme('dark')
        
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
                background: rgba(148, 163, 184, 70);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #38BDF8;
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
        self.settings_btn.setFont(QFont("Segoe UI", 11, QFont.Medium))
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.settings_btn)

        # ── COPY FEEDBACK (absolute positioned) ──
        self.copy_feedback = QLabel("Share ID Copied!", self)
        self.copy_feedback.setAlignment(Qt.AlignCenter)
        self.copy_feedback.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.copy_feedback.setStyleSheet("color: #34D399;")
        
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
        self._add_page_btn = AddPageButton()
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
        if hasattr(self._add_page_btn, "apply_theme"):
            self._add_page_btn.apply_theme(self.current_theme)
        else:
            self._add_page_btn.update()

    def set_update_available(self, available: bool, version: str = ""):
        """Show or hide subtle update indicator on the Settings button."""
        self._update_available = bool(available)
        self._update_version = version or ""
        if self._update_available:
            self.settings_btn.setText("⚙️ Settings  •  Update")
        else:
            self.settings_btn.setText("⚙️ Settings")
        self.apply_theme(self.current_theme)

    def apply_theme(self, theme):
        self.current_theme = theme
        spec = get_theme_spec(theme)
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]

        self.setStyleSheet(f"""
            #Sidebar {{
                background: {spec['sidebar_bg']};
                border-right: 1px solid {spec['sidebar_border']};
            }}
        """)

        if self._update_available:
            btn_bg = f"rgba({ar}, {ag}, {ab}, {26 if is_light else 34})"
            btn_fg = spec['accent'] if not is_light else spec['text_main']
            btn_border = f"1px solid rgba({ar}, {ag}, {ab}, {130 if is_light else 110})"
            self.settings_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {btn_fg};
                    border: {btn_border};
                    border-radius: 8px;
                    text-align: left;
                    padding: 8px 12px;
                }}
                QPushButton:hover {{
                    background-color: rgba({ar}, {ag}, {ab}, {45 if is_light else 52});
                    color: {spec['text_main']};
                    border: 1px solid {spec['accent']};
                }}
            """)
        elif is_light:
            self.settings_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(255, 255, 255, 165);
                    color: {spec['text_main']};
                    border: 1px solid {spec['input_border']};
                    border-radius: 8px;
                    text-align: left;
                    padding: 8px 12px;
                }}
                QPushButton:hover {{
                    background-color: rgba({ar}, {ag}, {ab}, 35);
                    color: {spec['text_main']};
                    border: 1px solid {spec['accent']};
                }}
            """)
        else:
            self.settings_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {spec['text_muted']};
                    border: none;
                    border-radius: 8px;
                    text-align: left;
                    padding: 8px 10px;
                }}
                QPushButton:hover {{
                    background-color: rgba({ar}, {ag}, {ab}, 28);
                    color: {spec['text_main']};
                }}
            """)

        if is_light:
            self.copy_feedback.setStyleSheet("background-color: rgba(255, 255, 255, 245); color: #059669; border: 1px solid #A7F3D0; padding: 5px 10px; border-radius: 6px;")
        else:
            self.copy_feedback.setStyleSheet(f"background-color: {spec['dialog_bg']}; color: #34D399; border: 1px solid rgba(52, 211, 153, 90); padding: 5px 10px; border-radius: 6px;")
        
        # Update all page buttons and add page btn
        for btn in self._page_buttons.values():
            btn.apply_theme(theme)
        self._apply_add_page_theme()

    def show_copy_feedback(self, page_id=None):
        """Show temporary 'Copied!' message positioned under the specific page button"""
        if hasattr(self, '_fade_timer') and self._fade_timer is not None:
            self._fade_timer.stop()
            
        if page_id and page_id in self._page_buttons:
            btn = self._page_buttons[page_id]
            btn_bottom = btn.mapTo(self, QPoint(0, btn.height()))
            self._feedback_y = btn_bottom.y() - 8
        else:
            self._feedback_y = 60
            
        self.copy_feedback.setGeometry(
            self._feedback_x, self._feedback_y,
            self._feedback_w, self._feedback_h
        )
        self.copy_feedback.setStyleSheet("color: rgba(52, 211, 153, 255);")
        self.copy_feedback.setVisible(True)
        self.copy_feedback.raise_()

        if hasattr(self, '_fade_timer') and self._fade_timer is not None:
            self._fade_timer.stop()
        if hasattr(self, '_fade_interval') and self._fade_interval is not None:
            self._fade_interval.stop()

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._start_stylesheet_fade)
        self._fade_timer.start(1500)
    
    def _start_stylesheet_fade(self):
        self._fade_step = 255
        if hasattr(self, '_fade_interval') and self._fade_interval is not None:
            self._fade_interval.stop()
        self._fade_interval = QTimer(self)
        self._fade_interval.timeout.connect(self._fade_step_update)
        self._fade_interval.start(30)
    
    def _fade_step_update(self):
        self._fade_step -= 10
        if self._fade_step <= 0:
            self._fade_interval.stop()
            self.copy_feedback.hide()
            return
        self.copy_feedback.setStyleSheet(f"color: rgba(52, 211, 153, {self._fade_step});")



class InfoBadge(QLabel):
    """
    Custom 'i' icon with instant, snappy tooltip and better hitbox.
    """
    def __init__(self, tooltip, parent=None):
        super().__init__("ⓘ", parent)
        self.setToolTip(tooltip)
        self.setFont(QFont("Segoe UI", 12))
        self.setCursor(Qt.WhatsThisCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(24, 24)
        
        self.apply_theme('dark')

    def apply_theme(self, theme):
        """Update style for theme, specifically QToolTip"""
        spec = get_theme_spec(theme)
        ar, ag, ab = spec["accent_rgb"]
        text_color = spec["text_muted"]
        hover_color = spec["accent"]
        hover_bg = f"rgba({ar}, {ag}, {ab}, 32)"
        tt_bg = spec["dialog_bg"]
        tt_text = spec["text_main"]
        tt_border = spec["input_border"]
            
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
                padding: 6px 8px;
                border-radius: 6px;
            }}
        """)

    def enterEvent(self, event):
        QToolTip.showText(QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)


class _ThemeComboItemDelegate(QStyledItemDelegate):
    """Custom item delegate for theme dropdown ensuring high-contrast hover states and color swatches."""

    def __init__(self, panel):
        super().__init__(panel)
        self._panel = panel

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), 34)

    def paint(self, painter, option, index):
        spec = get_theme_spec(getattr(self._panel, "current_theme", "dark"))
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]

        is_hovered = bool(option.state & (QStyle.State_MouseOver | QStyle.State_Selected))
        item_key = index.data(Qt.UserRole)
        item_spec = get_theme_spec(item_key) if item_key else spec
        is_active = (item_key == getattr(self._panel, "current_theme", "dark"))

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 1. Solid popup row background
        painter.fillRect(option.rect, QColor(spec["dialog_bg"]))

        # 2. Hover / Selection / Active pill
        pill_rect = QRectF(option.rect).adjusted(4.0, 2.0, -4.0, -2.0)
        if is_hovered:
            if is_light:
                # High-contrast tinted pill with dark text so text is never washed out on light backgrounds
                painter.setBrush(QColor(ar, ag, ab, 52))
                painter.setPen(QPen(QColor(ar, ag, ab, 195), 1.2))
                text_col = QColor(spec["text_main"])
            else:
                painter.setBrush(QColor(ar, ag, ab, 75))
                painter.setPen(QPen(QColor(ar, ag, ab, 215), 1.2))
                text_col = QColor("#FFFFFF")
            painter.drawRoundedRect(pill_rect, 6.0, 6.0)
        else:
            if is_active:
                painter.setBrush(QColor(ar, ag, ab, 24 if is_light else 34))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(pill_rect, 6.0, 6.0)
            text_col = QColor(spec["text_main"])

        # 3. Theme signature color swatch dot
        swatch_rect = QRectF(
            option.rect.left() + 13.0,
            option.rect.center().y() - 5.0,
            10.0,
            10.0,
        )
        painter.setBrush(QColor(item_spec["accent"]))
        painter.setPen(QPen(QColor(item_spec["dialog_bg"]), 1.2))
        painter.drawEllipse(swatch_rect)

        # 4. Theme label text
        font = QFont("Segoe UI", 10, QFont.Bold if (is_hovered or is_active) else QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(text_col)
        text_rect = option.rect.adjusted(31, 0, -26, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, str(index.data(Qt.DisplayRole) or ""))

        # 5. Active checkmark indicator
        if is_active:
            painter.setPen(QColor(spec["accent"]))
            check_rect = option.rect.adjusted(0, 0, -11, 0)
            painter.drawText(check_rect, Qt.AlignVCenter | Qt.AlignRight, "✓")

        painter.restore()


class _ThemeComboBox(QComboBox):
    """Custom QComboBox that renders a crisp antialiased chevron arrow via QPainter."""

    def __init__(self, panel):
        super().__init__(panel)
        self._panel = panel
        self.setItemDelegate(_ThemeComboItemDelegate(panel))
        self.view().setMouseTracking(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        spec = get_theme_spec(getattr(self._panel, "current_theme", "dark"))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(spec["accent"]), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        cx = self.width() - 14.0
        cy = self.height() * 0.5 + 1.0
        painter.drawLine(QPointF(cx - 4.5, cy - 2.5), QPointF(cx, cy + 2.0))
        painter.drawLine(QPointF(cx, cy + 2.0), QPointF(cx + 4.5, cy - 2.5))
        painter.end()


class SettingsPanel(QFrame):
    """
    Settings overlay panel with multi-theme dropdown, app mode checkboxes, UI SFX controls, and update section.
    """
    
    close_clicked = Signal()
    dnd_toggled = Signal(bool)
    prayer_mode_toggled = Signal(bool)
    simple_mode_toggled = Signal(bool)
    hardcore_mode_toggled = Signal(bool)
    ui_sounds_toggled = Signal(bool)
    ui_volume_changed = Signal(int)
    theme_changed = Signal(str)
    check_updates_clicked = Signal()
    install_update_clicked = Signal(str, str)  # (version, download_url)

    _EXPANDED_HEIGHT = 488
    _COLLAPSED_HEIGHT = 448
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = 'dark'
        self._height_anim = None
        self._update_state = "up_to_date"
        self._update_version = APP_VERSION
        self._update_download_url = ""
        self._update_progress = 0
        self._update_message = ""
        self.setObjectName("SettingsPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(315, self._EXPANDED_HEIGHT)
        
        self._setup_ui()
        self.apply_theme('dark')
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(24, 18, 24, 16)
        
        # Header with close button
        header = QHBoxLayout()
        
        self.title_label = QLabel("Settings")
        self.title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.addWidget(self.title_label)
        
        header.addStretch()
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        header.addWidget(self.close_btn)
        
        layout.addLayout(header)
        
        # ─────────────────────────────────────────
        # 1. Visual & Display Section
        # ─────────────────────────────────────────
        self.theme_label_ui = QLabel("Theme")
        self.theme_label_ui.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(self.theme_label_ui)

        self.theme_combo = _ThemeComboBox(self)
        self.theme_combo.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.theme_combo.setCursor(Qt.PointingHandCursor)
        self.theme_combo.setFixedHeight(38)
        for theme_key, theme_label in THEME_OPTIONS:
            self.theme_combo.addItem(theme_label, theme_key)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        layout.addWidget(self.theme_combo)

        # Keep hidden dark_btn / light_btn references for backward compatibility
        self.dark_btn = QPushButton("Dark", self)
        self.dark_btn.setCheckable(True)
        self.dark_btn.setChecked(True)
        self.dark_btn.hide()
        self.dark_btn.clicked.connect(lambda: self._set_theme("dark"))

        self.light_btn = QPushButton("Light", self)
        self.light_btn.setCheckable(True)
        self.light_btn.hide()
        self.light_btn.clicked.connect(lambda: self._set_theme("light"))

        self.simple_checkbox = self._create_checkbox(
            "Simple View", 
            "Cleans up the UI by hiding particles and animations for a minimalist focus."
        )
        self.simple_checkbox.toggled.connect(self.simple_mode_toggled.emit)
        layout.addWidget(self.simple_checkbox)
        
        # Separator between Visual & Display and Workflow & Behavior
        self.sep = QFrame()
        self.sep.setFixedHeight(1)
        self.sep.setStyleSheet("background-color: rgba(148, 163, 184, 35);")
        layout.addWidget(self.sep)
        
        # ─────────────────────────────────────────
        # 2. Workflow & Behavior Section
        # ─────────────────────────────────────────
        self.hardcore_checkbox = self._create_checkbox(
            "Hardcore Mode", 
            "Locks tasks if marked as failed, making them impossible to check as done."
        )
        self.hardcore_checkbox.toggled.connect(self.hardcore_mode_toggled.emit)
        layout.addWidget(self.hardcore_checkbox)

        self.prayer_checkbox = self._create_checkbox(
            "Prayer Times", 
            "Enables automatic alerts for daily prayer intervals based on local time."
        )
        self.prayer_checkbox.toggled.connect(self.prayer_mode_toggled.emit)
        layout.addWidget(self.prayer_checkbox)

        # Separator between Workflow & Behavior and Audio & Notifications
        self.sep_audio = QFrame()
        self.sep_audio.setFixedHeight(1)
        self.sep_audio.setStyleSheet("background-color: rgba(148, 163, 184, 35);")
        layout.addWidget(self.sep_audio)

        # ─────────────────────────────────────────
        # 3. Audio & Notifications Section
        # ─────────────────────────────────────────
        self.dnd_checkbox = self._create_checkbox(
            "Do Not Disturb", 
            "Mutes all audio, suppresses notifications, and disables taskbar flashing."
        )
        self.dnd_checkbox.toggled.connect(self._on_dnd_toggled)
        layout.addWidget(self.dnd_checkbox)
        
        self.ui_sounds_checkbox = self._create_checkbox(
            "UI Sound Effects",
            "Plays subtle tactile hover, click, and typing sounds without muting task alarms."
        )
        self.ui_sounds_checkbox.toggled.connect(self._on_ui_sounds_toggled)
        layout.addWidget(self.ui_sounds_checkbox)

        self.ui_vol_container = QFrame()
        self.ui_vol_container.setFixedHeight(28)
        self.ui_vol_container.setStyleSheet("background: transparent;")
        vol_layout = QHBoxLayout(self.ui_vol_container)
        vol_layout.setContentsMargins(36, 0, 4, 2)
        vol_layout.setSpacing(10)

        self.ui_vol_label = QLabel("SFX Volume")
        self.ui_vol_label.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        vol_layout.addWidget(self.ui_vol_label)

        self.ui_vol_slider = QSlider(Qt.Horizontal)
        self.ui_vol_slider.setRange(0, 100)
        self.ui_vol_slider.setValue(80)
        self.ui_vol_slider.setCursor(Qt.PointingHandCursor)
        self.ui_vol_slider.valueChanged.connect(self._on_ui_volume_slider_changed)
        vol_layout.addWidget(self.ui_vol_slider, 1)

        self.ui_vol_value_label = QLabel("80%")
        self.ui_vol_value_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.ui_vol_value_label.setFixedWidth(34)
        self.ui_vol_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        vol_layout.addWidget(self.ui_vol_value_label)

        layout.addWidget(self.ui_vol_container)
        
        layout.addStretch()

        # ─────────────────────────────────────────
        # 4. Version & Updates Footer
        # ─────────────────────────────────────────
        self.sep_update = QFrame()
        self.sep_update.setFixedHeight(1)
        self.sep_update.setStyleSheet("background-color: rgba(148, 163, 184, 35);")
        layout.addWidget(self.sep_update)

        self.update_container = QFrame()
        self.update_container.setStyleSheet("background: transparent;")
        update_v_layout = QVBoxLayout(self.update_container)
        update_v_layout.setContentsMargins(0, 2, 0, 0)
        update_v_layout.setSpacing(6)

        update_row = QHBoxLayout()
        update_row.setContentsMargins(0, 0, 0, 0)
        update_row.setSpacing(8)

        version_col = QVBoxLayout()
        version_col.setContentsMargins(0, 0, 0, 0)
        version_col.setSpacing(1)

        self.update_version_label = QLabel(f"Version {APP_VERSION}")
        self.update_version_label.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        version_col.addWidget(self.update_version_label)

        self.update_status_label = QLabel("Up to date")
        self.update_status_label.setFont(QFont("Segoe UI", 8))
        version_col.addWidget(self.update_status_label)

        update_row.addLayout(version_col, 1)

        self.update_action_btn = QPushButton("Check for Updates")
        self.update_action_btn.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.update_action_btn.setFixedHeight(28)
        self.update_action_btn.setCursor(Qt.PointingHandCursor)
        self.update_action_btn.clicked.connect(self._on_update_action_clicked)
        update_row.addWidget(self.update_action_btn)

        update_v_layout.addLayout(update_row)

        self.update_progress_bar = QProgressBar()
        self.update_progress_bar.setFixedHeight(4)
        self.update_progress_bar.setRange(0, 100)
        self.update_progress_bar.setValue(0)
        self.update_progress_bar.setTextVisible(False)
        self.update_progress_bar.hide()
        update_v_layout.addWidget(self.update_progress_bar)

        layout.addWidget(self.update_container)

        # Set default checked state for UI sounds and sync volume slider visibility
        self.ui_sounds_checkbox.checkbox.blockSignals(True)
        self.ui_sounds_checkbox.checkbox.setChecked(True)
        self.ui_sounds_checkbox.checkbox.blockSignals(False)
        self._update_volume_visibility(animate=False)

    def _update_volume_visibility(self, animate: bool = True):
        """Show SFX Volume row only when UI Sound Effects is enabled AND Do Not Disturb is disabled."""
        show_vol = bool(
            self.ui_sounds_checkbox.checkbox.isChecked()
            and not self.dnd_checkbox.checkbox.isChecked()
        )
        self.ui_vol_container.setVisible(show_vol)
        self.ui_vol_slider.setEnabled(show_vol)

        target_h = self._EXPANDED_HEIGHT if show_vol else self._COLLAPSED_HEIGHT
        if self._height_anim is not None:
            self._height_anim.stop()

        if animate and self.isVisible() and self.height() != target_h:
            self._height_anim = QVariantAnimation(self)
            self._height_anim.setDuration(135)
            self._height_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._height_anim.setStartValue(int(self.height()))
            self._height_anim.setEndValue(int(target_h))
            self._height_anim.valueChanged.connect(lambda v: self.setFixedSize(315, int(v)))
            self._height_anim.start()
        else:
            self.setFixedSize(315, target_h)

    def _update_ui_sounds_dnd_visual(self):
        """Gray/fade the UI Sound Effects row when Do Not Disturb is active."""
        dnd_on = self.dnd_checkbox.checkbox.isChecked()
        container = self.ui_sounds_checkbox

        if dnd_on:
            # Apply dim opacity to the whole container
            effect = QGraphicsOpacityEffect(container)
            effect.setOpacity(0.38)
            container.setGraphicsEffect(effect)
            # Mute label and info badge colors
            container.label_widget.setStyleSheet("color: #808080;")
            if hasattr(container, "info_btn"):
                container.info_btn.setStyleSheet("color: #808080;")
        else:
            # Restore full opacity
            container.setGraphicsEffect(None)
            # Restore colors from current theme
            spec = get_theme_spec(self.current_theme)
            container.label_widget.setStyleSheet(f"color: {spec['text_main']};")
            if hasattr(container, "info_btn"):
                container.info_btn.apply_theme(self.current_theme)

    def _on_dnd_toggled(self, checked: bool):
        self._update_volume_visibility(animate=True)
        self._update_ui_sounds_dnd_visual()
        self.dnd_toggled.emit(checked)

    def _on_ui_sounds_toggled(self, checked: bool):
        self._update_volume_visibility(animate=True)
        self.ui_sounds_toggled.emit(checked)

    def _on_ui_volume_slider_changed(self, value: int):
        self.ui_vol_value_label.setText(f"{value}%")
        self.ui_volume_changed.emit(value)

    def _apply_slider_theme(self):
        spec = get_theme_spec(self.current_theme)
        is_light = spec["is_light"]
        groove_bg = "#CBD5E1" if is_light else spec["input_bg"]
        subpage_bg = spec["accent"]
        handle_bg = "#FFFFFF" if is_light else spec["text_main"]
        handle_border = spec["accent"]
        self.ui_vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: none;
                height: 6px;
                background: {groove_bg};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {subpage_bg};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {handle_bg};
                border: 2px solid {handle_border};
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {subpage_bg};
            }}
            QSlider::sub-page:horizontal:disabled {{
                background: #64748B;
            }}
        """)

    def _on_theme_combo_changed(self, index: int):
        theme_key = self.theme_combo.itemData(index)
        if theme_key:
            self._set_theme(theme_key)

    def _sync_theme_controls(self, theme: str):
        """Sync dropdown index and legacy buttons without firing signals"""
        idx = self.theme_combo.findData(theme)
        if idx < 0:
            idx = 0
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.blockSignals(False)

        is_light = is_light_theme(theme)
        self.dark_btn.blockSignals(True)
        self.light_btn.blockSignals(True)
        self.dark_btn.setChecked(not is_light)
        self.light_btn.setChecked(is_light)
        self.dark_btn.blockSignals(False)
        self.light_btn.blockSignals(False)

    def _set_theme(self, theme):
        """Handle theme selection change"""
        self._sync_theme_controls(theme)
        self.theme_changed.emit(theme)
        
    def _create_checkbox(self, label, description):
        container = QFrame()
        container.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)
        
        # Checkbox button (styled as square)
        checkbox = QPushButton()
        checkbox.setCheckable(True)
        checkbox.setFixedSize(24, 24)
        checkbox.setCursor(Qt.PointingHandCursor)
        
        checkbox.toggled.connect(lambda checked: self._update_checkbox_visual(checkbox, checked))
        layout.addWidget(checkbox)
        
        # Label
        label_widget = QLabel(label)
        label_widget.setFont(QFont("Segoe UI", 11))
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
        
    def set_values(self, dnd, prayer, simple, hardcore, ui_sounds=True, ui_volume=80):
        """Set checkbox and slider states without triggering signals"""
        for cb in (
            self.dnd_checkbox.checkbox,
            self.prayer_checkbox.checkbox,
            self.simple_checkbox.checkbox,
            self.hardcore_checkbox.checkbox,
            self.ui_sounds_checkbox.checkbox,
        ):
            cb.blockSignals(True)
        self.ui_vol_slider.blockSignals(True)
        
        self.dnd_checkbox.checkbox.setChecked(dnd)
        self.prayer_checkbox.checkbox.setChecked(prayer)
        self.simple_checkbox.checkbox.setChecked(simple)
        self.hardcore_checkbox.checkbox.setChecked(hardcore)
        self.ui_sounds_checkbox.checkbox.setChecked(ui_sounds)
        vol_int = max(0, min(100, int(round(ui_volume * 100)) if isinstance(ui_volume, float) and ui_volume <= 1.0 else int(ui_volume)))
        self.ui_vol_slider.setValue(vol_int)
        self.ui_vol_value_label.setText(f"{vol_int}%")
        
        for cb in (
            self.dnd_checkbox.checkbox,
            self.prayer_checkbox.checkbox,
            self.simple_checkbox.checkbox,
            self.hardcore_checkbox.checkbox,
            self.ui_sounds_checkbox.checkbox,
        ):
            cb.blockSignals(False)
        self.ui_vol_slider.blockSignals(False)
        
        self._update_checkbox_visual(self.dnd_checkbox.checkbox, dnd)
        self._update_checkbox_visual(self.prayer_checkbox.checkbox, prayer)
        self._update_checkbox_visual(self.simple_checkbox.checkbox, simple)
        self._update_checkbox_visual(self.hardcore_checkbox.checkbox, hardcore)
        self._update_checkbox_visual(self.ui_sounds_checkbox.checkbox, ui_sounds)
        self._update_volume_visibility(animate=False)
        self._update_ui_sounds_dnd_visual()

        
        
    def set_prayer_loading(self, loading):
        """Show loading state on prayer checkbox"""
        pass

    def _on_update_action_clicked(self):
        if self._update_state == "update_available":
            self.install_update_clicked.emit(self._update_version, self._update_download_url)
        elif self._update_state not in ("checking", "downloading"):
            self.check_updates_clicked.emit()

    def set_update_state(
        self,
        state: str,
        version: str = "",
        download_url: str = "",
        progress: int = 0,
        message: str = "",
    ):
        """Update the footer UI for update checking/downloading states."""
        self._update_state = state or "up_to_date"
        if version:
            self._update_version = version.lstrip("vV")
        if download_url:
            self._update_download_url = download_url
        self._update_progress = max(0, min(100, int(progress)))
        self._update_message = message or ""

        self.update_version_label.setText(f"Version {APP_VERSION}")

        if self._update_state == "checking":
            self.update_status_label.setText("Checking for updates...")
            self.update_action_btn.setText("Checking...")
            self.update_action_btn.setEnabled(False)
            self.update_progress_bar.hide()
        elif self._update_state == "update_available":
            ver_text = f"v{self._update_version}" if self._update_version else "New version"
            self.update_status_label.setText(f"{ver_text} available")
            self.update_action_btn.setText(f"Install {ver_text}")
            self.update_action_btn.setEnabled(True)
            self.update_progress_bar.hide()
        elif self._update_state == "downloading":
            pct = self._update_progress
            self.update_status_label.setText(f"Downloading update... {pct}%")
            self.update_action_btn.setText(f"{pct}%")
            self.update_action_btn.setEnabled(False)
            self.update_progress_bar.setValue(pct)
            self.update_progress_bar.show()
        elif self._update_state == "error":
            err_msg = self._update_message or "Update check failed"
            if len(err_msg) > 30:
                err_msg = err_msg[:28] + "..."
            self.update_status_label.setText(err_msg)
            self.update_action_btn.setText("Retry")
            self.update_action_btn.setEnabled(True)
            self.update_progress_bar.hide()
        else:
            # "idle" or "up_to_date"
            self.update_status_label.setText(self._update_message or "Up to date")
            self.update_action_btn.setText("Check for Updates")
            self.update_action_btn.setEnabled(True)
            self.update_progress_bar.hide()

        self._apply_update_section_theme()

    def _apply_update_section_theme(self):
        if not hasattr(self, "update_version_label"):
            return
        spec = get_theme_spec(self.current_theme)
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]

        self.update_version_label.setStyleSheet(f"color: {spec['text_main']};")

        if self._update_state == "update_available":
            status_color = "#059669" if is_light else "#34D399"
        elif self._update_state == "error":
            status_color = "#DC2626" if is_light else "#F87171"
        elif self._update_state in ("checking", "downloading"):
            status_color = spec["accent"]
        else:
            status_color = spec["text_muted"]
        self.update_status_label.setStyleSheet(f"color: {status_color};")

        if self._update_state == "update_available":
            self.update_action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {spec['accent_primary']};
                    color: #FFFFFF;
                    border: 1px solid {spec['accent']};
                    border-radius: 7px;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    background-color: {spec['accent_hover']};
                }}
            """)
        else:
            btn_bg = "rgba(255, 255, 255, 175)" if is_light else spec["input_bg"]
            self.update_action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {btn_bg};
                    color: {spec['text_main']};
                    border: 1px solid {spec['input_border']};
                    border-radius: 7px;
                    padding: 4px 10px;
                }}
                QPushButton:hover:enabled {{
                    background-color: rgba({ar}, {ag}, {ab}, {25 if is_light else 35});
                    border: 1px solid {spec['accent']};
                }}
                QPushButton:disabled {{
                    color: {spec['text_muted']};
                    background-color: transparent;
                }}
            """)

        groove_bg = "#CBD5E1" if is_light else spec["input_bg"]
        self.update_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {groove_bg};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {spec['accent']};
                border-radius: 2px;
            }}
        """)

    def apply_theme(self, theme):
        """Apply theme to settings panel"""
        self.current_theme = theme
        spec = get_theme_spec(theme)
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]

        self._sync_theme_controls(theme)
        self._apply_slider_theme()
        self._apply_update_section_theme()

        all_cbs = [
            self.dnd_checkbox,
            self.prayer_checkbox,
            self.simple_checkbox,
            self.hardcore_checkbox,
            self.ui_sounds_checkbox,
        ]

        self.setStyleSheet(f"""
            #SettingsPanel {{
                background-color: {spec['panel_bg']};
                border-radius: 14px;
                border: 1px solid {spec['panel_border']};
            }}
            QToolTip {{
                background-color: {spec['dialog_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['input_border']};
                padding: 6px;
                border-radius: 6px;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {spec['text_main']};")
        self.theme_label_ui.setStyleSheet(f"color: {spec['text_muted']}; margin-top: 4px;")
        self.ui_vol_label.setStyleSheet(f"color: {spec['text_muted']};")
        self.ui_vol_value_label.setStyleSheet(f"color: {spec['accent']};")

        sep_color = "rgba(15, 23, 42, 22)" if is_light else "rgba(255, 255, 255, 25)"
        for sep_frame in (getattr(self, "sep", None), getattr(self, "sep_audio", None), getattr(self, "sep_update", None)):
            if sep_frame is not None:
                sep_frame.setStyleSheet(f"background-color: {sep_color}; margin: 4px 0px;")

        close_hover_bg = "rgba(0, 0, 0, 18)" if is_light else "rgba(255, 255, 255, 26)"
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {spec['text_muted']};
                border: none;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background-color: {close_hover_bg};
                color: {spec['text_main']};
            }}
        """)

        sel_bg = f"rgba({ar}, {ag}, {ab}, 52)" if is_light else spec["accent_primary"]
        sel_fg = spec["text_main"] if is_light else "#FFFFFF"
        self.theme_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {spec['input_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['input_border']};
                border-radius: 9px;
                padding: 6px 32px 6px 12px;
            }}
            QComboBox:hover {{
                border: 1px solid {spec['accent']};
                background-color: rgba({ar}, {ag}, {ab}, {22 if is_light else 32});
            }}
            QComboBox:on {{
                border: 1px solid {spec['accent']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid {spec['input_border']};
                border-top-right-radius: 9px;
                border-bottom-right-radius: 9px;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {spec['dialog_bg']};
                color: {spec['text_main']};
                border: 1px solid {spec['accent']};
                border-radius: 8px;
                padding: 4px;
                selection-background-color: {sel_bg};
                selection-color: {sel_fg};
                outline: 0;
            }}
        """)
        self.theme_combo.update()
        if self.theme_combo.view() is not None:
            self.theme_combo.view().viewport().update()

        for cb_container in all_cbs:
            cb_container.label_widget.setStyleSheet(f"color: {spec['text_main']};")
            if hasattr(cb_container, 'info_btn'):
                cb_container.info_btn.apply_theme(theme)
            is_checked = cb_container.checkbox.isChecked()
            self._update_checkbox_visual(cb_container.checkbox, is_checked)

        # Re-evaluate DND visual state after all theme colors are applied
        self._update_ui_sounds_dnd_visual()

    def _update_checkbox_visual(self, checkbox, checked):
        """Update checkbox text and style to match checked state AND theme"""
        spec = get_theme_spec(self.current_theme)
        is_light = spec["is_light"]
        
        unchecked_bg = "#F1F5F9" if is_light else spec["input_bg"]
        unchecked_border = spec["input_border"]
        unchecked_hover = spec["accent"]
        
        checkbox.setText("✓" if checked else "")
        
        if checked:
            bg = spec["accent_primary"]
            border = spec["accent"]
            color = "#FFFFFF"
        else:
            bg = unchecked_bg
            border = unchecked_border
            color = "transparent"
            
        checkbox.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 6px;
                color: {color};
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                border-color: {unchecked_hover if not checked else spec['accent_hover']};
            }}
        """)



class AddTaskDialog(QDialog):
    """Dialog for adding/editing a task with full icon picker"""
    
    def __init__(self, parent=None, task_data=None, icon_categories=None, theme=None):
        super().__init__(parent)
        self.task_data = task_data
        self.icon_categories = icon_categories or {}
        self.selected_icon = task_data.get('image_path') if task_data else None
        if theme is None and parent is not None:
            theme = getattr(parent, 'current_theme', 'dark')
        self.current_theme = theme or 'dark'
        
        self.setWindowTitle("Add Task" if not task_data else "Edit Task")
        self.setFixedSize(450, 550)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        
        self._setup_ui()
        self.apply_theme(self.current_theme)

    def showEvent(self, event):
        super().showEvent(event)
        apply_window_theme_frame(self, getattr(self, 'current_theme', 'dark'))
        
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
        
        def toggle_ampm():
            new_text = "PM" if ampm.text() == "AM" else "AM"
            ampm.setText(new_text)
            self._validate_form()
            
        ampm.clicked.connect(toggle_ampm)
        
        layout.addWidget(hour)
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
            
        p = p_box.text()
        
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
        
        self.form_frame = QWidget()
        self.icons_frame = QWidget()
        self._icon_picker_initialized = False
        
        self._setup_form()
        
        self.main_layout.addWidget(self.form_frame)
        self.main_layout.addWidget(self.icons_frame)
        self.icons_frame.hide()
        
    def _setup_form(self):
        layout = QVBoxLayout(self.form_frame)
        layout.setSpacing(15)
        
        # Task name
        self.task_name_label = QLabel("Task Name:")
        layout.addWidget(self.task_name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter task name...")
        if self.task_data:
            self.name_input.setText(self.task_data.get('name', ''))
        self.name_input.textChanged.connect(self._validate_form)
        layout.addWidget(self.name_input)
        
        # Icon section
        self.icon_label = QLabel("Icon:")
        layout.addWidget(self.icon_label)
        icon_row = QHBoxLayout()
        icon_row.setSpacing(10)
        
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(60, 60)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self._update_icon_preview()
        icon_row.addWidget(self.icon_preview)
        
        self.change_btn = QPushButton("Select Icon")
        self.change_btn.setCursor(Qt.PointingHandCursor)
        self.change_btn.clicked.connect(self._show_icon_picker)
        icon_row.addWidget(self.change_btn)
        
        self.or_label = QLabel(" or ")
        icon_row.addWidget(self.or_label)
        
        self.custom_img_btn = QPushButton("Custom Image")
        self.custom_img_btn.setCursor(Qt.PointingHandCursor)
        self.custom_img_btn.clicked.connect(self._on_custom_image)
        icon_row.addWidget(self.custom_img_btn)
        
        icon_row.addStretch()
        layout.addLayout(icon_row)
        
        # Time inputs
        time_layout = QHBoxLayout()
        
        self.start_label = QLabel("Start:")
        time_layout.addWidget(self.start_label)
        start_default = self.task_data.get('start_time', '09:00') if self.task_data else datetime.now().strftime("%H:%M")
        s_widget, self.start_hour, self.start_min, self.start_ampm = self._setup_time_picker(start_default)
        time_layout.addWidget(s_widget)
        
        self.end_label = QLabel("End:")
        time_layout.addWidget(self.end_label)
        end_default = self.task_data.get('end_time', '10:00') if self.task_data else (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        e_widget, self.end_hour, self.end_min, self.end_ampm = self._setup_time_picker(end_default)
        time_layout.addWidget(e_widget)
        
        layout.addLayout(time_layout)
        
        # Recurrence Section
        self.repeat_label = QLabel("Repeat Every:")
        layout.addWidget(self.repeat_label)
        recurrence_layout = QHBoxLayout()
        recurrence_layout.setSpacing(10)
        
        day_labels = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
        day_vals = [5, 6, 0, 1, 2, 3, 4]
        
        existing_days = self.task_data.get('repeat_days', [0,1,2,3,4,5,6]) if self.task_data else [0,1,2,3,4,5,6]
        
        self.day_buttons = {}
        
        for label, val in zip(day_labels, day_vals):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(val in existing_days)
            btn.setFixedSize(40, 40)
            
            def toggle_day(b=btn, v=val):
                spec = get_theme_spec(getattr(self, 'current_theme', 'dark'))
                is_light = spec["is_light"]
                is_checked = b.isChecked()
                unchecked_bg = "#E2E8F0" if is_light else spec["input_bg"]
                unchecked_fg = spec["text_muted"]
                unchecked_border = spec["input_border"]
                b.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {spec['accent_primary'] if is_checked else unchecked_bg};
                        color: {'#FFFFFF' if is_checked else unchecked_fg};
                        border: 1px solid {spec['accent'] if is_checked else unchecked_border};
                        border-radius: 18px;
                        font-weight: bold;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        border-color: {spec['accent']};
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
            self.delete_btn.clicked.connect(self._on_delete)
            btn_layout.addWidget(self.delete_btn)
            
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        
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
            self.selected_icon = file_path
            self.forceRefresh()
            self._validate_form()

    def forceRefresh(self):
        """User-requested immediate preview redraw"""
        self._update_icon_preview()
        self.update()

    def _update_icon_preview(self):
        """Intelligently display emoji or cached image in the preview box"""
        if not hasattr(self, 'icon_preview'): return
        
        try:
            icon_val = self.selected_icon if self.selected_icon else "❓"
            if not isinstance(icon_val, str): icon_val = str(icon_val)

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
            
            self.icon_preview.setPixmap(QPixmap()) 
            self.icon_preview.setFont(QFont("Segoe UI Emoji", 32))
            self.icon_preview.setText(icon_val)
        except Exception as e:
            print(f"Error updating icon preview: {e}")
            self.icon_preview.setText('❓')

    def _apply_icon_picker_theme(self):
        """Apply active theme palette to the icon picker view when initialized."""
        if not getattr(self, '_icon_picker_initialized', False):
            return
        spec = get_theme_spec(getattr(self, 'current_theme', 'dark'))
        is_light = spec["is_light"]
        ar, ag, ab = spec["accent_rgb"]
        fg = spec["text_main"]
        muted = spec["text_muted"]
        input_bg = spec["input_bg"]
        input_border = spec["input_border"]
        focus_border = spec["accent"]

        if hasattr(self, 'icon_back_btn'):
            self.icon_back_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba({ar}, {ag}, {ab}, {28 if is_light else 20});
                    color: {focus_border};
                    border: 1px solid {focus_border};
                    border-radius: 8px;
                    padding: 5px 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: rgba({ar}, {ag}, {ab}, {50 if is_light else 40});
                }}
            """)
        if hasattr(self, 'icon_picker_title'):
            self.icon_picker_title.setStyleSheet(f"color: {fg}; background: transparent;")
        if hasattr(self, 'icon_search_input'):
            self.icon_search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {fg};
                    border: 1px solid {input_border};
                    border-radius: 8px;
                    padding: 10px;
                    font-family: 'Segoe UI';
                }}
                QLineEdit:focus {{
                    border: 1px solid {focus_border};
                }}
            """)
        if hasattr(self, '_icon_scroll_content') and self._icon_scroll_content is not None:
            self._icon_scroll_content.setStyleSheet(f"""
                #IconScrollContent {{
                    background: transparent;
                }}
                #IconScrollContent QLabel {{
                    color: {muted};
                    background: transparent;
                }}
                #IconScrollContent QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                }}
                #IconScrollContent QPushButton:hover {{
                    background-color: rgba({ar}, {ag}, {ab}, 45);
                }}
            """)


    def apply_theme(self, theme):
        """Apply active theme palette to dialog"""
        self.current_theme = theme
        spec = get_theme_spec(theme)
        is_light = spec["is_light"]
        
        bg = spec["dialog_bg"]
        fg = spec["text_main"]
        muted = spec["text_muted"]
        input_bg = spec["input_bg"]
        input_border = spec["input_border"]
        focus_border = spec["accent"]

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(bg))
        pal.setColor(self.foregroundRole(), QColor(fg))
        self.setPalette(pal)

        # Ensure widget is polished before setting stylesheet so Qt's QStyleSheetStyle
        # never retains stale pre-polish cached rules.
        self.ensurePolished()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {fg};
            }}
            QLabel {{
                color: {fg};
                font-family: 'Segoe UI';
                background: transparent;
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI';
            }}
            QLineEdit:focus {{
                border: 1px solid {focus_border};
            }}
        """)
        self.style().unpolish(self)
        self.style().polish(self)

        for lbl_attr in ('task_name_label', 'icon_label', 'start_label', 'end_label', 'repeat_label'):
            if hasattr(self, lbl_attr):
                getattr(self, lbl_attr).setStyleSheet(f"color: {fg}; font-family: 'Segoe UI'; background: transparent;")
        if hasattr(self, 'or_label'):
            self.or_label.setStyleSheet(f"color: {muted}; font-family: 'Segoe UI'; background: transparent;")

        if hasattr(self, 'name_input'):
            self.name_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {input_bg};
                    color: {fg};
                    border: 1px solid {input_border};
                    border-radius: 8px;
                    padding: 10px;
                    font-family: 'Segoe UI';
                }}
                QLineEdit:focus {{
                    border: 1px solid {focus_border};
                }}
            """)

        inputs = [self.start_hour, self.start_min, self.end_hour, self.end_min]
        
        if all(hasattr(self, name) for name in ['start_hour', 'start_ampm']):
            input_style = f"""
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {input_border};
                border-radius: 8px;
                padding: 5px;
            """
            
            for inp in inputs:
                inp.setStyleSheet(f"QLineEdit {{ {input_style} }}")

            ampm_style = f"""
                QPushButton {{
                    background-color: {input_bg};
                    color: {fg};
                    border: 1px solid {input_border};
                    border-radius: 8px;
                    font-weight: bold;
                    padding: 6px;
                }}
                QPushButton:hover {{
                    border: 1px solid {focus_border};
                }}
            """
            for ampm_btn in (self.start_ampm, self.end_ampm):
                ampm_btn.setStyleSheet(ampm_style)

        if hasattr(self, 'icon_preview'):
            preview_bg = input_bg
            preview_border = f"1px solid {input_border}"
            self.icon_preview.setStyleSheet(f"background-color: {preview_bg}; border-radius: 12px; border: {preview_border};")

        def style_btn(btn, bg_col, fg_col, hover_bg, border_col):
            if hasattr(self, btn):
                getattr(self, btn).setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg_col};
                        color: {fg_col};
                        border: 1px solid {border_col};
                        border-radius: 8px;
                        padding: 10px {'20px' if 'change' not in btn else '15px'};
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {hover_bg};
                    }}
                    QPushButton:disabled {{
                        background-color: {'#E2E8F0' if is_light else input_bg};
                        color: {spec['text_muted']};
                        border: 1px solid {input_border};
                    }}
                """)

        if is_light:
            neutral_bg, neutral_fg, neutral_hover, neutral_border = "#E2E8F0", spec["text_main"], "#CBD5E1", input_border
        else:
            neutral_bg, neutral_fg, neutral_hover, neutral_border = input_bg, spec["text_main"], input_border, input_border

        primary_bg, primary_fg, primary_hover, primary_border = spec["accent_primary"], "#FFFFFF", spec["accent_hover"], spec["accent"]
        delete_bg, delete_fg, delete_hover, delete_border = "#E11D48", "#FFFFFF", "#F43F5E", "#FB7185"
            
        style_btn('change_btn', neutral_bg, neutral_fg, neutral_hover, neutral_border)
        style_btn('custom_img_btn', neutral_bg, neutral_fg, neutral_hover, neutral_border)
        style_btn('cancel_btn', neutral_bg, neutral_fg, neutral_hover, neutral_border)
        style_btn('save_btn', primary_bg, primary_fg, primary_hover, primary_border)
        style_btn('delete_btn', delete_bg, delete_fg, delete_hover, delete_border)

        if hasattr(self, 'day_buttons'):
            unchecked_bg = "#E2E8F0" if is_light else input_bg
            unchecked_fg = spec["text_muted"]
            unchecked_border = input_border
            checked_border = spec["accent"]
            
            for val, btn in self.day_buttons.items():
                is_checked = btn.isChecked()
                b_bg = spec["accent_primary"] if is_checked else unchecked_bg
                b_fg = "#FFFFFF" if is_checked else unchecked_fg
                b_border = checked_border if is_checked else unchecked_border
                
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {b_bg};
                        color: {b_fg};
                        border: 1px solid {b_border};
                        border-radius: 18px;
                        font-weight: bold;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        border-color: {spec['accent']};
                    }}
                """)

        self._apply_icon_picker_theme()
        apply_window_theme_frame(self, theme)


    def _setup_icon_picker(self):
        layout = QVBoxLayout(self.icons_frame)
        
        header = QHBoxLayout()
        self.icon_back_btn = QPushButton("← Back")
        self.icon_back_btn.clicked.connect(self._show_form)
        header.addWidget(self.icon_back_btn)
        
        self.icon_picker_title = QLabel("Select Icon")
        self.icon_picker_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.addWidget(self.icon_picker_title)
        header.addStretch()
        
        layout.addLayout(header)
        
        self.icon_search_input = QLineEdit()
        self.icon_search_input.setPlaceholderText("Search category...")
        layout.addWidget(self.icon_search_input)
        
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
        scroll_content.setObjectName("IconScrollContent")
        self._icon_scroll_content = scroll_content
        scroll_layout = QVBoxLayout(scroll_content)
        self._icon_category_sections = []
        self._icon_cat_labels = []
        self._icon_btns = []
        
        cols = 8
        for category, icons in self.icon_categories.items():
            section_widget = QWidget()
            section_layout = QVBoxLayout(section_widget)
            section_layout.setContentsMargins(0, 0, 0, 6)
            section_layout.setSpacing(6)

            cat_label = QLabel(category)
            cat_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            section_layout.addWidget(cat_label)
            self._icon_cat_labels.append(cat_label)
            
            grid = QGridLayout()
            grid.setSpacing(5)
            for i, icon in enumerate(icons):
                btn = QPushButton(icon)
                btn.setFont(QFont("Segoe UI Emoji", 18))
                btn.setFixedSize(40, 40)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, ic=icon: self._select_icon(ic))
                grid.addWidget(btn, i // cols, i % cols)
                self._icon_btns.append(btn)
                
            section_layout.addLayout(grid)
            scroll_layout.addWidget(section_widget)
            self._icon_category_sections.append((category.lower(), [str(ic) for ic in icons], section_widget))
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        def _filter_icons(text):
            query = text.strip().lower()
            for cat_lower, icon_list, sec_widget in self._icon_category_sections:
                if not query or query in cat_lower or any(query in ic for ic in icon_list):
                    sec_widget.show()
                else:
                    sec_widget.hide()

        self.icon_search_input.textChanged.connect(_filter_icons)
        
    def _show_icon_picker(self):
        if not self._icon_picker_initialized:
            self._setup_icon_picker()
            self._icon_picker_initialized = True
            self._apply_icon_picker_theme()
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
