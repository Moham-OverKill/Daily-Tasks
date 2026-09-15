import sys, ctypes
from ctypes import wintypes
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QCursor
class TestWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet('background-color: white; color: black;')
        self.resize(800, 600)
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0)
        self.title = QLabel('Drag Me'); l.addWidget(self.title); l.addStretch()
    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(message.__int__())
        if msg.message == 0x0083 and msg.wParam:
            return True, 0
        if msg.message == 0x0084:
            x = msg.lParam & 0xFFFF; y = (msg.lParam >> 16) & 0xFFFF
            if x > 32767: x -= 65536
            if y > 32767: y -= 65536
            lx = x - self.x(); ly = y - self.y()
            if ly < 32: return True, 2
            return True, 1
        return super().nativeEvent(eventType, message)
app = QApplication(sys.argv)
w = TestWin(); w.show()
QTimer.singleShot(2000, lambda: sys.exit(0))
sys.exit(app.exec())
