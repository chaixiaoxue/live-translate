import logging
import os
import sys

from config import Config
from audio.buffer import RingBuffer
from audio.capture import AudioCapture
from stt.whisper_engine import WhisperEngine
from translate.argos_engine import ArgosTranslator
from pipeline import ProcessingPipeline

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

from ui.floating_window import FloatingWindow
from ui.settings_dialog import SettingsDialog
from ui.tray_icon import TrayIcon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _configure_file_logging(project_dir: str):
    log_path = os.path.join(project_dir, "live_translate.log")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    logging.getLogger().addHandler(file_handler)


def main():
    project_dir = os.path.dirname(__file__)
    _configure_file_logging(project_dir)

    config = Config(config_path=os.path.join(project_dir, "config.json"))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setProperty("is_quitting", False)
    app.aboutToQuit.connect(lambda: logger.info("Qt application is quitting."))

    window = FloatingWindow(config)
    tray = TrayIcon(app)

    def show_settings():
        dialog = SettingsDialog(config, parent=window)
        if dialog.exec_():
            window.setWindowOpacity(config.opacity)
            window._refresh_display()

    def show_window():
        window.showNormal()
        window.raise_()
        window.activateWindow()

    window.set_settings_callback(show_settings)
    show_window()
    window.set_loading("Loading speech model...")

    ring_buffer = RingBuffer(sample_rate=16000, max_seconds=30)

    def init_models():
        try:
            logger.info("Initializing models.")
            whisper = WhisperEngine(
                model_size=config.whisper_model,
                language=config.language,
            )

            window.set_loading("Loading translation model...")
            translator = ArgosTranslator(from_lang="en", to_lang="zh")

            capture = AudioCapture(ring_buffer, target_sample_rate=16000)
            pipeline = ProcessingPipeline(
                ring_buffer=ring_buffer,
                whisper_engine=whisper,
                translator=translator,
                config=config,
            )

            pipeline.signals.translation_ready.connect(window.add_translation)
            pipeline.signals.status_changed.connect(
                lambda msg: logger.info("Status: %s", msg)
            )

            def on_start():
                try:
                    capture.start()
                    pipeline.start()
                    window.set_status("Listening to system audio...")
                except Exception as e:
                    logger.exception("Failed to start listening.")
                    pipeline.stop()
                    capture.stop()
                    window.set_stopped()
                    window.set_loading(f"Start failed: {e}")

            def on_pause():
                try:
                    pipeline.stop()
                    capture.stop()
                    window.set_status("Paused")
                except Exception:
                    logger.exception("Failed to pause listening.")

            def quit_app():
                app.setProperty("is_quitting", True)
                capture.stop()
                pipeline.stop()
                app.quit()

            window._btn_start.clicked.connect(on_start)
            window._btn_pause.clicked.connect(on_pause)
            tray.show_window.connect(show_window)
            tray.quit_app.connect(quit_app)
            tray.show()

            app._live_translate_runtime = {
                "capture": capture,
                "pipeline": pipeline,
                "tray": tray,
                "window": window,
            }
            app._live_translate_keepalive = QTimer()
            app._live_translate_keepalive.timeout.connect(lambda: None)
            app._live_translate_keepalive.start(1000)

            window.set_loading("Ready. Click Start.")
            logger.info("Application initialized.")
        except Exception as e:
            logger.exception("Failed to initialize.")
            window.set_loading(f"Initialization failed: {e}")

    QTimer.singleShot(100, init_models)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
