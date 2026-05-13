import logging
import threading
import numpy as np

logger = logging.getLogger(__name__)

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
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice", False):
                    return dev
            raise RuntimeError("No loopback device found. Ensure speakers are enabled.")

        return default_speakers

    def _resample(self, audio: np.ndarray, src_rate: int, channels: int) -> np.ndarray:
        """Resample audio to target sample rate and convert to mono."""
        if channels == 2:
            audio = audio.reshape(-1, 2)
            audio = audio.mean(axis=1).astype(np.int16)
        elif channels > 2:
            audio = audio.reshape(-1, channels)
            audio = audio[:, :2].mean(axis=1).astype(np.int16)

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

            logger.info("Audio capture started: %dHz, %d channels", sample_rate, channels)

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
