from __future__ import annotations

import math
import queue
import re
import threading
from dataclasses import dataclass
from difflib import SequenceMatcher
from time import perf_counter

import numpy as np

from src.text.custom_dictionary import load_custom_dictionary
from src.utils.paths import resource_path


ASR_DEADLINE_SECONDS = 2.85
SECOND_PASS_MIN_REMAINING = 0.45
SECOND_PASS_MAX_FIRST_PASS = 0.95


@dataclass(slots=True)
class AdaptiveASRResult:
    text: str
    elapsed_seconds: float
    preprocess_seconds: float
    confidence: float
    mode: str
    attempts: int
    timed_out: bool
    candidate_a: str = ""
    candidate_b: str = ""
    agreement: float = 0.0
    signal_rms: float = 0.0
    trimmed_ratio: float = 1.0
    dota_bias_hits: int = 0


class AdaptiveASR:
    """
    Accuracy-oriented wrapper around GigaAM with a strict user-facing deadline.

    GigaAM is a CTC model. sherpa-onnx's modified beam search/hotword bias is
    intended for transducer models, so this wrapper improves accuracy without
    switching the decoder to an unsupported mode:

    1. sanitize, trim silence and normalize the captured waveform;
    2. run a fast first pass;
    3. when there is enough latency budget, verify with a less-trimmed variant;
    4. score disagreements using text quality + Dota/custom-dictionary hints;
    5. never wait beyond the supplied deadline for a recognition pass.
    """

    def __init__(self, engine):
        self.engine = engine
        self._timed_out_thread: threading.Thread | None = None

        self._aliases = self._load_aliases()

    @staticmethod
    def _load_aliases() -> set[str]:
        import json

        result: set[str] = set()

        try:
            path = resource_path("data/dota_aliases.json")
            data = json.loads(path.read_text(encoding="utf-8-sig"))

            for source, target in data.items():
                for value in (source, target):
                    value = str(value).strip().lower()
                    if value:
                        result.add(value)
        except Exception:
            pass

        return result

    @staticmethod
    def _sanitize(audio: np.ndarray) -> np.ndarray:
        result = np.asarray(audio, dtype=np.float32).reshape(-1)

        if result.size == 0:
            return result

        result = np.nan_to_num(
            result,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        # Remove microphone DC offset. Do not apply aggressive denoising here:
        # it can destroy quiet consonants and make Russian ASR worse.
        result = result - float(np.mean(result))
        result = np.clip(result, -1.0, 1.0)

        return result.astype(np.float32, copy=False)

    @staticmethod
    def _frame_rms(
        audio: np.ndarray,
        sample_rate: int,
    ) -> tuple[np.ndarray, int]:
        frame = max(80, int(sample_rate * 0.020))
        hop = max(40, int(sample_rate * 0.010))

        if len(audio) < frame:
            rms = math.sqrt(float(np.mean(audio * audio)) + 1e-12)
            return np.asarray([rms], dtype=np.float32), hop

        values = []

        for start in range(0, len(audio) - frame + 1, hop):
            chunk = audio[start:start + frame]
            values.append(
                math.sqrt(float(np.mean(chunk * chunk)) + 1e-12)
            )

        return np.asarray(values, dtype=np.float32), hop

    @classmethod
    def _trim_silence(
        cls,
        audio: np.ndarray,
        sample_rate: int,
    ) -> tuple[np.ndarray, float]:
        if audio.size == 0:
            return audio, 1.0

        rms, hop = cls._frame_rms(audio, sample_rate)

        if rms.size == 0:
            return audio, 1.0

        peak = float(np.max(rms))
        floor = float(np.percentile(rms, 20))

        # Adaptive but deliberately conservative. We only cut obvious silence.
        threshold = max(
            0.0025,
            floor * 2.4,
            peak * 0.07,
        )

        active = np.flatnonzero(rms >= threshold)

        if active.size == 0:
            return audio, 1.0

        preserve_before = int(sample_rate * 0.20)
        preserve_after = int(sample_rate * 0.24)

        start = max(
            0,
            int(active[0] * hop) - preserve_before,
        )

        end = min(
            len(audio),
            int((active[-1] + 2) * hop) + preserve_after,
        )

        if end <= start:
            return audio, 1.0

        trimmed = audio[start:end]
        ratio = len(trimmed) / max(1, len(audio))

        return trimmed, float(ratio)

    @staticmethod
    def _normalize(audio: np.ndarray) -> np.ndarray:
        if audio.size == 0:
            return audio

        rms = math.sqrt(float(np.mean(audio * audio)) + 1e-12)
        peak = float(np.max(np.abs(audio)))

        if rms < 1e-5 or peak < 1e-5:
            return audio.astype(np.float32, copy=False)

        target_rms = 0.075
        gain = min(7.0, max(0.45, target_rms / rms))

        normalized = audio * gain
        normalized_peak = float(np.max(np.abs(normalized)))

        if normalized_peak > 0.95:
            normalized *= 0.95 / normalized_peak

        return np.clip(normalized, -1.0, 1.0).astype(
            np.float32,
            copy=False,
        )

    @staticmethod
    def _pad(
        audio: np.ndarray,
        sample_rate: int,
        seconds: float = 0.06,
    ) -> np.ndarray:
        count = max(0, int(sample_rate * seconds))

        if count == 0:
            return audio

        return np.pad(
            audio,
            (count, count),
            mode="constant",
        ).astype(np.float32, copy=False)

    @classmethod
    def _prepare_variants(
        cls,
        audio: np.ndarray,
        sample_rate: int,
    ) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
        started = perf_counter()

        clean = cls._sanitize(audio)
        rms = (
            math.sqrt(float(np.mean(clean * clean)) + 1e-12)
            if clean.size
            else 0.0
        )

        tight, trimmed_ratio = cls._trim_silence(
            clean,
            sample_rate,
        )

        tight = cls._pad(
            cls._normalize(tight),
            sample_rate,
            seconds=0.08,
        )

        # Verification pass intentionally keeps the full context. Boundary
        # mistakes and clipped first/last phonemes are a common PTT failure.
        wide = cls._pad(
            cls._normalize(clean),
            sample_rate,
            seconds=0.10,
        )

        return tight, wide, {
            "preprocess_seconds": perf_counter() - started,
            "signal_rms": rms,
            "trimmed_ratio": trimmed_ratio,
        }

    @staticmethod
    def _text_quality(text: str) -> float:
        text = text.strip()

        if not text:
            return 0.0

        compact = re.sub(r"\s+", " ", text)
        chars = [char for char in compact if not char.isspace()]

        if not chars:
            return 0.0

        alnum = sum(char.isalnum() for char in chars)
        useful_ratio = alnum / len(chars)

        words = [word for word in compact.split(" ") if word]
        score = 0.48 + 0.30 * useful_ratio

        if len(words) >= 2:
            score += 0.08

        if len(compact) >= 6:
            score += 0.05

        # Penalize obvious decoder garbage/repetition.
        if re.search(r"(.)\1{4,}", compact.lower()):
            score -= 0.25

        if len(words) >= 4 and len(set(word.lower() for word in words)) == 1:
            score -= 0.25

        return max(0.0, min(1.0, score))

    def _dota_bias_hits(self, text: str) -> int:
        normalized = text.lower()
        hits = 0

        words = set(
            re.findall(
                r"[0-9a-zа-яё-]+",
                normalized,
                flags=re.IGNORECASE,
            )
        )

        for term in self._aliases:
            if " " in term:
                if term in normalized:
                    hits += 1
            elif term in words:
                hits += 1

        try:
            custom = load_custom_dictionary()

            for source, target in custom.items():
                for value in (source, target):
                    value = str(value).strip().lower()
                    if value and value in normalized:
                        hits += 1
        except Exception:
            pass

        return hits

    def _candidate_score(
        self,
        text: str,
        signal_rms: float,
    ) -> tuple[float, int]:
        quality = self._text_quality(text)
        hits = self._dota_bias_hits(text)

        signal_score = min(
            1.0,
            max(0.0, signal_rms / 0.035),
        )

        score = (
            quality * 0.82
            + signal_score * 0.08
            + min(0.10, hits * 0.025)
        )

        return max(0.0, min(1.0, score)), hits

    def _run_engine_until(
        self,
        audio: np.ndarray,
        sample_rate: int,
        deadline_at: float,
    ) -> tuple[str, float] | None:
        previous = self._timed_out_thread

        if previous is not None and previous.is_alive():
            return None

        remaining = deadline_at - perf_counter()

        if remaining <= 0.01:
            return None

        result_queue: queue.Queue = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                result_queue.put(
                    (True, self.engine.transcribe(audio, sample_rate)),
                    block=False,
                )
            except Exception as exc:
                try:
                    result_queue.put((False, exc), block=False)
                except Exception:
                    pass

        thread = threading.Thread(
            target=worker,
            name="AdaptiveASRDecode",
            daemon=True,
        )
        thread.start()

        try:
            ok, value = result_queue.get(
                timeout=max(0.01, remaining),
            )
        except queue.Empty:
            self._timed_out_thread = thread
            return None

        self._timed_out_thread = None

        if not ok:
            raise value

        text, elapsed = value
        return str(text).strip(), float(elapsed)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int,
        *,
        deadline_at: float | None = None,
    ) -> AdaptiveASRResult:
        started = perf_counter()

        if deadline_at is None:
            deadline_at = started + ASR_DEADLINE_SECONDS

        tight, wide, stats = self._prepare_variants(
            audio,
            sample_rate,
        )

        preprocess_seconds = stats["preprocess_seconds"]
        signal_rms = stats["signal_rms"]
        trimmed_ratio = stats["trimmed_ratio"]

        first = self._run_engine_until(
            tight,
            sample_rate,
            deadline_at,
        )

        if first is None:
            return AdaptiveASRResult(
                text="",
                elapsed_seconds=perf_counter() - started,
                preprocess_seconds=preprocess_seconds,
                confidence=0.0,
                mode="TIMEOUT",
                attempts=1,
                timed_out=True,
                signal_rms=signal_rms,
                trimmed_ratio=trimmed_ratio,
            )

        first_text, first_seconds = first
        first_score, first_hits = self._candidate_score(
            first_text,
            signal_rms,
        )

        remaining = deadline_at - perf_counter()
        expected_retry = max(
            SECOND_PASS_MIN_REMAINING,
            first_seconds * 1.35 + 0.08,
        )

        should_retry = (
            bool(first_text)
            and first_seconds <= SECOND_PASS_MAX_FIRST_PASS
            and remaining >= expected_retry
            and len(wide) > 0
        )

        if not should_retry:
            return AdaptiveASRResult(
                text=first_text,
                elapsed_seconds=perf_counter() - started,
                preprocess_seconds=preprocess_seconds,
                confidence=round(first_score, 3),
                mode="FAST",
                attempts=1,
                timed_out=False,
                candidate_a=first_text,
                signal_rms=signal_rms,
                trimmed_ratio=trimmed_ratio,
                dota_bias_hits=first_hits,
            )

        second = self._run_engine_until(
            wide,
            sample_rate,
            deadline_at,
        )

        if second is None:
            # Verification timed out, but we already have a valid first result.
            return AdaptiveASRResult(
                text=first_text,
                elapsed_seconds=perf_counter() - started,
                preprocess_seconds=preprocess_seconds,
                confidence=round(first_score, 3),
                mode="FAST_DEADLINE",
                attempts=2,
                timed_out=False,
                candidate_a=first_text,
                signal_rms=signal_rms,
                trimmed_ratio=trimmed_ratio,
                dota_bias_hits=first_hits,
            )

        second_text, _second_seconds = second
        second_score, second_hits = self._candidate_score(
            second_text,
            signal_rms,
        )

        agreement = SequenceMatcher(
            None,
            first_text.lower(),
            second_text.lower(),
        ).ratio() if first_text and second_text else 0.0

        if agreement >= 0.94:
            chosen = first_text if len(first_text) >= len(second_text) else second_text
            chosen_score = max(first_score, second_score)
            confidence = min(0.99, chosen_score + 0.12)
            mode = "VERIFY"
            hits = max(first_hits, second_hits)
        else:
            # Prefer the candidate with better textual/Dota plausibility.
            # A tiny tie-break favors the tight-trim pass because it contains
            # less non-speech context.
            if first_score + 0.015 >= second_score:
                chosen = first_text
                chosen_score = first_score
                hits = first_hits
            else:
                chosen = second_text
                chosen_score = second_score
                hits = second_hits

            confidence = min(
                0.95,
                chosen_score + agreement * 0.10,
            )
            mode = "ACCURACY_RETRY"

        return AdaptiveASRResult(
            text=chosen,
            elapsed_seconds=perf_counter() - started,
            preprocess_seconds=preprocess_seconds,
            confidence=round(confidence, 3),
            mode=mode,
            attempts=2,
            timed_out=False,
            candidate_a=first_text,
            candidate_b=second_text,
            agreement=round(agreement, 3),
            signal_rms=signal_rms,
            trimmed_ratio=trimmed_ratio,
            dota_bias_hits=hits,
        )
