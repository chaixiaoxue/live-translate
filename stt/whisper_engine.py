import logging
import numpy as np
import torch  # noqa: F401 - load torch DLLs before ctranslate2 on Windows.
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class WhisperEngine:
    """Speech-to-text using faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "base", language: str = "en"):
        self._language = language
        logger.info("Loading Whisper model: %s", model_size)
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe 16kHz mono 16-bit PCM audio to text.

        Args:
            audio: Audio samples as int16 ndarray.

        Returns:
            Transcribed English text, or empty string if audio is too short.
        """
        if len(audio) < 1600:  # < 0.1s
            return ""

        # faster-whisper expects float32 normalized to [-1, 1]
        audio_float = audio.astype(np.float32) / 32768.0

        segments, info = self._model.transcribe(
            audio_float,
            language=self._language,
            beam_size=5,
            vad_filter=False,  # We already do VAD
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        return " ".join(text_parts).strip()

    def unload(self):
        """Release model resources."""
        self._model = None
