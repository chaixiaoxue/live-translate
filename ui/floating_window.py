import psutil
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QGraphicsDropShadowEffect,
)


class FloatingWindow(QWidget):
    """Always-on-top transparent floating window for translation display."""

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._is_paused = False
        self._items: list[dict] = []  # {"english": str, "chinese": str}
        self._on_settings_callback = None
        self._setup_ui()
        self._setup_cpu_timer()

    def _setup_ui(self):
        self.setWindowTitle("Live Translate")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(self._config.opacity)

        if self._config.window_x is not None:
            self.move(self._config.window_x, self._config.window_y)
        self.resize(self._config.window_width, self._config.window_height)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_bar = QHBoxLayout()
        title_label = QLabel("⏺ Live Translate")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        layout.addLayout(title_bar)

        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(6)
        layout.addLayout(self._content_layout)

        self._placeholder = QLabel("等待音频...")
        self._placeholder.setStyleSheet("color: #aaaaaa; font-size: 14px;")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(self._placeholder)

        layout.addStretch()

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self._btn_start = QPushButton("▶ 开始")
        self._btn_start.setStyleSheet(self._button_style("#4CAF50"))
        self._btn_start.clicked.connect(self._on_start)

        self._btn_pause = QPushButton("⏸ 暂停")
        self._btn_pause.setStyleSheet(self._button_style("#FF9800"))
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_pause.setEnabled(False)

        self._btn_settings = QPushButton("⚙ 设置")
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

        self.setStyleSheet("""
            FloatingWindow {
                background-color: rgba(30, 30, 30, 230);
                border-radius: 10px;
            }
        """)

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
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._placeholder.setParent(None)

        for entry in reversed(self._items):
            en_label = QLabel(f"🎤 {entry['english']}")
            en_label.setWordWrap(True)
            en_label.setStyleSheet("color: #e0e0e0; font-size: 13px;")
            en_label.setFont(QFont("Segoe UI", self._config.font_size - 2))

            zh_label = QLabel(f"📝 {entry['chinese']}")
            zh_label.setWordWrap(True)
            zh_label.setStyleSheet("color: #4FC3F7; font-size: 15px;")
            zh_label.setFont(QFont("Microsoft YaHei", self._config.font_size))

            self._content_layout.addWidget(en_label)
            self._content_layout.addWidget(zh_label)

            sep = QLabel("─" * 40)
            sep.setStyleSheet("color: #444444; font-size: 10px;")
            self._content_layout.addWidget(sep)

    def _on_start(self):
        self._is_paused = False
        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._placeholder.setText("等待音频...")

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
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        label = QLabel(message)
        label.setStyleSheet("color: #FFD54F; font-size: 14px;")
        label.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(label)

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def closeEvent(self, event):
        self._config.window_x = self.x()
        self._config.window_y = self.y()
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.save()
        event.accept()
