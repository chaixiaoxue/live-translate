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

    def __init__(
        self,
        buffer,
        target_sample_rate: int = 16000,
        device_name: str | None = None,
    ):
        self._buffer = buffer
        self._target_sample_rate = target_sample_rate
        self._device_name = device_name
        self._running = False
        self._thread: threading.Thread | None = None
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._state_lock = threading.Lock()

    def _find_loopback_device(self) -> dict:
        """Find the default WASAPI loopback device."""
        if not HAS_PYAUDIO:
            raise RuntimeError("pyaudiowpatch not installed.")

        if self._pa is None:
            self._pa = pyaudio.PyAudio()

        try:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            raise RuntimeError("WASAPI not available on this system.")

        if self._device_name:
            selected_name = self._normalize_device_name(self._device_name)
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if not dev.get("isLoopbackDevice", False):
                    continue
                loopback_name = self._normalize_device_name(dev["name"])
                if selected_name in loopback_name or loopback_name in selected_name:
                    return dev
            logger.warning(
                "Configured audio device not found: %s. Falling back to default.",
                self._device_name,
            )

        default_speakers = self._pa.get_device_info_by_index(
            wasapi_info["defaultOutputDevice"]
        )

        if not default_speakers.get("isLoopbackDevice", False):
            default_name = self._normalize_device_name(default_speakers["name"])
            fallback = None
            for i in range(self._pa.get_device_count()):
                dev = self._pa.get_device_info_by_index(i)
                if dev.get("isLoopbackDevice", False):
                    if fallback is None:
                        fallback = dev
                    loopback_name = self._normalize_device_name(dev["name"])
                    if default_name and default_name in loopback_name:
                        return dev
            if fallback is not None:
                logger.warning(
                    "Default output loopback not found for %s; using %s",
                    default_speakers["name"],
                    fallback["name"],
                )
                return fallback
            raise RuntimeError("No loopback device found. Ensure speakers are enabled.")

        return default_speakers

    def _normalize_device_name(self, name: str) -> str:
        return (
            name.replace("[Loopback]", "")
            .replace("（", "(")
            .replace("）", ")")
            .strip()
            .lower()
        )

    @staticmethod
    def list_loopback_devices() -> list[dict]:
        """Return available WASAPI loopback devices for settings UI."""
        if not HAS_PYAUDIO:
            return []

        pa = pyaudio.PyAudio()
        try:
            devices = []
            try:
                wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            except OSError:
                return []
            for i in range(pa.get_device_count()):
                dev = pa.get_device_info_by_index(i)
                if dev.get("hostApi") == wasapi_info["index"] and dev.get(
                    "isLoopbackDevice", False
                ):
                    devices.append(
                        {
                            "index": dev["index"],
                            "name": dev["name"],
                            "defaultSampleRate": dev["defaultSampleRate"],
                            "maxInputChannels": dev["maxInputChannels"],
                        }
                    )
            return devices
        finally:
            pa.terminate()

    def set_device_name(self, device_name: str | None):
        if self._running:
            raise RuntimeError("Cannot change audio device while listening.")
        self._device_name = device_name

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
            stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_info["index"],
                frames_per_buffer=4096,
            )
            with self._state_lock:
                self._stream = stream

            logger.info("Audio capture started: %dHz, %d channels", sample_rate, channels)

            while self._running:
                try:
                    data = stream.read(4096, exception_on_overflow=False)
                    audio = np.frombuffer(data, dtype=np.int16)
                    mono = self._resample(audio, sample_rate, channels)
                    self._buffer.write(mono)
                except Exception as e:
                    if self._running:
                        logger.error("Audio capture error: %s", e)

        except Exception as e:
            logger.error("Failed to open audio stream: %s", e)
        finally:
            with self._state_lock:
                stream = self._stream
                self._stream = None
            if stream:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                except Exception as e:
                    logger.debug("Ignoring audio stream stop error: %s", e)
                try:
                    stream.close()
                except Exception as e:
                    logger.debug("Ignoring audio stream close error: %s", e)

    def start(self):
        """Start capturing system audio in a background thread."""
        if self._running:
            return
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Audio capture is still stopping. Please try again.")
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
        with self._state_lock:
            stream = self._stream
        if stream:
            try:
                if stream.is_active():
                    stream.stop_stream()
            except Exception as e:
                logger.debug("Ignoring audio stream interrupt error: %s", e)
        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("Audio capture thread did not stop within timeout.")
                return
            self._thread = None
        logger.info("Audio capture stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
