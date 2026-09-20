from time import perf_counter

import numpy as np
import sherpa_onnx

from src.utils.paths import resource_path


MODEL_DIR = resource_path(
    "models/sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19"
)


class GigaAMEngine:
    def __init__(self):
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

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> tuple[str, float]:

        started = perf_counter()

        audio = np.asarray(
            audio,
            dtype=np.float32,
        )

        stream = self.recognizer.create_stream()

        stream.accept_waveform(
            sample_rate,
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

        return text, elapsed
