import sys
import logging
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from config import Config
from audio.buffer import RingBuffer
from audio.capture import AudioCapture
from stt.whisper_engine import WhisperEngine
from translate.argos_engine import ArgosTranslator
from pipeline import ProcessingPipeline
from ui.floating_window import FloatingWindow
from ui.settings_dialog import SettingsDialog
from ui.tray_icon import TrayIcon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # Config
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    config = Config(config_path=config_path)

    # Initialize Qt
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # UI
    window = FloatingWindow(config)
    tray = TrayIcon()

    # Settings dialog callback
    def show_settings():
        dialog = SettingsDialog(config, parent=window)
        if dialog.exec_():
            window.setWindowOpacity(config.opacity)
            window._refresh_display()

    window.set_settings_callback(show_settings)

    # Audio pipeline
    ring_buffer = RingBuffer(sample_rate=16000, max_seconds=30)

    # Show loading state
    window.show()
    window.set_loading("正在加载语音识别模型...")

    # Use QTimer to load models asynchronously (keep UI responsive)
    def init_models():
        try:
            whisper = WhisperEngine(
                model_size=config.whisper_model,
                language=config.language,
            )
            window.set_loading("正在加载翻译模型...")
            translator = ArgosTranslator(from_lang="en", to_lang="zh")
            window.set_loading("模型加载完成，准备就绪。")

            # Audio capture
            capture = AudioCapture(ring_buffer, target_sample_rate=16000)

            # Processing pipeline
            pipeline = ProcessingPipeline(
                ring_buffer=ring_buffer,
                whisper_engine=whisper,
                translator=translator,
                config=config,
            )

            # Connect signals
            pipeline.signals.translation_ready.connect(window.add_translation)
            pipeline.signals.status_changed.connect(
                lambda msg: logger.info("Status: %s", msg)
            )

            # Start/stop with window controls
            def on_start():
                capture.start()
                pipeline.start()

            def on_pause():
                pipeline.stop()
                capture.stop()

            window._btn_start.clicked.connect(on_start)
            window._btn_pause.clicked.connect(on_pause)

            # Tray
            tray.show_window.connect(window.show)
            tray.quit_app.connect(lambda: (capture.stop(), pipeline.stop(), app.quit()))
            tray.show()

        except Exception as e:
            logger.error("Failed to initialize: %s", e)
            window.set_loading(f"初始化失败: {e}")

    QTimer.singleShot(100, init_models)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
