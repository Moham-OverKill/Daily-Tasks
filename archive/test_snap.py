import sys, ctypes
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QCursor
class TestWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        # NO WA_TranslucentBackground
        self.setStyleSheet('background-color: #2B2B2B; color: white;')
        self.resize(800, 600)
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0)
        self.title = QLabel('Drag Me'); l.addWidget(self.title); l.addStretch()
    def nativeEvent(self, t, m):
        msg = ctypes.wintypes.MSG.from_address(m.__int__())
        if msg.message == 0x0083 and msg.wParam:
            return True, 0
        if msg.message == 0x0084:
            x = msg.lParam & 0xFFFF; y = (msg.lParam >> 16) & 0xFFFF
            lx = x - self.x(); ly = y - self.y()
            if ly < 32: return True, 2
            return True, 1
        return super().nativeEvent(t, m)
app = QApplication(sys.argv)
w = TestWin(); w.show()
sys.exit(app.exec())
