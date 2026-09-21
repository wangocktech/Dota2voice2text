import json
import re
from time import perf_counter

import numpy as np
import onnxruntime as ort
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
from tokenizers import Tokenizer


from src.text.custom_dictionary import (
    apply_custom_dictionary,
    load_custom_dictionary,
)
from src.utils.paths import resource_path

DATA_DIR = resource_path("data")
PUNCT_DIR = resource_path("models/rupunct-small-onnx")


PUNCTUATION = {
    "O": "",
    "PERIOD": ".",
    "COMMA": ",",
    "QUESTION": "?",
    "TIRE": " —",
    "DVOETOCHIE": ":",
    "VOSKL": "!",
    "PERIODCOMMA": ";",
    "DEFIS": "-",
    "MNOGOTOCHIE": "...",
    "QUESTIONVOSKL": "?!",
}


class TextPostProcessor:
    def __init__(self):
        self.custom_dictionary = load_custom_dictionary()

        self.aliases = json.loads(
            (
                DATA_DIR
                / "dota_aliases.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        # IMPORTANT:
        # dota_terms.txt contains many ordinary Russian words. Older builds used
        # the whole file as a fuzzy-correction target, which could turn already
        # correct ASR text into another valid word ("тест" -> "текст",
        # "помогите" -> "помогут", etc.).
        #
        # v0.3.3 accuracy fix only allows fuzzy correction against explicit
        # Dota aliases. Ordinary Russian words are therefore preserved.
        self.fuzzy_aliases = {
            source.lower(): target
            for source, target in self.aliases.items()
            if (
                " " not in source.strip()
                and len(source.strip()) >= 5
            )
        }

        self.fuzzy_alias_sources = list(
            self.fuzzy_aliases.keys()
        )

        options = (
            ort.SessionOptions()
        )

        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1

        options.graph_optimization_level = (
            ort.GraphOptimizationLevel
            .ORT_ENABLE_ALL
        )

        self.session = ort.InferenceSession(
            str(
                PUNCT_DIR
                / "rupunct_small_int8.onnx"
            ),
            sess_options=options,
            providers=[
                "CPUExecutionProvider"
            ],
        )

        self.tokenizer = (
            Tokenizer.from_file(
                str(
                    PUNCT_DIR
                    / "tokenizer.json"
                )
            )
        )

        config = json.loads(
            (
                PUNCT_DIR
                / "config.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        self.id2label = {
            int(key): value
            for key, value
            in config["id2label"].items()
        }

        # Прогрев модели один раз при запуске.
        self._punctuate(
            "проверка работы программы"
        )

    def reload_custom_dictionary(self):
        self.custom_dictionary = load_custom_dictionary()

    def _replace_aliases(
        self,
        text: str,
    ) -> str:

        result = text

        # Сначала длинные фразы.
        for source, target in sorted(
            self.aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
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

    def _correct_dota_words(
        self,
        text: str,
    ) -> str:
        """
        Conservative Dota correction.

        Only explicit aliases may be used as fuzzy targets. This is deliberate:
        a huge generic vocabulary can silently damage words that GigaAM already
        recognized correctly.
        """

        if not self.fuzzy_alias_sources:
            return text

        output = []

        for word in text.split():
            clean = re.sub(
                r"[^A-Za-zА-Яа-яЁё-]",
                "",
                word,
            )

            lower = clean.lower()

            if not lower or len(lower) < 5:
                output.append(word)
                continue

            # Exact aliases were already handled by _replace_aliases().
            if lower in self.aliases:
                output.append(word)
                continue

            # Keep fuzzy search narrow: similar length + same first character.
            candidates = [
                source
                for source in self.fuzzy_alias_sources
                if (
                    source[:1] == lower[:1]
                    and abs(len(source) - len(lower)) <= 1
                )
            ]

            if not candidates:
                output.append(word)
                continue

            match = process.extractOne(
                lower,
                candidates,
                scorer=fuzz.ratio,
                score_cutoff=86,
            )

            if match is None:
                output.append(word)
                continue

            candidate = match[0]
            distance = Levenshtein.distance(
                lower,
                candidate,
            )

            max_distance = (
                1
                if len(lower) <= 8
                else 2
            )

            if distance > max_distance:
                output.append(word)
                continue

            replacement = self.fuzzy_aliases[
                candidate
            ]

            # Preserve punctuation around the token.
            start = word.find(clean)

            if start < 0:
                output.append(replacement)
                continue

            end = start + len(clean)
            output.append(
                word[:start]
                + replacement
                + word[end:]
            )

        return " ".join(output)

    @staticmethod
    def _render_word(
        word: str,
        label: str,
    ) -> str:

        if label.startswith(
            "UPPER_TOTAL_"
        ):
            base = word.upper()

            punct_name = label[
                len("UPPER_TOTAL_"):
            ]

        elif label.startswith(
            "UPPER_"
        ):
            base = (
                word[:1].upper()
                + word[1:]
            )

            punct_name = label[
                len("UPPER_"):
            ]

        elif label.startswith(
            "LOWER_"
        ):
            base = word.lower()

            punct_name = label[
                len("LOWER_"):
            ]

        else:
            base = word
            punct_name = "O"

        punctuation = (
            PUNCTUATION.get(
                punct_name,
                "",
            )
        )

        return base + punctuation

    def _punctuate(
        self,
        text: str,
    ) -> str:

        words = text.split()

        if not words:
            return ""

        encoding = (
            self.tokenizer.encode(
                words,
                is_pretokenized=True,
            )
        )

        input_ids = np.array(
            [encoding.ids],
            dtype=np.int64,
        )

        attention_mask = np.array(
            [encoding.attention_mask],
            dtype=np.int64,
        )

        token_type_ids = np.array(
            [encoding.type_ids],
            dtype=np.int64,
        )

        logits = self.session.run(
            None,
            {
                "input_ids":
                    input_ids,

                "attention_mask":
                    attention_mask,

                "token_type_ids":
                    token_type_ids,
            },
        )[0][0]

        predictions = np.argmax(
            logits,
            axis=-1,
        )

        labels = [
            "LOWER_O"
        ] * len(words)

        seen = set()

        for token_index, word_id in enumerate(
            encoding.word_ids
        ):
            if word_id is None:
                continue

            if word_id in seen:
                continue

            seen.add(word_id)

            label_id = int(
                predictions[token_index]
            )

            labels[word_id] = (
                self.id2label[
                    label_id
                ]
            )

        result = []

        for word, label in zip(
            words,
            labels,
        ):
            result.append(
                self._render_word(
                    word,
                    label,
                )
            )

        text = " ".join(result)

        # Гарантируем большую первую букву.
        for index, char in enumerate(text):
            if char.isalpha():
                text = (
                    text[:index]
                    + char.upper()
                    + text[index + 1:]
                )
                break

        # Если модель вообще не поставила
        # конечный знак.
        if (
            text
            and text[-1]
            not in ".!?…"
        ):
            text += "."

        return text

    def process(
        self,
        text: str,
    ):

        started = perf_counter()

        corrected = apply_custom_dictionary(
            text.strip(),
            self.custom_dictionary,
        )

        corrected = (
            self._replace_aliases(
                corrected
            )
        )

        corrected = (
            self._correct_dota_words(
                corrected
            )
        )

        final = self._punctuate(
            corrected
        )

        elapsed = (
            perf_counter()
            - started
        )

        return final, elapsed


