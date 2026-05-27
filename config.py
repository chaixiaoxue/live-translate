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
        "silence_threshold_ms": 350,
        "max_segment_seconds": 10.0,
        "audio_device_name": None,
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
