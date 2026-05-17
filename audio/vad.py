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
        max_segment_seconds: float = 4.0,
    ):
        self._sample_rate = sample_rate
        self._vad = webrtcvad.Vad(sensitivity)
        self._silence_threshold_ms = silence_threshold_ms
        self._frame_duration_ms = 30
        self._frame_size = int(sample_rate * self._frame_duration_ms / 1000)  # 480 samples
        self._silence_frames = max(1, int(silence_threshold_ms / self._frame_duration_ms))
        self._max_speech_frames = max(
            1, int(max_segment_seconds * 1000 / self._frame_duration_ms)
        )
        self._speech_frames: list[np.ndarray] = []
        self._consecutive_silence = 0

    def process(self, audio: np.ndarray) -> list[np.ndarray]:
        """Process audio samples and return completed speech segments."""
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
                if len(self._speech_frames) >= self._max_speech_frames:
                    segment = np.concatenate(self._speech_frames)
                    segments.append(segment)
                    self._speech_frames = []
                    self._consecutive_silence = 0
            else:
                if self._speech_frames:
                    self._consecutive_silence += 1
                    if self._consecutive_silence >= self._silence_frames:
                        segment = np.concatenate(self._speech_frames)
                        segments.append(segment)
                        self._speech_frames = []
                        self._consecutive_silence = 0

        return segments

    def flush(self) -> list[np.ndarray]:
        """Flush any remaining speech."""
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
