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
