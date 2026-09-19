from pathlib import Path
from queue import Queue
from threading import Thread
from time import perf_counter

import numpy as np
import sherpa_onnx
import sounddevice as sd
from pynput import mouse


MODEL_DIR = Path(
    "models/sherpa-onnx-streaming-t-one-russian-2025-09-08"
)


class StreamingRecognizer:
    def __init__(self, device_index: int):
        self.device_index = device_index

        device = sd.query_devices(
            device_index,
            "input",
        )

        self.sample_rate = int(
            device["default_samplerate"]
        )

        print()
        print(f'Микрофон: {device["name"]}')
        print(f"Частота: {self.sample_rate} Hz")
        print()

        print("Загрузка T-One...")

        self.recognizer = (
            sherpa_onnx.OnlineRecognizer.from_t_one_ctc(
                tokens=str(
                    MODEL_DIR / "tokens.txt"
                ),
                model=str(
                    MODEL_DIR / "model.onnx"
                ),
                num_threads=4,
                sample_rate=8000,
                decoding_method="greedy_search",
                provider="cpu",
                enable_endpoint_detection=False,
            )
        )

        print("✅ T-One готов.")
        print()

        self.audio_stream = None
        self.sherpa_stream = None

        self.queue = None

        self.recording = False
        self.processing = False

        self.release_time = None

    def audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        if status:
            print(f"[AUDIO] {status}")

        if not self.recording:
            return

        samples = (
            indata[:, 0]
            .astype(np.float32)
            .copy()
        )

        self.queue.put(samples)

    def start(self):
        if self.recording or self.processing:
            return

        print()
        print("🔴 Слушаю...")

        self.queue = Queue()

        self.sherpa_stream = (
            self.recognizer.create_stream()
        )

        self.recording = True
        self.processing = True

        Thread(
            target=self.decode_worker,
            daemon=True,
        ).start()

        self.audio_stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self.audio_callback,
        )

        self.audio_stream.start()

    def stop(self):
        if not self.recording:
            return

        self.release_time = perf_counter()

        self.recording = False

        if self.audio_stream is not None:
            self.audio_stream.stop()
            self.audio_stream.close()

            self.audio_stream = None

        # Конец аудио
        self.queue.put(None)

        print()
        print("⏹ Кнопка отпущена")

    def decode_worker(self):
        last_text = ""

        while True:
            chunk = self.queue.get()

            if chunk is None:
                break

            self.sherpa_stream.accept_waveform(
                self.sample_rate,
                chunk,
            )

            while self.recognizer.is_ready(
                self.sherpa_stream
            ):
                self.recognizer.decode_stream(
                    self.sherpa_stream
                )

            result = self.recognizer.get_result(
                self.sherpa_stream
            )

            text = result.strip()

            if text and text != last_text:
                last_text = text

                print(
                    f"\r📝 {text}",
                    end="",
                    flush=True,
                )

        # Небольшой хвост тишины,
        # чтобы модель закончила последнее слово
        tail = np.zeros(
            int(self.sample_rate * 0.35),
            dtype=np.float32,
        )

        self.sherpa_stream.accept_waveform(
            self.sample_rate,
            tail,
        )

        self.sherpa_stream.input_finished()

        while self.recognizer.is_ready(
            self.sherpa_stream
        ):
            self.recognizer.decode_stream(
                self.sherpa_stream
            )

        result = self.recognizer.get_result_all(
            self.sherpa_stream
        )

        text = result.text.strip()

        elapsed = (
            perf_counter()
            - self.release_time
        )

        print()
        print()
        print("=" * 60)
        print(f"🎙 Финал: {text}")
        print(
            f"⚡ После отпускания кнопки: "
            f"{elapsed:.3f} сек."
        )
        print("=" * 60)
        print()

        self.processing = False


def main():
    recognizer = StreamingRecognizer(
        device_index=7
    )

    print("MOUSE5 — удерживай и говори")
    print("Ctrl+C — выход")
    print()

    def on_click(
        x,
        y,
        button,
        pressed,
    ):
        if button != mouse.Button.x2:
            return

        if pressed:
            recognizer.start()
        else:
            recognizer.stop()

    with mouse.Listener(
        on_click=on_click
    ) as listener:
        listener.join()


if __name__ == "__main__":
    main()
