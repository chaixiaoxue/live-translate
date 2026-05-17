import os
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStyle, QSystemTrayIcon, QMenu, QAction


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu."""

    show_window = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            icon = QIcon.fromTheme("audio-input-microphone")
            if icon.isNull() and QApplication.instance() is not None:
                icon = QApplication.instance().style().standardIcon(
                    QStyle.SP_ComputerIcon
                )
            self.setIcon(icon)

        self.setToolTip("Live Translate - 实时翻译")

        menu = QMenu()

        show_action = QAction("显示窗口", menu)
        show_action.triggered.connect(self.show_window.emit)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window.emit()
