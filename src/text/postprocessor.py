import json
import re
from time import perf_counter

import numpy as np
import onnxruntime as ort
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
from tokenizers import Tokenizer


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
        self.aliases = json.loads(
            (
                DATA_DIR
                / "dota_aliases.json"
            ).read_text(
                encoding="utf-8"
            )
        )

        terms = (
            DATA_DIR
            / "dota_terms.txt"
        ).read_text(
            encoding="utf-8"
        ).splitlines()

        self.term_map = {
            term.lower(): term
            for term in terms
            if term.strip()
        }

        self.terms = list(
            self.term_map.keys()
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

        words = text.split()

        output = []

        for word in words:
            clean = re.sub(
                r"[^A-Za-zА-Яа-яЁё-]",
                "",
                word,
            )

            lower = clean.lower()

            if not lower:
                output.append(word)
                continue

            if lower in self.term_map:
                output.append(word)
                continue

            if len(lower) < 4:
                output.append(word)
                continue

            match = process.extractOne(
                lower,
                self.terms,
                scorer=fuzz.ratio,
                score_cutoff=78,
            )

            if match is None:
                output.append(word)
                continue

            candidate = match[0]

            max_distance = (
                1
                if len(lower) <= 6
                else 2
            )

            distance = (
                Levenshtein.distance(
                    lower,
                    candidate,
                )
            )

            if distance <= max_distance:
                output.append(
                    self.term_map[
                        candidate
                    ]
                )
            else:
                output.append(word)

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

        corrected = (
            self._replace_aliases(
                text.strip()
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


