from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    """Settings panel for configuring the translation app."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("设置")
        self.setFixedSize(360, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout()

        model_group = QGroupBox("语音识别模型")
        model_layout = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(["tiny", "base", "small"])
        self._model_combo.setCurrentText(self._config.whisper_model)
        model_layout.addRow("模型:", self._model_combo)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        display_group = QGroupBox("显示设置")
        display_layout = QFormLayout()

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setValue(int(self._config.opacity * 100))
        self._opacity_label = QLabel(f"{int(self._config.opacity * 100)}%")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        display_layout.addRow("透明度:", opacity_row)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(10, 24)
        self._font_spin.setValue(self._config.font_size)
        display_layout.addRow("字体大小:", self._font_spin)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        vad_group = QGroupBox("语音检测")
        vad_layout = QFormLayout()

        self._sensitivity_combo = QComboBox()
        self._sensitivity_combo.addItems(["0 (最严格)", "1", "2 (推荐)", "3 (最灵敏)"])
        self._sensitivity_combo.setCurrentIndex(self._config.vad_sensitivity)
        vad_layout.addRow("灵敏度:", self._sensitivity_combo)

        self._silence_spin = QSpinBox()
        self._silence_spin.setRange(300, 2000)
        self._silence_spin.setSingleStep(100)
        self._silence_spin.setValue(self._config.silence_threshold_ms)
        self._silence_spin.setSuffix(" ms")
        vad_layout.addRow("静音阈值:", self._silence_spin)

        self._max_segment_spin = QSpinBox()
        self._max_segment_spin.setRange(4, 20)
        self._max_segment_spin.setSingleStep(1)
        self._max_segment_spin.setValue(int(self._config.max_segment_seconds))
        self._max_segment_spin.setSuffix(" s")
        vad_layout.addRow("单段最长:", self._max_segment_spin)

        vad_group.setLayout(vad_layout)
        layout.addWidget(vad_group)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _save(self):
        self._config.whisper_model = self._model_combo.currentText()
        self._config.opacity = self._opacity_slider.value() / 100.0
        self._config.font_size = self._font_spin.value()
        self._config.vad_sensitivity = self._sensitivity_combo.currentIndex()
        self._config.silence_threshold_ms = self._silence_spin.value()
        self._config.max_segment_seconds = float(self._max_segment_spin.value())
        self._config.save()
        self.accept()
