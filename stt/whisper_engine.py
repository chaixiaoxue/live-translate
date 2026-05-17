import logging
import os
from pathlib import Path
import numpy as np

from app_paths import app_dir

os.environ.setdefault("HF_HOME", str(app_dir() / ".cache-data" / "huggingface"))

logger = logging.getLogger(__name__)


def _find_local_model(model_size: str) -> Path | None:
    model_path = Path(model_size)
    if model_path.exists():
        return model_path

    cache_name = f"models--Systran--faster-whisper-{model_size}"
    snapshots_dir = app_dir() / ".cache-data" / "huggingface" / "hub" / cache_name / "snapshots"
    if not snapshots_dir.exists():
        return None

    candidates = sorted(
        (path for path in snapshots_dir.iterdir() if (path / "model.bin").exists()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


class WhisperEngine:
    """Speech-to-text using faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "base", language: str = "en"):
        self._language = language
        logger.info("Importing faster-whisper runtime.")
        from faster_whisper import WhisperModel

        local_model = _find_local_model(model_size)
        if local_model is not None:
            logger.info("Loading local Whisper model: %s", local_model)
            self._model = WhisperModel(
                str(local_model),
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
        else:
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
