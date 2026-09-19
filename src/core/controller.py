import threading
from time import perf_counter

import numpy as np
import sounddevice as sd
from pynput import mouse

from src.input.dota_sender import DotaChatSender
from src.speech.gigaam_engine import GigaAMEngine
from src.text.postprocessor import TextPostProcessor


class VoiceController:
    def __init__(
        self,
        device_index: int,
        auto_send: bool = False,
        on_status=None,
        on_text=None,
    ):
        self.device_index = device_index

        self.on_status = (
            on_status
            or (lambda text: None)
        )

        self.on_text = (
            on_text
            or (lambda text: None)
        )

        # Загружаются ОДИН РАЗ
        # при запуске программы
        self.on_status(
            "Загрузка GigaAM..."
        )

        self.speech = GigaAMEngine()

        self.on_status(
            "Загрузка корректора..."
        )

        self.postprocessor = (
            TextPostProcessor()
        )

        self.sender = (
            DotaChatSender(
                auto_send=auto_send
            )
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
        self.listener = None

        self.release_time = None

    # ========================================================
    # Start / Stop controller
    # ========================================================

    def start(self):
        if self.listener is not None:
            return

        self.listener = mouse.Listener(
            on_click=self._on_click
        )

        self.listener.start()

        self.on_status(
            "Готов"
        )

    def stop(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener = None

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass

            self.stream = None

        self.recording = False

        self.on_status(
            "Остановлено"
        )

    # ========================================================
    # Hotkeys
    # ========================================================

    def _on_click(
        self,
        x,
        y,
        button,
        pressed,
    ):
        try:
            # MOUSE5
            if button == mouse.Button.x2:
                if pressed:
                    self._start_recording(
                        "team"
                    )
                else:
                    self._stop_recording()

            # MOUSE4
            elif button == mouse.Button.x1:
                if pressed:
                    self._start_recording(
                        "all"
                    )
                else:
                    self._stop_recording()

        except Exception as exc:
            self.on_status(
                f"Ошибка: {exc}"
            )

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
            print(
                f"[AUDIO] {status}"
            )

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
        if (
            self.recording
            or self.processing
        ):
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

        self.release_time = (
            perf_counter()
        )

        with self.lock:
            self.recording = False

        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        with self.lock:
            frames = (
                self.frames.copy()
            )

            self.frames = []

        if not frames:
            self.on_status(
                "Аудио не записано"
            )
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
    # Recognition pipeline
    # ========================================================

    def _process(
        self,
        audio: np.ndarray,
        chat_type: str,
    ):
        try:
            self.on_status(
                "Распознаю..."
            )

            # ----------------------------------------
            # GigaAM
            # ----------------------------------------

            raw_text, asr_time = (
                self.speech.transcribe(
                    audio,
                    self.sample_rate,
                )
            )

            print()
            print(
                f"🎙 RAW: {raw_text}"
            )

            print(
                f"⚡ GigaAM: "
                f"{asr_time:.3f} сек."
            )

            if not raw_text:
                self.on_status(
                    "Речь не распознана"
                )
                return

            # ----------------------------------------
            # Dota dictionary + punctuation
            # ----------------------------------------

            final_text, post_time = (
                self.postprocessor.process(
                    raw_text
                )
            )

            print(
                f"✨ FINAL: "
                f"{final_text}"
            )

            print(
                f"⚡ Post: "
                f"{post_time:.3f} сек."
            )

            self.on_text(
                final_text
            )

            # ----------------------------------------
            # Dota
            # ----------------------------------------

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
                f"🚀 ВСЕГО после отпускания: "
                f"{total_time:.3f} сек."
            )

            if total_time > 5:
                print(
                    "⚠ Превышен лимит "
                    "задержки 5 секунд!"
                )

            if inserted:
                self.on_status(
                    f"Готов • "
                    f"{total_time:.2f} сек."
                )
            else:
                self.on_status(
                    "Dota 2 не активна"
                )

        except Exception as exc:
            print(
                f"❌ Ошибка: {exc}"
            )

            self.on_status(
                f"Ошибка: {exc}"
            )

        finally:
            self.processing = False
