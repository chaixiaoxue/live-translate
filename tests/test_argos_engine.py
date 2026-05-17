from pathlib import Path
from unittest.mock import MagicMock, patch

from translate.argos_engine import ArgosTranslator


class FakeLanguage:
    def __init__(self, code: str, translator=None):
        self.code = code
        self._translator = translator

    def get_translation(self, to_lang):
        return self._translator


def test_translate_returns_chinese():
    """Should translate English to Chinese."""
    mock_translator = MagicMock()
    mock_translator.translate.return_value = "translated text"

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._translator = mock_translator
    engine._from_lang = "en"
    engine._to_lang = "zh"

    result = engine.translate("Hello everyone, let's start the meeting.")
    assert result == "translated text"
    mock_translator.translate.assert_called_once_with(
        "Hello everyone, let's start the meeting."
    )


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
    mock_translator.translate.return_value = "hello"

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._translator = mock_translator
    engine._from_lang = "en"
    engine._to_lang = "zh"

    result = engine.translate("  Hello  ")
    assert result == "hello"


def test_uses_installed_package_without_download():
    """Should not update/download when the language pair is already installed."""
    translator = MagicMock()
    languages = [FakeLanguage("en", translator), FakeLanguage("zh")]

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._from_lang = "en"
    engine._to_lang = "zh"
    engine._translator = None

    with (
        patch(
            "translate.argos_engine.argostranslate.translate.get_installed_languages",
            return_value=languages,
        ),
        patch(
            "translate.argos_engine.argostranslate.package.update_package_index"
        ) as update_index,
        patch("translate.argos_engine.argostranslate.package.install_from_path") as install,
    ):
        engine._ensure_package_installed()

    assert engine._translator is translator
    update_index.assert_not_called()
    install.assert_not_called()


def test_installs_bundled_package_before_downloading():
    """Should install the checked-in package when the language pair is missing."""
    translator = MagicMock()
    languages_after_install = [FakeLanguage("en", translator), FakeLanguage("zh")]

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._from_lang = "en"
    engine._to_lang = "zh"
    engine._translator = None

    with (
        patch(
            "translate.argos_engine.argostranslate.translate.get_installed_languages",
            side_effect=[[], languages_after_install],
        ),
        patch.object(
            engine,
            "_find_bundled_package",
            return_value=Path("vendor/argos-packages/translate-en_zh.argosmodel"),
        ),
        patch(
            "translate.argos_engine.argostranslate.package.update_package_index"
        ) as update_index,
        patch("translate.argos_engine.argostranslate.package.install_from_path") as install,
    ):
        engine._ensure_package_installed()

    assert engine._translator is translator
    install.assert_called_once_with("vendor\\argos-packages\\translate-en_zh.argosmodel")
    update_index.assert_not_called()
