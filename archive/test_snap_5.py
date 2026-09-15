import sys, ctypes
from ctypes import wintypes
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QTimer, QRect
class TestWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet('background: transparent;')
        self.resize(800, 600)
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0)
        self.w = QWidget(); self.w.setStyleSheet('background: white;'); l.addWidget(self.w)
        ll = QVBoxLayout(self.w); self.title = QLabel('Drag Me'); ll.addWidget(self.title); ll.addStretch()
    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(message.__int__())
        if msg.message == 0x0084:
            x = msg.lParam & 0xFFFF; y = (msg.lParam >> 16) & 0xFFFF
            if x > 32767: x -= 65536
            if y > 32767: y -= 65536
            lx = x - self.x(); ly = y - self.y()
            if ly < 32: return True, 2
            return True, 1
        return super().nativeEvent(eventType, message)
app = QApplication(sys.argv)
w = TestWin(); w.showMaximized()
def pr(): print(f'Geometry: {w.geometry()} Screen: {app.primaryScreen().availableGeometry()}'); sys.exit(0)
QTimer.singleShot(1000, pr)
sys.exit(app.exec())
