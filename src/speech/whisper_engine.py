from time import perf_counter

from faster_whisper import WhisperModel


class WhisperEngine:
    def __init__(self, model_size: str = "turbo"):
        print(f"Загрузка модели Whisper: {model_size}...")

        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=12,
            num_workers=1,
        )

        print("✅ Whisper готов.")

    def transcribe(self, audio_path: str) -> str:
        started = perf_counter()

        segments, _ = self.model.transcribe(
            audio_path,

            language="ru",

            # Главное ускорение
            beam_size=1,
            best_of=1,

            temperature=0.0,

            # PTT уже сам задаёт начало и конец
            vad_filter=False,

            without_timestamps=True,
            word_timestamps=False,

            condition_on_previous_text=False,
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()

        elapsed = perf_counter() - started

        print(f"⚡ Распознавание: {elapsed:.2f} сек.")

        return text
