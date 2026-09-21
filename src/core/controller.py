import threading
from time import perf_counter

import numpy as np
import sounddevice as sd

from src.input.dota_sender import DotaChatSender
from src.input.hotkeys import GlobalPTTListener
from src.speech.gigaam_engine import GigaAMEngine
from src.text.postprocessor import TextPostProcessor
from src.utils.dota_status import is_dota_running
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
    ):
        self.device_index = device_index
        self.team_bind = team_bind
        self.all_bind = all_bind

        self.on_status = on_status or (lambda text: None)
        self.on_text = on_text or (lambda text: None)
        self.on_timing = on_timing or (lambda value: None)

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
        self.processing = False
        self.chat_type = None

        self.lock = threading.Lock()

        self.hotkeys = GlobalPTTListener(
            self._on_hotkey
        )

        self.release_time = None

    # ========================================================
    # Controller
    # ========================================================

    def start(self):
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

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        if status:
            print(f"[AUDIO] {status}")

        with self.lock:
            if self.recording:
                self.frames.append(
                    indata[:, 0]
                    .astype(np.float32)
                    .copy()
                )

    def _start_recording(
        self,
        chat_type: str,
    ):
        if self.recording or self.processing:
            return

        self.chat_type = chat_type

        with self.lock:
            self.frames = []
            self.recording = True

        self.stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )

        self.stream.start()

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

        self.release_time = perf_counter()

        with self.lock:
            self.recording = False

        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        with self.lock:
            frames = self.frames.copy()
            self.frames = []

        if not frames:
            self.on_status("Аудио не записано")
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
            return

        chat_type = self.chat_type
        self.processing = True

        threading.Thread(
            target=self._process,
            args=(
                audio,
                chat_type,
            ),
            daemon=True,
        ).start()

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

            raw_text, asr_time = (
                self.speech.transcribe(
                    audio,
                    self.sample_rate,
                )
            )

            print()
            print(f"🎙 RAW: {raw_text}")
            print(
                f"⚡ GigaAM: "
                f"{asr_time:.3f} сек."
            )

            if not raw_text:
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

            if total_time > 5:
                print(
                    "⚠ Превышено 5 секунд!"
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
