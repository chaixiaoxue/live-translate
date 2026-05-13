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
    speech = np.random.randint(-3000, 3000, size=16000, dtype=np.int16)
    silence = np.zeros(16000, dtype=np.int16)
    audio = np.concatenate([speech, silence])

    segments = vad.process(audio)
    assert len(segments) >= 1
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
