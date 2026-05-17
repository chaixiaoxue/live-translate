import logging
import os
import re
import zipfile
from types import SimpleNamespace
from pathlib import Path

from app_paths import app_dir, bundled_dir

_APP_DIR = app_dir()
_BUNDLED_DIR = bundled_dir()
_BUNDLED_PACKAGE_DIRS = (
    _APP_DIR / "vendor" / "argos-packages",
    _BUNDLED_DIR / "vendor" / "argos-packages",
)
os.environ.setdefault("XDG_DATA_HOME", str(_APP_DIR / ".local-data"))
os.environ.setdefault("XDG_CONFIG_HOME", str(_APP_DIR / ".config-data"))
os.environ.setdefault("XDG_CACHE_HOME", str(_APP_DIR / ".cache-data"))
os.environ.setdefault("HF_HOME", str(_APP_DIR / ".cache-data" / "huggingface"))
os.environ.setdefault("ARGOS_CHUNK_TYPE", "MINISBD")
os.environ.setdefault("ARGOS_STANZA_AVAILABLE", "false")

logger = logging.getLogger(__name__)
argostranslate = SimpleNamespace(package=None, translate=None)


class ArgosTranslator:
    """Offline translation using Argos Translate."""

    def __init__(self, from_lang: str = "en", to_lang: str = "zh"):
        self._from_lang = from_lang
        self._to_lang = to_lang
        self._translator = None
        logger.info("Importing Argos Translate runtime.")
        self._package_module = self._get_package_module()
        self._ensure_package_installed()

    def _get_package_module(self):
        package_module = getattr(self, "_package_module", None)
        if package_module is not None:
            return package_module
        if argostranslate.package is None:
            import argostranslate.package as package_module

            argostranslate.package = package_module
        return argostranslate.package

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
            self._install_from_path_without_translate_import(bundled_package)
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
        installed = self._get_package_module().get_installed_packages()
        package = next(
            (
                pkg
                for pkg in installed
                if pkg.type == "translate"
                and pkg.from_code == self._from_lang
                and pkg.to_code == self._to_lang
            ),
            None,
        )
        if package is None:
            return False

        self._translator = _DirectPackageTranslator(package)
        return True

    def _find_bundled_package(self) -> Path | None:
        for package_dir in _BUNDLED_PACKAGE_DIRS:
            if not package_dir.exists():
                continue
            candidates = sorted(
                package_dir.glob(
                    f"translate-{self._from_lang}_{self._to_lang}*.argosmodel"
                )
            )
            if candidates:
                return candidates[0]
        return None

    def _download_and_install_package(self):
        package_module = self._get_package_module()
        package_module.update_package_index()
        available_packages = package_module.get_available_packages()

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
        package_module.install_from_path(download_path)
        logger.info("Translation package installed.")

    def _install_from_path_without_translate_import(self, path: Path):
        from argostranslate import settings

        if not zipfile.is_zipfile(path):
            raise RuntimeError(f"Not a valid Argos model: {path}")
        settings.package_data_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "r") as zipf:
            zipf.extractall(path=settings.package_data_dir)

    def translate(self, text: str) -> str:
        """Translate English text to Chinese."""
        text = text.strip()
        if not text:
            return ""
        return self._translator.translate(text)


class _DirectPackageTranslator:
    """Translate with an installed Argos package without SBD side dependencies."""

    def __init__(self, package):
        import ctranslate2
        from argostranslate import settings

        self._package = package
        model_path = str(package.package_path / "model")
        self._translator = ctranslate2.Translator(
            model_path,
            device=settings.device,
            inter_threads=settings.inter_threads,
            intra_threads=settings.intra_threads,
            compute_type=settings.compute_type,
        )

    def translate(self, text: str) -> str:
        sentences = _split_sentences(text)
        tokenized = [self._package.tokenizer.encode(sentence) for sentence in sentences]
        if not tokenized:
            return ""

        target_prefix = getattr(self._package, "target_prefix", "")
        prefix_batches = [[target_prefix]] * len(tokenized) if target_prefix else None
        translated_batches = self._translator.translate_batch(
            tokenized,
            target_prefix=prefix_batches,
            replace_unknowns=True,
            max_batch_size=32,
            batch_type="tokens",
            beam_size=4,
            num_hypotheses=1,
            length_penalty=0.2,
        )

        translated_tokens = []
        for translated_batch in translated_batches:
            translated_tokens.extend(translated_batch.hypotheses[0])

        value = self._package.tokenizer.decode(translated_tokens)
        if target_prefix and value.startswith(target_prefix):
            value = value[len(target_prefix) :]
        return value.lstrip()


def _split_sentences(text: str) -> list[str]:
    sentences = [
        match.group(0).strip()
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text)
        if match.group(0).strip()
    ]
    return sentences or [text]
