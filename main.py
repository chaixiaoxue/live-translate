import logging
import os
import sys
import atexit

import psutil

from app_paths import app_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

_INSTANCE_LOCK_PATH = None


def _configure_file_logging(project_dir: str):
    log_path = os.path.join(project_dir, "live_translate.log")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    )
    logging.getLogger().addHandler(file_handler)


def _command_belongs_to_project(command_line: str, project_dir: str) -> bool:
    normalized_cmd = os.path.normcase(command_line or "")
    normalized_project = os.path.normcase(os.path.abspath(project_dir))
    return normalized_project in normalized_cmd and "main.py" in normalized_cmd


def _acquire_pid_lock(project_dir: str) -> bool:
    """Use a project-local pid file to prevent duplicate GUI instances."""
    global _INSTANCE_LOCK_PATH
    lock_path = os.path.join(project_dir, "live_translate.pid")
    current_pid = os.getpid()

    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(current_pid))
            break
        except FileExistsError:
            try:
                with open(lock_path, "r", encoding="utf-8") as f:
                    existing_pid = int(f.read().strip())
                if existing_pid != current_pid and psutil.pid_exists(existing_pid):
                    proc = psutil.Process(existing_pid)
                    command_line = " ".join(proc.cmdline())
                    if _command_belongs_to_project(command_line, project_dir):
                        logger.info(
                            "Another Live Translate instance is already running: %s",
                            existing_pid,
                        )
                        return False
            except (OSError, ValueError, psutil.Error):
                pass

            try:
                os.remove(lock_path)
            except OSError:
                return False

    _INSTANCE_LOCK_PATH = lock_path
    atexit.register(_release_pid_lock)
    return True


def _release_pid_lock():
    if _INSTANCE_LOCK_PATH is None:
        return

    try:
        with open(_INSTANCE_LOCK_PATH, "r", encoding="utf-8") as f:
            locked_pid = int(f.read().strip())
        if locked_pid == os.getpid():
            os.remove(_INSTANCE_LOCK_PATH)
    except (OSError, ValueError):
        pass


def main():
    project_dir = str(app_dir())
    _configure_file_logging(project_dir)
    logger.info("Starting Live Translate from %s", project_dir)

    if not _acquire_pid_lock(project_dir):
        logger.info("Another Live Translate instance is already running. Exiting.")
        return

    logger.info("Importing PyQt...")
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication

    logger.info("Importing audio pipeline modules...")
    from audio.buffer import RingBuffer
    from audio.capture import AudioCapture
    from config import Config
    from pipeline import ProcessingPipeline

    logger.info("Importing speech model module...")
    from stt.whisper_engine import WhisperEngine

    logger.info("Importing translation module...")
    from translate.argos_engine import ArgosTranslator

    logger.info("Importing UI modules...")
    from ui.floating_window import FloatingWindow
    from ui.settings_dialog import SettingsDialog
    from ui.tray_icon import TrayIcon
    logger.info("Imports complete.")

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
            runtime = getattr(app, "_live_translate_runtime", {})
            capture = runtime.get("capture")
            if capture is not None:
                try:
                    capture.set_device_name(config.audio_device_name)
                except RuntimeError:
                    logger.info("Audio device change will apply after pausing.")

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

            capture = AudioCapture(
                ring_buffer,
                target_sample_rate=16000,
                device_name=config.audio_device_name,
            )
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
                    capture.stop()
                    pipeline.stop(flush=False)
                    window.set_status("Paused")
                except Exception:
                    logger.exception("Failed to pause listening.")

            def quit_app():
                app.setProperty("is_quitting", True)
                capture.stop()
                pipeline.stop(flush=True)
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
