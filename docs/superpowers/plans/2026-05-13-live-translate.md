# Live Translate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop app that captures system audio, recognizes English speech in real-time, translates to Chinese, and displays results in an always-on-top floating window.

**Architecture:** Three-thread model — audio capture thread fills a ring buffer, processing thread runs VAD→STT→translate pipeline, main thread runs PyQt5 UI. Qt signals bridge threads.

**Tech Stack:** Python 3.10+, faster-whisper, argostranslate, pyaudiowpatch, webrtcvad, PyQt5, numpy

---

## File Structure

```
live-translate/
├── main.py                     # Entry point: init models, wire pipeline, launch UI
├── requirements.txt            # All dependencies
├── config.py                   # Singleton config: model paths, UI settings, defaults
├── tests/
│   ├── __init__.py
│   ├── test_config.py          # Config load/save/defaults
│   ├── test_buffer.py          # Ring buffer write/read/overflow
│   ├── test_vad.py             # VAD segment detection
│   ├── test_whisper_engine.py  # Whisper transcription (mock model)
│   └── test_argos_engine.py    # Argos translation (mock translator)
├── audio/
│   ├── __init__.py
│   ├── capture.py              # WASAPI loopback audio capture thread
│   ├── buffer.py               # Thread-safe ring buffer for PCM audio
│   └── vad.py                  # Voice activity detection, sentence segmentation
├── stt/
│   ├── __init__.py
│   └── whisper_engine.py       # faster-whisper wrapper: audio bytes → English text
├── translate/
│   ├── __init__.py
│   └── argos_engine.py         # Argos Translate wrapper: English text → Chinese text
├── ui/
│   ├── __init__.py
│   ├── floating_window.py      # Main always-on-top overlay window
│   ├── settings_dialog.py      # Settings panel dialog
│   └── tray_icon.py            # System tray icon and menu
└── assets/
    └── icon.ico                # App icon (16x16, 32x32, 48x48 multi-res)
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `live-translate/requirements.txt`
- Create: `live-translate/config.py`
- Create: `live-translate/tests/__init__.py`
- Create: `live-translate/tests/test_config.py`

- [ ] **Step 1: Create project directory and requirements.txt**

```bash
mkdir -p live-translate/{audio,stt,translate,ui,assets,tests}
```

Create `live-translate/requirements.txt`:
```
faster-whisper>=1.0.0
argostranslate>=1.9.0
pyaudiowpatch>=0.2.12
webrtcvad>=2.0.10
PyQt5>=5.15.0
numpy>=1.24.0
psutil>=5.9.0
pytest>=7.0.0
```

Create empty `__init__.py` in each package:
```bash
touch live-translate/audio/__init__.py
touch live-translate/stt/__init__.py
touch live-translate/translate/__init__.py
touch live-translate/ui/__init__.py
touch live-translate/tests/__init__.py
```

- [ ] **Step 2: Write the failing test for config**

Create `live-translate/tests/test_config.py`:
```python
import json
import os
import tempfile
from config import Config


def test_default_values():
    """Config should have sensible defaults when no file exists."""
    cfg = Config(config_path="/tmp/nonexistent_config.json")
    assert cfg.whisper_model == "base"
    assert cfg.language == "en"
    assert cfg.opacity == 0.85
    assert cfg.font_size == 14
    assert cfg.max_display_items == 3
    assert cfg.vad_sensitivity == 2
    assert cfg.silence_threshold_ms == 800


def test_save_and_load():
    """Config should round-trip through save/load."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        path = f.name

    try:
        cfg = Config(config_path=path)
        cfg.opacity = 0.5
        cfg.font_size = 20
        cfg.whisper_model = "small"
        cfg.save()

        cfg2 = Config(config_path=path)
        assert cfg2.opacity == 0.5
        assert cfg2.font_size == 20
        assert cfg2.whisper_model == "small"
    finally:
        os.unlink(path)


def test_update_from_dict():
    """Config should accept partial updates."""
    cfg = Config(config_path="/tmp/nonexistent_config.json")
    cfg.update({"opacity": 0.6, "font_size": 18})
    assert cfg.opacity == 0.6
    assert cfg.font_size == 18
    assert cfg.whisper_model == "base"  # unchanged
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd live-translate && python -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 4: Implement config.py**

Create `live-translate/config.py`:
```python
import json
import os


class Config:
    """Application configuration with file persistence."""

    DEFAULTS = {
        "whisper_model": "base",
        "language": "en",
        "opacity": 0.85,
        "font_size": 14,
        "max_display_items": 3,
        "vad_sensitivity": 2,
        "silence_threshold_ms": 800,
        "window_x": None,
        "window_y": None,
        "window_width": 400,
        "window_height": 300,
    }

    def __init__(self, config_path: str = "config.json"):
        self._path = config_path
        for key, value in self.DEFAULTS.items():
            setattr(self, key, value)
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in self.DEFAULTS:
                    setattr(self, key, value)
        except (json.JSONDecodeError, IOError):
            pass

    def save(self):
        data = {key: getattr(self, key) for key in self.DEFAULTS}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def update(self, data: dict):
        for key, value in data.items():
            if key in self.DEFAULTS:
                setattr(self, key, value)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd live-translate && python -m pytest tests/test_config.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add live-translate/
git commit -m "feat: project scaffolding with config module"
```

---

### Task 2: Ring Buffer

**Files:**
- Create: `live-translate/audio/buffer.py`
- Create: `live-translate/tests/test_buffer.py`

- [ ] **Step 1: Write the failing test**

Create `live-translate/tests/test_buffer.py`:
```python
import numpy as np
from audio.buffer import RingBuffer


def test_write_and_read():
    """Should write PCM samples and read them back."""
    buf = RingBuffer(sample_rate=16000, max_seconds=5)
    samples = np.array([1, 2, 3, 4, 5], dtype=np.int16)
    buf.write(samples)

    result = buf.read_all()
    np.testing.assert_array_equal(result, samples)


def test_overflow_discards_old():
    """When buffer is full, oldest samples should be discarded."""
    buf = RingBuffer(sample_rate=16000, max_seconds=1)  # max 16000 samples
    buf.write(np.ones(10000, dtype=np.int16))
    buf.write(np.ones(10000, dtype=np.int16))  # overflow

    result = buf.read_all()
    assert len(result) <= 16000


def test_read_all_clears_buffer():
    """read_all should return all data and clear the buffer."""
    buf = RingBuffer(sample_rate=16000, max_seconds=5)
    buf.write(np.array([1, 2, 3], dtype=np.int16))
    result = buf.read_all()
    assert len(result) == 3

    result2 = buf.read_all()
    assert len(result2) == 0


def test_empty_read():
    """Reading from empty buffer should return empty array."""
    buf = RingBuffer(sample_rate=16000, max_seconds=5)
    result = buf.read_all()
    assert len(result) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd live-translate && python -m pytest tests/test_buffer.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'audio.buffer'`

- [ ] **Step 3: Implement ring buffer**

Create `live-translate/audio/buffer.py`:
```python
import threading
import numpy as np


class RingBuffer:
    """Thread-safe ring buffer for PCM audio samples."""

    def __init__(self, sample_rate: int = 16000, max_seconds: int = 30):
        self._max_samples = sample_rate * max_seconds
        self._buffer = np.zeros(self._max_samples, dtype=np.int16)
        self._write_pos = 0
        self._count = 0
        self._lock = threading.Lock()

    def write(self, samples: np.ndarray):
        """Append samples to the buffer. Discards oldest if full."""
        with self._lock:
            n = len(samples)
            if n >= self._max_samples:
                # Entire buffer is overwritten
                self._buffer[:] = samples[-self._max_samples:]
                self._write_pos = 0
                self._count = self._max_samples
                return

            available = self._max_samples - self._count
            if n > available:
                # Overflow: discard oldest
                overflow = n - available
                self._count -= overflow
                self._write_pos = (self._write_pos + overflow) % self._max_samples

            end = self._write_pos + self._count
            for i in range(n):
                idx = (end + i) % self._max_samples
                self._buffer[idx] = samples[i]
            self._count += n

    def read_all(self) -> np.ndarray:
        """Read all samples and clear the buffer."""
        with self._lock:
            if self._count == 0:
                return np.array([], dtype=np.int16)
            result = np.empty(self._count, dtype=np.int16)
            for i in range(self._count):
                result[i] = self._buffer[(self._write_pos + i) % self._max_samples]
            self._write_pos = 0
            self._count = 0
            return result

    @property
    def count(self) -> int:
        return self._count
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd live-translate && python -m pytest tests/test_buffer.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add live-translate/audio/buffer.py live-translate/tests/test_buffer.py
git commit -m "feat: thread-safe ring buffer for audio samples"
```

---

### Task 3: VAD (Voice Activity Detection)

**Files:**
- Create: `live-translate/audio/vad.py`
- Create: `live-translate/tests/test_vad.py`

- [ ] **Step 1: Write the failing test**

Create `live-translate/tests/test_vad.py`:
```python
import numpy as np
from audio.vad import VADSegmenter


def test_silence_returns_no_segments():
    """Pure silence should produce no speech segments."""
    vad = VADSegmenter(sample_rate=16000, sensitivity=2, silence_threshold_ms=300)
    silence = np.zeros(48000, dtype=np.int16)  # 3 seconds of silence
    segments = vad.process(silence)
    assert len(segments) == 0


def test_speech_then_silence_returns_segment():
    """Speech followed by silence should produce one segment."""
    vad = VADSegmenter(sample_rate=16000, sensitivity=2, silence_threshold_ms=300)
    # Simulate speech: random noise (not pure silence)
    speech = np.random.randint(-3000, 3000, size=16000, dtype=np.int16)
    silence = np.zeros(16000, dtype=np.int16)
    audio = np.concatenate([speech, silence])

    segments = vad.process(audio)
    assert len(segments) >= 1
    # Each segment should be non-empty
    for seg in segments:
        assert len(seg) > 0


def test_multiple_sentences():
    """Two speech bursts separated by silence should produce two segments."""
    vad = VADSegmenter(sample_rate=16000, sensitivity=2, silence_threshold_ms=300)
    speech1 = np.random.randint(-3000, 3000, size=16000, dtype=np.int16)
    silence = np.zeros(16000, dtype=np.int16)
    speech2 = np.random.randint(-3000, 3000, size=16000, dtype=np.int16)
    trailing_silence = np.zeros(16000, dtype=np.int16)
    audio = np.concatenate([speech1, silence, speech2, trailing_silence])

    segments = vad.process(audio)
    assert len(segments) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd live-translate && python -m pytest tests/test_vad.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'audio.vad'`

- [ ] **Step 3: Implement VAD segmenter**

Create `live-translate/audio/vad.py`:
```python
import numpy as np
import webrtcvad


class VADSegmenter:
    """Voice Activity Detection using WebRTC VAD.

    Splits continuous audio into speech segments by detecting silence gaps.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        sensitivity: int = 2,
        silence_threshold_ms: int = 800,
    ):
        self._sample_rate = sample_rate
        self._vad = webrtcvad.Vad(sensitivity)
        self._silence_threshold_ms = silence_threshold_ms
        # WebRTC VAD only supports 10/20/30ms frames at 16kHz
        self._frame_duration_ms = 30
        self._frame_size = int(sample_rate * self._frame_duration_ms / 1000)  # 480 samples
        self._silence_frames = int(silence_threshold_ms / self._frame_duration_ms)
        # State: accumulate speech frames until silence detected
        self._speech_frames: list[np.ndarray] = []
        self._consecutive_silence = 0

    def process(self, audio: np.ndarray) -> list[np.ndarray]:
        """Process audio samples and return completed speech segments.

        Args:
            audio: 16kHz mono 16-bit PCM samples.

        Returns:
            List of speech segments (each is an ndarray of PCM samples).
        """
        segments = []
        num_frames = len(audio) // self._frame_size

        for i in range(num_frames):
            start = i * self._frame_size
            end = start + self._frame_size
            frame = audio[start:end]
            frame_bytes = frame.astype(np.int16).tobytes()

            is_speech = self._vad.is_speech(frame_bytes, self._sample_rate)

            if is_speech:
                self._speech_frames.append(frame.copy())
                self._consecutive_silence = 0
            else:
                if self._speech_frames:
                    self._consecutive_silence += 1
                    if self._consecutive_silence >= self._silence_frames:
                        # End of sentence: flush accumulated speech
                        segment = np.concatenate(self._speech_frames)
                        segments.append(segment)
                        self._speech_frames = []
                        self._consecutive_silence = 0

        return segments

    def flush(self) -> list[np.ndarray]:
        """Flush any remaining speech (call at end of stream)."""
        if self._speech_frames:
            segment = np.concatenate(self._speech_frames)
            self._speech_frames = []
            self._consecutive_silence = 0
            return [segment]
        return []

    def reset(self):
        """Clear internal state."""
        self._speech_frames = []
        self._consecutive_silence = 0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd live-translate && python -m pytest tests/test_vad.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add live-translate/audio/vad.py live-translate/tests/test_vad.py
git commit -m "feat: VAD sentence segmentation with webrtcvad"
```

---

### Task 4: Whisper STT Engine

**Files:**
- Create: `live-translate/stt/whisper_engine.py`
- Create: `live-translate/tests/test_whisper_engine.py`

- [ ] **Step 1: Write the failing test**

Create `live-translate/tests/test_whisper_engine.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd live-translate && python -m pytest tests/test_whisper_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'stt.whisper_engine'`

- [ ] **Step 3: Implement whisper engine**

Create `live-translate/stt/whisper_engine.py`:
```python
import logging
import numpy as np
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd live-translate && python -m pytest tests/test_whisper_engine.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add live-translate/stt/ whisper_engine.py live-translate/tests/test_whisper_engine.py
git commit -m "feat: Whisper STT engine with faster-whisper"
```

---

### Task 5: Argos Translation Engine

**Files:**
- Create: `live-translate/translate/argos_engine.py`
- Create: `live-translate/tests/test_argos_engine.py`

- [ ] **Step 1: Write the failing test**

Create `live-translate/tests/test_argos_engine.py`:
```python
from unittest.mock import MagicMock, patch
from translate.argos_engine import ArgosTranslator


def test_translate_returns_chinese():
    """Should translate English to Chinese."""
    mock_translator = MagicMock()
    mock_translator.translate.return_value = "大家好，让我们开始会议。"

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._translator = mock_translator
    engine._from_lang = "en"
    engine._to_lang = "zh"

    result = engine.translate("Hello everyone, let's start the meeting.")
    assert result == "大家好，让我们开始会议。"
    mock_translator.translate.assert_called_once_with("Hello everyone, let's start the meeting.")


def test_translate_empty_string():
    """Should return empty string for empty input."""
    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._translator = MagicMock()
    engine._from_lang = "en"
    engine._to_lang = "zh"

    result = engine.translate("")
    assert result == ""


def test_translate_strips_whitespace():
    """Should strip whitespace from input before translating."""
    mock_translator = MagicMock()
    mock_translator.translate.return_value = "你好"

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._translator = mock_translator
    engine._from_lang = "en"
    engine._to_lang = "zh"

    result = engine.translate("  Hello  ")
    assert result == "你好"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd live-translate && python -m pytest tests/test_argos_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'translate.argos_engine'`

- [ ] **Step 3: Implement Argos translation engine**

Create `live-translate/translate/argos_engine.py`:
```python
import logging
import argostranslate.package
import argostranslate.translate

logger = logging.getLogger(__name__)


class ArgosTranslator:
    """Offline translation using Argos Translate."""

    def __init__(self, from_lang: str = "en", to_lang: str = "zh"):
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._translator = None
        self._ensure_package_installed()

    def _ensure_package_installed(self):
        """Download and install the translation package if not present."""
        logger.info("Checking for %s → %s translation package...", self._from_lang, self._to_lang)

        # Update package index
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()

        # Find the package we need
        target_package = None
        for pkg in available_packages:
            if pkg.from_code == self._from_lang and pkg.to_code == self._to_lang:
                target_package = pkg
                break

        if target_package is None:
            raise RuntimeError(
                f"Translation package {self._from_lang} → {self._to_lang} not found."
            )

        # Check if already installed
        installed = argostranslate.translate.get_installed_languages()
        installed_codes = {(l.code, l.code) for l in installed}

        # Install if needed
        logger.info("Installing %s → %s package...", self._from_lang, self._to_lang)
        download_path = target_package.download()
        argostranslate.package.install_from_path(download_path)
        logger.info("Translation package installed.")

        # Get the translator
        installed = argostranslate.translate.get_installed_languages()
        from_lang = next((l for l in installed if l.code == self._from_lang), None)
        to_lang = next((l for l in installed if l.code == self._to_lang), None)

        if from_lang is None or to_lang is None:
            raise RuntimeError("Failed to load installed languages.")

        self._translator = from_lang.get_translation(to_lang)
        logger.info("Translator ready: %s → %s", self._from_lang, self._to_lang)

    def translate(self, text: str) -> str:
        """Translate English text to Chinese.

        Args:
            text: English text to translate.

        Returns:
            Chinese translation, or empty string for empty input.
        """
        text = text.strip()
        if not text:
            return ""
        return self._translator.translate(text)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd live-translate && python -m pytest tests/test_argos_engine.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add live-translate/translate/argos_engine.py live-translate/tests/test_argos_engine.py
git commit -m "feat: Argos offline translation engine (en → zh)"
```

---

### Task 6: Audio Capture (WASAPI Loopback)

**Files:**
- Create: `live-translate/audio/capture.py`

Note: This module depends on `pyaudiowpatch` which is Windows-only. Tests require a Windows environment with audio output.

- [ ] **Step 1: Implement audio capture thread**

Create `live-translate/audio/capture.py`:
```python
import logging
import threading
import numpy as np

logger = logging.getLogger(__name__)

# pyaudiowpatch is Windows-only (WASAPI support)
try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.warning("pyaudiowpatch not available. Audio capture disabled.")


class AudioCapture:
    """Captures system audio output via WASAPI Loopback.

    Runs in a dedicated thread, writing 16kHz mono PCM samples
    to the provided ring buffer.
    """

    def __init__(self, buffer, target_sample_rate: int = 16000):
        self._buffer = buffer
        self._target_sample_rate = target_sample_rate
        self._running = False
        self._thread: threading.Thread | None = None
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None

    def _find_loopback_device(self) -> dict:
        """Find the default WASAPI loopback device."""
        if not HAS_PYAUDIO:
            raise RuntimeError("pyaudiowpatch not installed.")

        self._pa = pyaudio.PyAudio()

        try:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            raise RuntimeError("WASAPI not available on this system.")

        default_speakers = self._pa.get_device_info_by_index(
            wasapi_info["defaultOutputDevice"]
        )

        if not default_speakers.get("isLoopbackDevice", False):
            # Try to find the loopback counterpart
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice", False):
                    return dev
            raise RuntimeError("No loopback device found. Ensure speakers are enabled.")

        return default_speakers

    def _resample(self, audio: np.ndarray, src_rate: int, channels: int) -> np.ndarray:
        """Resample audio to target sample rate and convert to mono."""
        # Convert to mono if stereo
        if channels == 2:
            audio = audio.reshape(-1, 2)
            audio = audio.mean(axis=1).astype(np.int16)
        elif channels > 2:
            audio = audio.reshape(-1, channels)
            audio = audio[:, :2].mean(axis=1).astype(np.int16)

        # Simple resampling (linear interpolation)
        if src_rate != self._target_sample_rate:
            duration = len(audio) / src_rate
            target_len = int(duration * self._target_sample_rate)
            indices = np.linspace(0, len(audio) - 1, target_len).astype(int)
            audio = audio[indices]

        return audio

    def _capture_loop(self, device_info: dict):
        """Main capture loop running in background thread."""
        sample_rate = int(device_info["defaultSampleRate"])
        channels = int(device_info["maxInputChannels"])

        try:
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_info["index"],
                frames_per_buffer=4096,
            )

            logger.info(
                "Audio capture started: %dHz, %d channels",
                sample_rate,
                channels,
            )

            while self._running:
                try:
                    data = self._stream.read(4096, exception_on_overflow=False)
                    audio = np.frombuffer(data, dtype=np.int16)
                    mono = self._resample(audio, sample_rate, channels)
                    self._buffer.write(mono)
                except Exception as e:
                    logger.error("Audio capture error: %s", e)

        except Exception as e:
            logger.error("Failed to open audio stream: %s", e)
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None

    def start(self):
        """Start capturing system audio in a background thread."""
        if self._running:
            return

        device_info = self._find_loopback_device()
        logger.info("Loopback device: %s", device_info["name"])

        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, args=(device_info,), daemon=True
        )
        self._thread.start()

    def stop(self):
        """Stop capturing audio."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if self._pa:
            self._pa.terminate()
            self._pa = None
        logger.info("Audio capture stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
```

- [ ] **Step 2: Commit**

```bash
git add live-translate/audio/capture.py
git commit -m "feat: WASAPI loopback audio capture with resampling"
```

---

### Task 7: Floating Window UI

**Files:**
- Create: `live-translate/ui/floating_window.py`

- [ ] **Step 1: Implement the floating window**

Create `live-translate/ui/floating_window.py`:
```python
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
            | Qt.Tool  # Hide from taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(self._config.opacity)

        # Restore position
        if self._config.window_x is not None:
            self.move(self._config.window_x, self._config.window_y)
        self.resize(self._config.window_width, self._config.window_height)

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title bar (draggable)
        title_bar = QHBoxLayout()
        title_label = QLabel("⏺ Live Translate")
        title_label.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        layout.addLayout(title_bar)

        # Content area
        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(6)
        layout.addLayout(self._content_layout)

        # Placeholder for empty state
        self._placeholder = QLabel("等待音频...")
        self._placeholder.setStyleSheet("color: #aaaaaa; font-size: 14px;")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(self._placeholder)

        layout.addStretch()

        # Control bar
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

        # Dark background with rounded corners
        self.setStyleSheet("""
            FloatingWindow {
                background-color: rgba(30, 30, 30, 230);
                border-radius: 10px;
            }
        """)

        # Drop shadow
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

    # -- Dragging --

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

    # -- Slots --

    @pyqtSlot(str, str)
    def add_translation(self, english: str, chinese: str):
        """Add a new translation result to the display."""
        if self._is_paused:
            return

        self._items.append({"english": english, "chinese": chinese})

        # Keep only last N items
        while len(self._items) > self._config.max_display_items:
            self._items.pop(0)

        self._refresh_display()

    def _refresh_display(self):
        """Rebuild the content area with current items."""
        # Clear existing items
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._placeholder.setParent(None)

        for entry in reversed(self._items):  # Newest first
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

            # Separator
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
        """Show a loading message in the content area."""
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
        """Save window position on close."""
        self._config.window_x = self.x()
        self._config.window_y = self.y()
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.save()
        event.accept()
```

- [ ] **Step 2: Commit**

```bash
git add live-translate/ui/floating_window.py
git commit -m "feat: floating window UI with always-on-top and drag support"
```

---

### Task 8: Settings Dialog

**Files:**
- Create: `live-translate/ui/settings_dialog.py`

- [ ] **Step 1: Implement settings dialog**

Create `live-translate/ui/settings_dialog.py`:
```python
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QSpinBox, QPushButton,
    QGroupBox, QFormLayout,
)


class SettingsDialog(QDialog):
    """Settings panel for configuring the translation app."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("设置")
        self.setFixedSize(350, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout()

        # -- Whisper Model --
        model_group = QGroupBox("语音识别模型")
        model_layout = QFormLayout()
        self._model_combo = QComboBox()
        self._model_combo.addItems(["tiny", "base", "small"])
        self._model_combo.setCurrentText(self._config.whisper_model)
        model_layout.addRow("模型:", self._model_combo)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # -- Display --
        display_group = QGroupBox("显示设置")
        display_layout = QFormLayout()

        # Opacity
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(30, 90)
        self._opacity_slider.setValue(int(self._config.opacity * 100))
        self._opacity_label = QLabel(f"{int(self._config.opacity * 100)}%")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        display_layout.addRow("透明度:", opacity_row)

        # Font size
        self._font_spin = QSpinBox()
        self._font_spin.setRange(10, 24)
        self._font_spin.setValue(self._config.font_size)
        display_layout.addRow("字体大小:", self._font_spin)

        # Max display items
        self._items_spin = QSpinBox()
        self._items_spin.setRange(1, 10)
        self._items_spin.setValue(self._config.max_display_items)
        display_layout.addRow("显示条数:", self._items_spin)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # -- VAD --
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

        vad_group.setLayout(vad_layout)
        layout.addWidget(vad_group)

        layout.addStretch()

        # Buttons
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
        self._config.max_display_items = self._items_spin.value()
        self._config.vad_sensitivity = self._sensitivity_combo.currentIndex()
        self._config.silence_threshold_ms = self._silence_spin.value()
        self._config.save()
        self.accept()
```

- [ ] **Step 2: Commit**

```bash
git add live-translate/ui/settings_dialog.py
git commit -m "feat: settings dialog with model, display, and VAD configuration"
```

---

### Task 9: System Tray Icon

**Files:**
- Create: `live-translate/ui/tray_icon.py`

- [ ] **Step 1: Implement system tray**

Create `live-translate/ui/tray_icon.py`:
```python
import os
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction


class TrayIcon(QSystemTrayIcon):
    """System tray icon with context menu."""

    show_window = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Load icon or use default
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon.fromTheme("audio-input-microphone"))

        self.setToolTip("Live Translate - 实时翻译")

        # Context menu
        menu = QMenu()

        show_action = QAction("显示窗口", menu)
        show_action.triggered.connect(self.show_window.emit)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # Double-click to show window
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window.emit()
```

- [ ] **Step 2: Commit**

```bash
git add live-translate/ui/tray_icon.py
git commit -m "feat: system tray icon with show/quit menu"
```

---

### Task 10: Processing Pipeline

**Files:**
- Create: `live-translate/pipeline.py`

- [ ] **Step 1: Implement the processing pipeline**

Create `live-translate/pipeline.py`:
```python
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
    """Wires VAD → STT → Translate into a processing loop.

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
        )
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        logger.info("Processing pipeline started.")

    def stop(self):
        """Stop the processing pipeline."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        # Flush any remaining speech from VAD
        if self._vad:
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
        """Main processing loop: buffer → VAD → STT → translate → signal."""
        import time

        while self._running:
            # Read audio from buffer
            audio = self._buffer.read_all()

            if len(audio) == 0:
                time.sleep(0.1)  # 100ms polling
                continue

            # VAD: detect sentence boundaries
            segments = self._vad.process(audio)

            for segment in segments:
                if not self._running:
                    break

                # Skip very short segments (< 0.5s)
                if len(segment) < 8000:
                    continue

                try:
                    # STT: transcribe English
                    self._signals.status_changed.emit("识别中...")
                    english_text = self._whisper.transcribe(segment)

                    if not english_text:
                        continue

                    # Translate to Chinese
                    self._signals.status_changed.emit("翻译中...")
                    chinese_text = self._translator.translate(english_text)

                    if not chinese_text:
                        continue

                    # Emit result
                    self._signals.translation_ready.emit(english_text, chinese_text)
                    logger.info("EN: %s → ZH: %s", english_text, chinese_text)

                except Exception as e:
                    logger.error("Pipeline error: %s", e)
                    self._signals.status_changed.emit(f"错误: {e}")

            time.sleep(0.05)

    @property
    def is_running(self) -> bool:
        return self._running
```

- [ ] **Step 2: Commit**

```bash
git add live-translate/pipeline.py
git commit -m "feat: processing pipeline (VAD → STT → translate → signal)"
```

---

### Task 11: Main Entry Point

**Files:**
- Create: `live-translate/main.py`

- [ ] **Step 1: Implement main.py**

Create `live-translate/main.py`:
```python
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
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # UI
    window = FloatingWindow(config)
    tray = TrayIcon()

    # Settings dialog callback
    def show_settings():
        dialog = SettingsDialog(config, parent=window)
        if dialog.exec_():
            # Apply changes that take effect immediately
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
```

- [ ] **Step 2: Commit**

```bash
git add live-translate/main.py
git commit -m "feat: main entry point with full pipeline integration"
```

---

### Task 12: Integration Testing on Windows

**Files:**
- None (manual testing checklist)

- [ ] **Step 1: Install dependencies on Windows**

```bash
cd live-translate
pip install -r requirements.txt
```

- [ ] **Step 2: Run unit tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 3: Launch the app**

```bash
python main.py
```

Verify:
- [ ] Floating window appears, always on top
- [ ] Window is draggable
- [ ] "开始" button starts audio capture
- [ ] Playing English audio (YouTube, Teams) triggers recognition
- [ ] English text and Chinese translation appear in window
- [ ] "暂停" button stops translation
- [ ] Settings dialog opens and saves correctly
- [ ] Closing window minimizes to tray
- [ ] Tray "退出" quits the app

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "chore: integration tested and ready for use"
```
