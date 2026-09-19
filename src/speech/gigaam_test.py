from pathlib import Path
from time import perf_counter
import threading

import numpy as np
import sherpa_onnx
import sounddevice as sd
from pynput import mouse


MODEL_DIR = Path(
    "models/sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19"
)

DEVICE_INDEX = 7


class OfflineVoiceTest:
    def __init__(self):
        device = sd.query_devices(
            DEVICE_INDEX,
            "input",
        )

        self.sample_rate = int(
            device["default_samplerate"]
        )

        print(f'Микрофон: {device["name"]}')
        print(f"Частота: {self.sample_rate} Hz")
        print()
        print("Загрузка GigaAM v2...")

        self.recognizer = (
            sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
                model=str(
                    MODEL_DIR / "model.int8.onnx"
                ),
                tokens=str(
                    MODEL_DIR / "tokens.txt"
                ),
                num_threads=8,
                sample_rate=16000,
                feature_dim=80,
                decoding_method="greedy_search",
                provider="cpu",
            )
        )

        print("✅ GigaAM v2 готов.")
        print()

        self.frames = []
        self.stream = None
        self.recording = False

    def callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        if status:
            print(status)

        if self.recording:
            self.frames.append(
                indata[:, 0].copy()
            )

    def start(self):
        if self.recording:
            return

        self.frames = []
        self.recording = True

        self.stream = sd.InputStream(
            device=DEVICE_INDEX,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self.callback,
        )

        self.stream.start()

        print()
        print("🔴 Запись...")

    def stop(self):
        if not self.recording:
            return

        self.recording = False

        self.stream.stop()
        self.stream.close()
        self.stream = None

        if not self.frames:
            print("Нет аудио.")
            return

        audio = np.concatenate(
            self.frames
        ).astype(np.float32)

        duration = (
            len(audio)
            / self.sample_rate
        )

        print(
            f"⏹ Запись завершена: "
            f"{duration:.2f} сек."
        )

        threading.Thread(
            target=self.recognize,
            args=(audio,),
            daemon=True,
        ).start()

    def recognize(self, audio):
        started = perf_counter()

        stream = (
            self.recognizer.create_stream()
        )

        stream.accept_waveform(
            self.sample_rate,
            audio,
        )

        self.recognizer.decode_stream(
            stream
        )

        text = stream.result.text.strip()

        elapsed = (
            perf_counter()
            - started
        )

        print()
        print("=" * 60)
        print(f"🎙 {text}")
        print(
            f"⚡ После отпускания: "
            f"{elapsed:.3f} сек."
        )
        print("=" * 60)
        print()


def main():
    app = OfflineVoiceTest()

    print("MOUSE5 — удерживай и говори")
    print("Ctrl+C — выход")

    def on_click(
        x,
        y,
        button,
        pressed,
    ):
        if button != mouse.Button.x2:
            return

        if pressed:
            app.start()
        else:
            app.stop()

    with mouse.Listener(
        on_click=on_click
    ) as listener:
        listener.join()


if __name__ == "__main__":
    main()
