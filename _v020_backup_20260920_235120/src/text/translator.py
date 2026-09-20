import json
import re
from collections import OrderedDict
from pathlib import Path
from time import perf_counter

import ctranslate2
import sentencepiece as spm

from src.utils.paths import resource_path


MODEL_DIR = Path(resource_path(
    "models/opus-mt-ru-en-ct2-int8"
))

GLOSSARY_FILE = Path(resource_path(
    "data/dota_translation_glossary.json"
))

PHRASES_FILE = Path(resource_path(
    "data/dota_translation_phrases.json"
))

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_SPACE_RE = re.compile(r"\s+")
_PUNCT_SPACE_RE = re.compile(r"\s+([,.!?;:])")


class EnglishTranslator:
    """
    Fast local RU -> EN translator tuned for short Dota 2 chat messages.

    Pipeline:
      exact Dota phrase -> glossary normalization -> OPUS-MT -> post-fixes -> cache
    """

    CACHE_SIZE = 256

    def __init__(self):
        required_files = (
            "model.bin",
            "config.json",
            "source.spm",
            "target.spm",
        )

        missing = [
            name
            for name in required_files
            if not (MODEL_DIR / name).exists()
        ]

        if missing:
            raise FileNotFoundError(
                "Не установлена модель перевода RU → EN. "
                "Запустите INSTALL_TRANSLATION.ps1. "
                "Не найдены: " + ", ".join(missing)
            )

        print("🌐 Загрузка RU → EN переводчика...")

        self.translator = ctranslate2.Translator(
            str(MODEL_DIR),
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=4,
        )

        self.source_sp = spm.SentencePieceProcessor(
            model_file=str(MODEL_DIR / "source.spm")
        )
        self.target_sp = spm.SentencePieceProcessor(
            model_file=str(MODEL_DIR / "target.spm")
        )

        self.glossary = self._load_json(GLOSSARY_FILE, {})
        rules = self._load_json(PHRASES_FILE, {})

        self.exact_phrases = {
            self._phrase_key(k): v
            for k, v in rules.get("exact", {}).items()
        }
        self.pre_phrases = rules.get("pre_replace", {})
        self.post_phrases = rules.get("post_replace", {})

        # Longer terms first, so "сентри варды" wins over "варды".
        self.glossary_items = sorted(
            self.glossary.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        self.pre_phrase_items = sorted(
            self.pre_phrases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        self.post_phrase_items = sorted(
            self.post_phrases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        self._cache = OrderedDict()

        # Warm-up: first real message should not pay model startup cost.
        self.translate("Поставьте варды.")

        print("✅ RU → EN переводчик готов.")

    @staticmethod
    def _load_json(path: Path, default):
        if not path.exists():
            return default

        try:
            return json.loads(
                path.read_text(encoding="utf-8-sig")
            )
        except Exception as exc:
            print(f"⚠ Не удалось загрузить {path.name}: {exc}")
            return default

    @staticmethod
    def _phrase_key(text: str) -> str:
        text = text.strip().lower().replace("ё", "е")
        text = re.sub(r"[.!?,;:]+$", "", text)
        text = _SPACE_RE.sub(" ", text)
        return text

    @staticmethod
    def _cleanup(text: str) -> str:
        text = text.strip()
        text = _PUNCT_SPACE_RE.sub(r"\1", text)
        text = _SPACE_RE.sub(" ", text)

        # Common decoder artifacts.
        text = text.replace(" n't", "n't")
        text = text.replace(" 's", "'s")
        text = text.replace(" 're", "'re")
        text = text.replace(" 'm", "'m")
        text = text.replace(" 've", "'ve")
        text = text.replace(" 'll", "'ll")

        if text:
            text = text[0].upper() + text[1:]

        return text

    def _cache_get(self, key: str):
        value = self._cache.pop(key, None)
        if value is not None:
            self._cache[key] = value
        return value

    def _cache_put(self, key: str, value: str):
        if key in self._cache:
            self._cache.pop(key)

        self._cache[key] = value

        while len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)

    def _replace_case_insensitive(
        self,
        text: str,
        replacements,
    ) -> str:
        result = text

        for source, target in replacements:
            pattern = (
                r"(?<!\w)"
                + re.escape(source)
                + r"(?!\w)"
            )
            result = re.sub(
                pattern,
                target,
                result,
                flags=re.IGNORECASE,
            )

        return result

    def _prepare(self, text: str) -> str:
        # First replace multi-word tactical phrases, then individual terms.
        result = self._replace_case_insensitive(
            text,
            self.pre_phrase_items,
        )
        result = self._replace_case_insensitive(
            result,
            self.glossary_items,
        )
        return result

    def _post_fix(self, text: str) -> str:
        result = text

        for source, target in self.post_phrase_items:
            result = re.sub(
                re.escape(source),
                target,
                result,
                flags=re.IGNORECASE,
            )

        return result

    def translate(
        self,
        text: str,
    ) -> tuple[str, float]:
        started = perf_counter()

        text = text.strip()
        if not text:
            return "", 0.0

        cache_key = text
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached, perf_counter() - started

        # If the result is already English/Latin, do not run it through RU->EN.
        if not _CYRILLIC_RE.search(text):
            result = self._cleanup(text)
            self._cache_put(cache_key, result)
            return result, perf_counter() - started

        phrase_key = self._phrase_key(text)
        exact = self.exact_phrases.get(phrase_key)
        if exact:
            result = self._cleanup(exact)
            self._cache_put(cache_key, result)
            return result, perf_counter() - started

        prepared = self._prepare(text)

        try:
            tokens = self.source_sp.encode(
                prepared,
                out_type=str,
            )
            tokens.append("</s>")

            # beam_size=2 costs very little on short chat phrases but is
            # generally more reliable than greedy decoding.
            result = self.translator.translate_batch(
                [tokens],
                beam_size=2,
                max_decoding_length=128,
            )[0]

            translated = self.target_sp.decode(
                result.hypotheses[0]
            )

            translated = self._post_fix(translated)
            translated = self._cleanup(translated)

            # Never lose the user's message because of an empty model result.
            if not translated:
                translated = text

        except Exception as exc:
            print(f"⚠ Translation fallback: {exc}")
            translated = text

        self._cache_put(cache_key, translated)

        return translated, perf_counter() - started
