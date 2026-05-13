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
                self._buffer[:] = samples[-self._max_samples:]
                self._write_pos = 0
                self._count = self._max_samples
                return

            available = self._max_samples - self._count
            if n > available:
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
