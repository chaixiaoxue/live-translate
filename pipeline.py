import logging
import threading
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from audio.buffer import RingBuffer
from audio.vad import VADSegmenter

logger = logging.getLogger(__name__)


class TranslationResult:
    """Holds a single translation result."""

    def __init__(self, english: str, chinese: str):
        self.english = english
        self.chinese = chinese


class PipelineSignals(QObject):
    """Qt signals emitted by the processing pipeline."""
    translation_ready = pyqtSignal(str, str)  # (english, chinese)
    status_changed = pyqtSignal(str)           # status message


class ProcessingPipeline:
    """Wires VAD -> STT -> Translate into a processing loop.

    Runs in a dedicated thread, reading from the ring buffer,
    detecting sentences, transcribing, and translating.
    """

    def __init__(
        self,
        ring_buffer: RingBuffer,
        whisper_engine,
        translator,
        config,
    ):
        self._buffer = ring_buffer
        self._whisper = whisper_engine
        self._translator = translator
        self._config = config
        self._signals = PipelineSignals()
        self._running = False
        self._thread: threading.Thread | None = None
        self._vad: VADSegmenter | None = None

    @property
    def signals(self) -> PipelineSignals:
        return self._signals

    def start(self):
        """Start the processing pipeline in a background thread."""
        if self._running:
            return

        self._vad = VADSegmenter(
            sample_rate=16000,
            sensitivity=self._config.vad_sensitivity,
            silence_threshold_ms=self._config.silence_threshold_ms,
            max_segment_seconds=self._config.max_segment_seconds,
        )
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        logger.info("Processing pipeline started.")

    def stop(self, flush: bool = True):
        """Stop the processing pipeline."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        # Flush any remaining speech from VAD
        if flush and self._vad:
            remaining = self._vad.flush()
            for segment in remaining:
                if len(segment) >= 8000:
                    try:
                        english_text = self._whisper.transcribe(segment)
                        if english_text:
                            chinese_text = self._translator.translate(english_text)
                            if chinese_text:
                                self._signals.translation_ready.emit(english_text, chinese_text)
                    except Exception as e:
                        logger.error("Flush error: %s", e)
        logger.info("Processing pipeline stopped.")

    def _process_loop(self):
        """Main processing loop: buffer -> VAD -> STT -> translate -> signal."""
        import time

        while self._running:
            audio = self._buffer.read_all()

            if len(audio) == 0:
                time.sleep(0.1)
                continue

            segments = self._vad.process(audio)

            for segment in segments:
                if not self._running:
                    break

                if len(segment) < 8000:
                    continue

                try:
                    self._signals.status_changed.emit("识别中...")
                    english_text = self._whisper.transcribe(segment)

                    if not english_text:
                        continue

                    self._signals.status_changed.emit("翻译中...")
                    chinese_text = self._translator.translate(english_text)

                    if not chinese_text:
                        continue

                    self._signals.translation_ready.emit(english_text, chinese_text)
                    logger.info("EN: %s -> ZH: %s", english_text, chinese_text)

                except Exception as e:
                    logger.error("Pipeline error: %s", e)
                    self._signals.status_changed.emit(f"错误: {e}")

            time.sleep(0.05)

    @property
    def is_running(self) -> bool:
        return self._running
