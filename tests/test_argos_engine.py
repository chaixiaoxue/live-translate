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
