import json
import re
from pathlib import Path
from time import perf_counter

import ctranslate2
import sentencepiece as spm

from src.utils.paths import resource_path


MODEL_DIR = resource_path(
    "models/opus-mt-ru-en-ct2-int8"
)

GLOSSARY_FILE = resource_path(
    "data/dota_translation_glossary.json"
)


class EnglishTranslator:
    def __init__(self):
        model_dir = Path(MODEL_DIR)

        required_files = (
            "model.bin",
            "config.json",
            "source.spm",
            "target.spm",
        )

        missing = [
            name
            for name in required_files
            if not (model_dir / name).exists()
        ]

        if missing:
            raise FileNotFoundError(
                "Не установлена модель перевода RU → EN. "
                "Запустите INSTALL_TRANSLATION.ps1. "
                "Не найдены: "
                + ", ".join(missing)
            )

        print(
            "🌐 Загрузка RU → EN переводчика..."
        )

        self.translator = ctranslate2.Translator(
            str(model_dir),
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=4,
        )

        self.source_sp = (
            spm.SentencePieceProcessor(
                model_file=str(
                    model_dir / "source.spm"
                )
            )
        )

        self.target_sp = (
            spm.SentencePieceProcessor(
                model_file=str(
                    model_dir / "target.spm"
                )
            )
        )

        self.glossary = {}

        glossary_path = Path(
            GLOSSARY_FILE
        )

        if glossary_path.exists():
            self.glossary = json.loads(
                glossary_path.read_text(
                    encoding="utf-8-sig"
                )
            )

        # Long terms first: "сентри варды" before "варды".
        self.glossary_items = sorted(
            self.glossary.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        # Warm up once so the first real message is not slow.
        self.translate(
            "Поставьте варды."
        )

        print(
            "✅ RU → EN переводчик готов."
        )

    def _normalize_dota_terms(
        self,
        text: str,
    ) -> str:
        result = text

        for source, target in self.glossary_items:
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

    @staticmethod
    def _cleanup(
        text: str,
    ) -> str:
        text = text.strip()

        # SentencePiece / model can occasionally leave spaces
        # before punctuation.
        text = re.sub(
            r"\s+([,.!?;:])",
            r"\1",
            text,
        )

        text = re.sub(
            r"\s{2,}",
            " ",
            text,
        )

        if text:
            text = (
                text[0].upper()
                + text[1:]
            )

        return text

    def translate(
        self,
        text: str,
    ) -> tuple[str, float]:
        if not text.strip():
            return "", 0.0

        started = perf_counter()

        prepared = (
            self._normalize_dota_terms(
                text
            )
        )

        tokens = self.source_sp.encode(
            prepared,
            out_type=str,
        )

        # Marian expects EOS.
        tokens.append("</s>")

        result = self.translator.translate_batch(
            [tokens],
            beam_size=1,
            max_decoding_length=128,
        )[0]

        translated_tokens = (
            result.hypotheses[0]
        )

        translated = (
            self.target_sp.decode(
                translated_tokens
            )
        )

        translated = self._cleanup(
            translated
        )

        elapsed = (
            perf_counter()
            - started
        )

        return translated, elapsed
