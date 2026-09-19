import sys
import wave
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import mouse

from src.input.dota_sender import DotaChatSender
from src.speech.whisper_engine import WhisperEngine


OUTPUT_DIR = Path("recordings")
OUTPUT_FILE = OUTPUT_DIR / "temp.wav"


class PushToTalkRecorder:
    def __init__(
        self,
        device_index: int,
        whisper: WhisperEngine,
        sender: DotaChatSender,
    ):
        self.device_index = device_index
        self.whisper = whisper
        self.sender = sender

        device_info = sd.query_devices(device_index, "input")

        self.sample_rate = int(device_info["default_samplerate"])
        self.channels = 1

        self.stream = None
        self.frames = []

        self.recording = False
        self.processing = False

        self.chat_type = None

        self.lock = threading.Lock()

        print()
        print(f'Устройство: {device_info["name"]}')
        print(f"Частота: {self.sample_rate} Hz")
        print()

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"[AUDIO] {status}")

        with self.lock:
            if self.recording:
                self.frames.append(indata.copy())

    def start(self, chat_type: str):
        if self.recording or self.processing:
            return

        self.chat_type = chat_type

        with self.lock:
            self.frames = []
            self.recording = True

        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback,
            )

            self.stream.start()

        except Exception:
            with self.lock:
                self.recording = False

            raise

        if chat_type == "team":
            print()
            print("🔴 Слушаю → КОМАНДНЫЙ ЧАТ...")
        else:
            print()
            print("🔴 Слушаю → ОБЩИЙ ЧАТ...")

    def stop(self):
        if not self.recording:
            return

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
            print("⚠ Ничего не записано.")
            return

        audio = np.concatenate(frames, axis=0)

        duration = len(audio) / self.sample_rate

        if duration < 0.15:
            print("⚠ Запись слишком короткая.")
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        with wave.open(str(OUTPUT_FILE), "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio.tobytes())

        print(f"⏹ Запись завершена ({duration:.2f} сек.)")
        print("🧠 Распознаю...")

        chat_type = self.chat_type

        threading.Thread(
            target=self._recognize_and_insert,
            args=(chat_type,),
            daemon=True,
        ).start()

    def _recognize_and_insert(self, chat_type: str):
        self.processing = True

        try:
            text = self.whisper.transcribe(str(OUTPUT_FILE))

            if not text:
                print("⚠ Речь не распознана.")
                return

            print()
            print("=" * 60)
            print(f"🎙 Ты сказал: {text}")
            print("=" * 60)

            self.sender.insert_text(
                text=text,
                chat_type=chat_type,
            )

            print()

        except Exception as exc:
            print(f"❌ Ошибка: {exc}")

        finally:
            self.processing = False


def main():
    if len(sys.argv) < 2:
        print("Укажи ID микрофона.")
        print()
        print("Пример:")
        print("python -m src.audio.recorder 7")
        raise SystemExit(1)

    device_index = int(sys.argv[1])

    print()
    print("Dota2voice2text")
    print("================")
    print()

    whisper = WhisperEngine("turbo")

    sender = DotaChatSender(
        auto_send=False,
    )

    recorder = PushToTalkRecorder(
        device_index=device_index,
        whisper=whisper,
        sender=sender,
    )

    print("MOUSE5 — командный чат")
    print("MOUSE4 — общий чат")
    print("Ctrl+C — выход")
    print()

    def on_click(x, y, button, pressed):
        try:
            # MOUSE5
            if button == mouse.Button.x2:
                if pressed:
                    recorder.start("team")
                else:
                    recorder.stop()

            # MOUSE4
            elif button == mouse.Button.x1:
                if pressed:
                    recorder.start("all")
                else:
                    recorder.stop()

        except Exception as exc:
            print(f"❌ Ошибка: {exc}")

    with mouse.Listener(on_click=on_click) as listener:
        listener.join()


if __name__ == "__main__":
    main()
