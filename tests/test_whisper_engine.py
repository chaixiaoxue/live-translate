from unittest.mock import MagicMock, patch
import numpy as np
from stt.whisper_engine import WhisperEngine


def test_transcribe_returns_text():
    """Should return transcribed text from audio."""
    mock_model = MagicMock()
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_model.transcribe.return_value = (
        iter([MagicMock(text="Hello everyone, let's start the meeting.")]),
        mock_info,
    )

    engine = WhisperEngine.__new__(WhisperEngine)
    engine._model = mock_model
    engine._language = "en"

    audio = np.random.randint(-3000, 3000, size=16000, dtype=np.int16)
    result = engine.transcribe(audio)

    assert result == "Hello everyone, let's start the meeting."
    mock_model.transcribe.assert_called_once()


def test_transcribe_empty_audio():
    """Should return empty string for very short audio."""
    engine = WhisperEngine.__new__(WhisperEngine)
    engine._model = MagicMock()
    engine._language = "en"

    audio = np.array([], dtype=np.int16)
    result = engine.transcribe(audio)
    assert result == ""


def test_transcribe_returns_stripped_text():
    """Should strip leading/trailing whitespace from result."""
    mock_model = MagicMock()
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_model.transcribe.return_value = (
        iter([MagicMock(text="  Hello world.  ")]),
        mock_info,
    )

    engine = WhisperEngine.__new__(WhisperEngine)
    engine._model = mock_model
    engine._language = "en"

    audio = np.random.randint(-3000, 3000, size=16000, dtype=np.int16)
    result = engine.transcribe(audio)
    assert result == "Hello world."
