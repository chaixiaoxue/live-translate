import psutil
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from html import escape


class FloatingWindow(QWidget):
    """Always-on-top transparent floating window for translation display."""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._is_paused = False
        self._items: list[dict] = []
        self._on_settings_callback = None
        self._setup_ui()
        self._setup_cpu_timer()

    def _setup_ui(self):
        self.setWindowTitle("Live Translate")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowOpacity(self._config.opacity)

        if self._config.window_x is not None:
            self.move(self._config.window_x, self._config.window_y)
        self.resize(self._config.window_width, self._config.window_height)
        self._ensure_on_screen()

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_bar = QHBoxLayout()
        title_label = QLabel("Live Translate")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        layout.addLayout(title_bar)

        self._content_view = QTextBrowser()
        self._content_view.setReadOnly(True)
        self._content_view.setOpenExternalLinks(False)
        self._content_view.setFrameShape(QTextBrowser.NoFrame)
        self._content_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._content_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_view.setFont(QFont("Microsoft YaHei", self._config.font_size))
        self._content_view.setStyleSheet(
            """
            QTextBrowser {
                background: transparent;
                border: none;
                color: #e0e0e0;
            }
            QScrollBar:vertical {
                background: #1c1c1c;
                width: 8px;
                margin: 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
        )
        layout.addWidget(self._content_view, 1)
        self.set_loading("Waiting for audio...")

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self._btn_start = QPushButton("Start")
        self._btn_start.setStyleSheet(self._button_style("#4CAF50"))
        self._btn_start.clicked.connect(self._on_start)

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.setStyleSheet(self._button_style("#FF9800"))
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_pause.setEnabled(False)

        self._btn_settings = QPushButton("Settings")
        self._btn_settings.setStyleSheet(self._button_style("#2196F3"))
        self._btn_settings.clicked.connect(self._on_settings)

        controls.addWidget(self._btn_start)
        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_settings)
        controls.addStretch()

        self._cpu_label = QLabel("CPU: --%")
        self._cpu_label.setStyleSheet("color: #888888; font-size: 11px;")
        controls.addWidget(self._cpu_label)

        layout.addLayout(controls)
        self.setLayout(layout)

        self.setStyleSheet(
            """
            FloatingWindow {
                background-color: #121212;
                border: 1px solid #2f2f2f;
                border-radius: 10px;
            }
            """
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _button_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
            QPushButton:disabled {{
                background-color: #555555;
                color: #888888;
            }}
        """

    def _setup_cpu_timer(self):
        self._cpu_timer = QTimer()
        self._cpu_timer.timeout.connect(self._update_cpu)
        self._cpu_timer.start(2000)

    def _update_cpu(self):
        cpu = psutil.cpu_percent(interval=None)
        self._cpu_label.setText(f"CPU: {cpu:.0f}%")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, "_drag_pos") and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    @pyqtSlot(str, str)
    def add_translation(self, english: str, chinese: str):
        """Add a new translation result to the display."""
        if self._is_paused:
            return
        self._items.append({"english": english, "chinese": chinese})
        while len(self._items) > self._config.max_display_items:
            self._items.pop(0)
        self._refresh_display()

    def _refresh_display(self):
        blocks = []
        for entry in reversed(self._items):
            english = escape(entry["english"])
            chinese = escape(entry["chinese"])
            blocks.append(
                f"""
                <div style="margin-bottom: 10px;">
                    <div style="color: #e0e0e0; font-size: {self._config.font_size - 2}px;">
                        {english}
                    </div>
                    <div style="color: #4fc3f7; font-size: {self._config.font_size}px; margin-top: 4px;">
                        {chinese}
                    </div>
                    <div style="color: #444444; margin-top: 8px;">------------------------------</div>
                </div>
                """
            )

        self._content_view.setHtml(
            """
            <html>
            <body style="margin: 0; padding: 0; font-family: Microsoft YaHei, Segoe UI, sans-serif;">
            """
            + "\n".join(blocks)
            + """
            </body>
            </html>
            """
        )
        self._content_view.verticalScrollBar().setValue(0)

    def _on_start(self):
        self._is_paused = False
        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self.set_loading("Waiting for audio...")

    def _on_pause(self):
        self._is_paused = True
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)

    def _on_settings(self):
        if self._on_settings_callback:
            self._on_settings_callback()

    def set_settings_callback(self, callback):
        self._on_settings_callback = callback

    def set_loading(self, message: str):
        self._content_view.setHtml(
            f"""
            <html>
            <body style="margin: 0; padding: 0; color: #ffd54f; font-size: 14px;
                         font-family: Microsoft YaHei, Segoe UI, sans-serif;">
                {escape(message)}
            </body>
            </html>
            """
        )

    def _clear_content(self):
        self._content_view.clear()

    def set_status(self, message: str):
        self.set_loading(message)

    def set_stopped(self):
        self._is_paused = True
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def closeEvent(self, event):
        app = QApplication.instance()
        if app is not None and not app.property("is_quitting"):
            self.hide()
            event.ignore()
            return

        self._config.window_x = self.x()
        self._config.window_y = self.y()
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.save()
        event.accept()

    def _ensure_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = min(max(self.x(), available.left()), available.right() - self.width())
        y = min(max(self.y(), available.top()), available.bottom() - self.height())
        if x != self.x() or y != self.y():
            self.move(x, y)
