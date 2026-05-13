import logging
import argostranslate.package
import argostranslate.translate

logger = logging.getLogger(__name__)


class ArgosTranslator:
    """Offline translation using Argos Translate."""

    def __init__(self, from_lang: str = "en", to_lang: str = "zh"):
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._translator = None
        self._ensure_package_installed()

    def _ensure_package_installed(self):
        """Download and install the translation package if not present."""
        logger.info("Checking for %s → %s translation package...", self._from_lang, self._to_lang)

        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()

        target_package = None
        for pkg in available_packages:
            if pkg.from_code == self._from_lang and pkg.to_code == self._to_lang:
                target_package = pkg
                break

        if target_package is None:
            raise RuntimeError(
                f"Translation package {self._from_lang} → {self._to_lang} not found."
            )

        logger.info("Installing %s → %s package...", self._from_lang, self._to_lang)
        download_path = target_package.download()
        argostranslate.package.install_from_path(download_path)
        logger.info("Translation package installed.")

        installed = argostranslate.translate.get_installed_languages()
        from_lang = next((l for l in installed if l.code == self._from_lang), None)
        to_lang = next((l for l in installed if l.code == self._to_lang), None)

        if from_lang is None or to_lang is None:
            raise RuntimeError("Failed to load installed languages.")

        self._translator = from_lang.get_translation(to_lang)
        logger.info("Translator ready: %s → %s", self._from_lang, self._to_lang)

    def translate(self, text: str) -> str:
        """Translate English text to Chinese."""
        text = text.strip()
        if not text:
            return ""
        return self._translator.translate(text)
