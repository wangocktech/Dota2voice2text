from pathlib import Path
import wave

import numpy as np
import sherpa_onnx


MODEL_DIR = Path(
    "models/sherpa-onnx-streaming-t-one-russian-2025-09-08"
)


recognizer = sherpa_onnx.OnlineRecognizer.from_t_one_ctc(
    tokens=str(MODEL_DIR / "tokens.txt"),
    model=str(MODEL_DIR / "model.onnx"),
    num_threads=4,
    sample_rate=8000,
    decoding_method="greedy_search",
    provider="cpu",
    enable_endpoint_detection=False,
)


wav_path = MODEL_DIR / "0.wav"

with wave.open(str(wav_path), "rb") as f:
    sample_rate = f.getframerate()
    channels = f.getnchannels()
    sample_width = f.getsampwidth()

    if channels != 1:
        raise RuntimeError(
            f"Ожидалось mono, получено каналов: {channels}"
        )

    if sample_width != 2:
        raise RuntimeError(
            f"Ожидался PCM16, sample width: {sample_width}"
        )

    raw = f.readframes(f.getnframes())


samples = (
    np.frombuffer(raw, dtype=np.int16)
    .astype(np.float32)
    / 32768.0
)


stream = recognizer.create_stream()

stream.accept_waveform(
    sample_rate,
    samples,
)

# Немного тишины в конец, чтобы модель закончила фразу
tail = np.zeros(
    int(sample_rate * 0.5),
    dtype=np.float32,
)

stream.accept_waveform(
    sample_rate,
    tail,
)

stream.input_finished()


while recognizer.is_ready(stream):
    recognizer.decode_stream(stream)


result = recognizer.get_result_all(stream)

print()
print("=" * 70)
print("T-One result:")
print(result.text)
print("=" * 70)
