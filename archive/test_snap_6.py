import sys, ctypes
from ctypes import wintypes
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QCursor
class TestWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet('background: transparent;')
        self.resize(800, 600)
        hwnd = int(self.winId()); GWL_STYLE = -16; WS_THICKFRAME = 0x00040000; WS_CAPTION = 0x00C00000
        import platform; user32 = ctypes.windll.user32
        if platform.architecture()[0] == '64bit':
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE); user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_CAPTION)
        else:
            style = user32.GetWindowLongW(hwnd, GWL_STYLE); user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_CAPTION)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
        self.main_l = QVBoxLayout(self); self.main_l.setContentsMargins(0,0,0,0)
        self.w = QWidget(); self.w.setStyleSheet('background: #2B2B2B; color: white;'); self.main_l.addWidget(self.w)
        l = QVBoxLayout(self.w); l.setContentsMargins(0,0,0,0)
        tb = QHBoxLayout(); l.addLayout(tb)
        self.title = QLabel('Drag Me'); tb.addWidget(self.title); tb.addStretch()
        min_btn = QPushButton('-'); tb.addWidget(min_btn); min_btn.clicked.connect(self.showMinimized)
        max_btn = QPushButton('O'); tb.addWidget(max_btn); max_btn.clicked.connect(self.toggle_max)
        l.addStretch()
    def toggle_max(self):
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()
    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(message.__int__())
        if msg.message == 0x0083 and msg.wParam:
            return True, 0
        if msg.message == 0x0084:
            pt = QCursor.pos(); x = pt.x(); y = pt.y(); lx = x - self.x(); ly = y - self.y()
            w = self.width(); h = self.height()
            is_max = ctypes.windll.user32.IsZoomed(msg.hWnd)
            bor_side = 0 if is_max else 8; bor_top = 0 if is_max else 4
            left = lx < bor_side; right = lx > w - bor_side; top = ly < bor_top; bottom = ly > h - bor_side
            caption = (ly >= 0 and ly < 32) and not (lx > w - 100)
            if not is_max:
                if top and left: return True, 0xD
                if top and right: return True, 0xE
                if bottom and left: return True, 0x10
                if bottom and right: return True, 0x11
                if left: return True, 0xA
                if right: return True, 0xB
                if top: return True, 0xC
                if bottom: return True, 0xF
            if caption: return True, 0x2
        return super().nativeEvent(eventType, message)
app = QApplication(sys.argv)
w = TestWin(); w.show()
def test_margins():
    w.showMaximized()
    def chk():
        if ctypes.windll.user32.IsZoomed(int(w.winId())):
            margin = 8; w.main_l.setContentsMargins(margin, margin, margin, margin)
    QTimer.singleShot(100, chk)
QTimer.singleShot(1000, test_margins)
QTimer.singleShot(3000, lambda: sys.exit(0))
sys.exit(app.exec())
