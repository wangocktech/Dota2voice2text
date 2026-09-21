import threading
from collections import deque
from time import perf_counter, sleep

import numpy as np
import sounddevice as sd

from src.input.dota_sender import DotaChatSender
from src.input.hotkeys import GlobalPTTListener
from src.speech.gigaam_engine import GigaAMEngine
from src.speech.adaptive_asr import AdaptiveASR
from src.text.postprocessor import TextPostProcessor
from src.utils.dota_status import is_dota_running
from src.utils.asr_metrics import save_asr_metrics
from src.text.translator import EnglishTranslator
from src.text.translation_model_manager import (
    is_translation_model_installed,
)


class VoiceController:
    def __init__(
        self,
        device_index: int,
        team_bind: str = "mouse:x2",
        all_bind: str = "mouse:x1",
        auto_send: bool = False,
        translate_to_english: bool = False,
        on_status=None,
        on_text=None,
        on_timing=None,
        on_ptt=None,
    ):
        self.device_index = device_index
        self.team_bind = team_bind
        self.all_bind = all_bind

        self.on_status = on_status or (lambda text: None)
        self.on_text = on_text or (lambda text: None)
        self.on_timing = on_timing or (lambda value: None)
        self.on_ptt = on_ptt or (
            lambda active, chat_type: None
        )

        if (
            translate_to_english
            and not is_translation_model_installed()
        ):
            raise RuntimeError(
                "Модель перевода не установлена."
            )

        # Models are loaded once when the controller starts.
        self.on_status("Загрузка GigaAM...")
        self.speech = GigaAMEngine()
        self.adaptive_asr = AdaptiveASR(self.speech)

        self.on_status("Загрузка корректора...")
        self.postprocessor = TextPostProcessor()

        self.translate_to_english = translate_to_english
        self.translator = None

        if self.translate_to_english:
            self.on_status("Загрузка переводчика...")
            self.translator = EnglishTranslator()

        self.sender = DotaChatSender(
            auto_send=auto_send
        )

        device = sd.query_devices(
            device_index,
            "input",
        )

        self.sample_rate = int(
            device["default_samplerate"]
        )

        self.frames = []
        self.stream = None

        self.recording = False
        self.tail_capture = False
        self.processing = False
        self.chat_type = None

        self.pre_roll_seconds = 0.30
        self.tail_seconds = 0.30
        self.block_duration = 0.02
        self.blocksize = max(160, int(self.sample_rate * self.block_duration))
        self.pre_roll_max_samples = max(1, int(self.sample_rate * self.pre_roll_seconds))
        self.pre_roll_frames = deque()
        self.pre_roll_samples = 0

        self.lock = threading.Lock()

        self.hotkeys = GlobalPTTListener(
            self._on_hotkey
        )

        self.release_time = None

    # ========================================================
    # Controller
    # ========================================================

    def start(self):
        self._ensure_audio_stream()
        self.hotkeys.start()
        self.on_status("Готов")

    def stop(self):
        self.hotkeys.stop()

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass

            self.stream = None

        self.recording = False
        self.tail_capture = False
        self.processing = False
        self.on_ptt(False, self.chat_type or "")
        self.on_status("Остановлено")

    # ========================================================
    # Hotkeys
    # ========================================================

    def _on_hotkey(
        self,
        bind: str,
        pressed: bool,
    ):
        try:
            if bind == self.team_bind:
                if pressed:
                    self._start_recording("team")
                else:
                    self._stop_recording()
                return

            if bind == self.all_bind:
                if pressed:
                    self._start_recording("all")
                else:
                    self._stop_recording()

        except Exception as exc:
            print(f"❌ HOTKEY: {exc}")
            self.on_status(f"Ошибка: {exc}")

    # ========================================================
    # Audio
    # ========================================================

    def _remember_pre_roll(self, chunk: np.ndarray):
        self.pre_roll_frames.append(chunk)
        self.pre_roll_samples += len(chunk)

        while (
            self.pre_roll_frames
            and self.pre_roll_samples > self.pre_roll_max_samples
        ):
            removed = self.pre_roll_frames.popleft()
            self.pre_roll_samples -= len(removed)

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        if status:
            print(f"[AUDIO] {status}")

        chunk = (
            indata[:, 0]
            .astype(np.float32)
            .copy()
        )

        with self.lock:
            if self.recording or self.tail_capture:
                self.frames.append(chunk)
            else:
                self._remember_pre_roll(chunk)

    def _ensure_audio_stream(self):
        if self.stream is not None:
            return

        self.stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.blocksize,
            latency="low",
            callback=self._audio_callback,
        )

        self.stream.start()

    def _start_recording(
        self,
        chat_type: str,
    ):
        if (
            self.recording
            or self.processing
            or self.tail_capture
        ):
            return

        self._ensure_audio_stream()
        self.chat_type = chat_type

        with self.lock:
            # Copy a short rolling buffer so the first consonant is not lost
            # when the user starts speaking at the same moment as the PTT press.
            self.frames = [
                frame.copy()
                for frame in self.pre_roll_frames
            ]
            self.recording = True

        self.on_ptt(
            True,
            chat_type,
        )

        if chat_type == "team":
            self.on_status(
                "Слушаю → командный чат"
            )
        else:
            self.on_status(
                "Слушаю → общий чат"
            )

    def _stop_recording(self):
        if not self.recording:
            return

        self.on_ptt(
            False,
            self.chat_type or "",
        )

        self.release_time = perf_counter()

        with self.lock:
            self.recording = False
            self.tail_capture = True

        chat_type = self.chat_type
        self.processing = True

        threading.Thread(
            target=self._finish_capture_after_tail,
            args=(chat_type,),
            daemon=True,
        ).start()

    def _finish_capture_after_tail(
        self,
        chat_type: str,
    ):
        try:
            # Keep a small post-release tail. It prevents the last consonant or
            # short word from being cut when the user releases PTT quickly.
            sleep(self.tail_seconds)

            with self.lock:
                self.tail_capture = False
                frames = self.frames.copy()
                self.frames = []

            if not frames:
                self.on_status("Аудио не записано")
                self.processing = False
                return

            audio = np.concatenate(
                frames
            ).astype(np.float32)

            duration = (
                len(audio)
                / self.sample_rate
            )

            if duration < 0.15:
                self.on_status(
                    "Запись слишком короткая"
                )
                self.processing = False
                return

            self._process(
                audio,
                chat_type,
            )

        except Exception as exc:
            self.processing = False
            print(f"❌ CAPTURE: {exc}")
            self.on_status(
                f"Ошибка: {exc}"
            )

    # ========================================================
    # Pipeline
    # ========================================================

    def _process(
        self,
        audio,
        chat_type,
    ):
        try:
            self.on_status("Распознаю...")

            recognition_deadline = (
                self.release_time + 2.85
                if self.release_time is not None
                else perf_counter() + 2.85
            )

            asr_result = (
                self.adaptive_asr.transcribe(
                    audio,
                    self.sample_rate,
                    deadline_at=recognition_deadline,
                )
            )

            raw_text = asr_result.text
            asr_time = asr_result.elapsed_seconds

            print()
            print(f"🎙 RAW: {raw_text}")
            print(
                f"⚡ Adaptive ASR: "
                f"{asr_time:.3f} сек. | "
                f"{asr_result.mode} | "
                f"confidence "
                f"{asr_result.confidence * 100:.0f}% | "
                f"attempts {asr_result.attempts}"
            )
            print(
                f"   preprocess "
                f"{asr_result.preprocess_seconds:.3f}s | "
                f"trim {asr_result.trimmed_ratio:.2f} | "
                f"Dota hints {asr_result.dota_bias_hits}"
            )

            if (
                asr_result.candidate_b
                and asr_result.candidate_b != asr_result.candidate_a
            ):
                print(
                    "   Candidate A: "
                    f"{asr_result.candidate_a}"
                )
                print(
                    "   Candidate B: "
                    f"{asr_result.candidate_b}"
                )
                print(
                    "   Agreement: "
                    f"{asr_result.agreement:.2f}"
                )

            if not raw_text:
                if asr_result.timed_out:
                    self.on_status(
                        "Распознавание превысило 3 сек."
                    )
                else:
                    self.on_status(
                        "Речь не распознана"
                    )
                return

            final_text, post_time = (
                self.postprocessor.process(
                    raw_text
                )
            )

            print(
                f"✨ RU: {final_text}"
            )
            print(
                f"⚡ POST: "
                f"{post_time:.3f} сек."
            )

            translation_time = 0.0

            if self.translator is not None:
                self.on_status(
                    "Перевожу на английский..."
                )

                (
                    translated_text,
                    translation_time,
                ) = self.translator.translate(
                    final_text
                )

                print(
                    f"🌐 EN: "
                    f"{translated_text}"
                )
                print(
                    f"⚡ Translation: "
                    f"{translation_time:.3f} сек."
                )

                final_text = translated_text

            print(
                f"✅ FINAL: "
                f"{final_text}"
            )

            self.on_text(final_text)

            self.on_status(
                "Вставляю текст..."
            )

            inserted = (
                self.sender.insert_text(
                    text=final_text,
                    chat_type=chat_type,
                )
            )

            total_time = (
                perf_counter()
                - self.release_time
            )

            save_asr_metrics({
                "mode": asr_result.mode,
                "confidence": round(asr_result.confidence, 3),
                "attempts": asr_result.attempts,
                "asr_seconds": round(asr_time, 4),
                "preprocess_seconds": round(
                    asr_result.preprocess_seconds,
                    4,
                ),
                "post_seconds": round(post_time, 4),
                "translation_seconds": round(translation_time, 4),
                "total_seconds": round(total_time, 4),
                "trimmed_ratio": round(asr_result.trimmed_ratio, 3),
                "agreement": round(asr_result.agreement, 3),
                "dota_bias_hits": asr_result.dota_bias_hits,
            })

            print(
                f"🚀 ВСЕГО: "
                f"{total_time:.3f} сек."
            )

            if self.translator is not None:
                print(
                    f"   ASR {asr_time:.3f}s | "
                    f"POST {post_time:.3f}s | "
                    f"EN {translation_time:.3f}s"
                )

            self.on_timing(total_time)

            if asr_time > 2.85:
                print(
                    "⚠ ASR достиг лимита 3 секунд."
                )

            if total_time > 5:
                print(
                    "⚠ Полный pipeline превысил 5 секунд!"
                )

            if inserted:
                self.on_status(
                    f"Готов • "
                    f"{total_time:.2f} сек."
                )
            else:
                if is_dota_running():
                    status_text = (
                        "Dota 2 запущена, "
                        "но окно не активно"
                    )
                else:
                    status_text = (
                        "Dota 2 не запущена"
                    )

                self.on_status(
                    status_text
                )

        except Exception as exc:
            print(f"❌ Ошибка: {exc}")
            self.on_status(
                f"Ошибка: {exc}"
            )

        finally:
            self.processing = False
