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
