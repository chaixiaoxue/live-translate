import logging
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BUNDLED_PACKAGE_DIR = _PROJECT_ROOT / "vendor" / "argos-packages"
os.environ.setdefault("XDG_DATA_HOME", str(_PROJECT_ROOT / ".local-data"))
os.environ.setdefault("XDG_CONFIG_HOME", str(_PROJECT_ROOT / ".config-data"))
os.environ.setdefault("XDG_CACHE_HOME", str(_PROJECT_ROOT / ".cache-data"))
os.environ.setdefault("HF_HOME", str(_PROJECT_ROOT / ".cache-data" / "huggingface"))

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
        """Load translation package, installing bundled copy only when needed."""
        logger.info(
            "Checking for %s -> %s translation package...",
            self._from_lang,
            self._to_lang,
        )

        if self._load_installed_translator():
            logger.info("Using installed %s -> %s package.", self._from_lang, self._to_lang)
            return

        bundled_package = self._find_bundled_package()
        if bundled_package is not None:
            logger.info("Installing bundled package: %s", bundled_package)
            argostranslate.package.install_from_path(str(bundled_package))
        else:
            logger.warning(
                "Bundled %s -> %s package not found; downloading package index.",
                self._from_lang,
                self._to_lang,
            )
            self._download_and_install_package()

        if not self._load_installed_translator():
            raise RuntimeError("Failed to load installed languages.")

        logger.info("Translator ready: %s -> %s", self._from_lang, self._to_lang)

    def _load_installed_translator(self) -> bool:
        installed = argostranslate.translate.get_installed_languages()
        from_lang = next((l for l in installed if l.code == self._from_lang), None)
        to_lang = next((l for l in installed if l.code == self._to_lang), None)

        if from_lang is None or to_lang is None:
            return False

        self._translator = from_lang.get_translation(to_lang)
        return self._translator is not None

    def _find_bundled_package(self) -> Path | None:
        if not _BUNDLED_PACKAGE_DIR.exists():
            return None

        candidates = sorted(
            _BUNDLED_PACKAGE_DIR.glob(
                f"translate-{self._from_lang}_{self._to_lang}*.argosmodel"
            )
        )
        return candidates[0] if candidates else None

    def _download_and_install_package(self):
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()

        target_package = None
        for pkg in available_packages:
            if pkg.from_code == self._from_lang and pkg.to_code == self._to_lang:
                target_package = pkg
                break

        if target_package is None:
            raise RuntimeError(
                f"Translation package {self._from_lang} -> {self._to_lang} not found."
            )

        logger.info("Downloading %s -> %s package...", self._from_lang, self._to_lang)
        download_path = target_package.download()
        argostranslate.package.install_from_path(download_path)
        logger.info("Translation package installed.")

    def translate(self, text: str) -> str:
        """Translate English text to Chinese."""
        text = text.strip()
        if not text:
            return ""
        return self._translator.translate(text)
