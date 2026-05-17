from pathlib import Path
from unittest.mock import MagicMock, patch

from translate.argos_engine import ArgosTranslator


class FakeLanguage:
    def __init__(self, code: str, translator=None):
        self.code = code
        self._translator = translator

    def get_translation(self, to_lang):
        return self._translator


class FakePackage:
    type = "translate"
    from_code = "en"
    to_code = "zh"


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

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._from_lang = "en"
    engine._to_lang = "zh"
    engine._translator = None
    engine._package_module = MagicMock()
    engine._package_module.get_installed_packages.return_value = [FakePackage()]

    with patch("translate.argos_engine._DirectPackageTranslator", return_value=translator):
        engine._ensure_package_installed()

    assert engine._translator is translator
    engine._package_module.update_package_index.assert_not_called()
    engine._package_module.install_from_path.assert_not_called()


def test_installs_bundled_package_before_downloading():
    """Should install the checked-in package when the language pair is missing."""
    translator = MagicMock()

    engine = ArgosTranslator.__new__(ArgosTranslator)
    engine._from_lang = "en"
    engine._to_lang = "zh"
    engine._translator = None
    engine._package_module = MagicMock()
    engine._package_module.get_installed_packages.side_effect = [
        [],
        [FakePackage()],
    ]

    with (
        patch("translate.argos_engine._DirectPackageTranslator", return_value=translator),
        patch.object(
            engine,
            "_find_bundled_package",
            return_value=Path("vendor/argos-packages/translate-en_zh.argosmodel"),
        ),
        patch.object(engine, "_install_from_path_without_translate_import") as install,
    ):
        engine._ensure_package_installed()

    assert engine._translator is translator
    install.assert_called_once_with(
        Path("vendor/argos-packages/translate-en_zh.argosmodel")
    )
    engine._package_module.update_package_index.assert_not_called()
