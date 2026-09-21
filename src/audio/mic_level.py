import math

import numpy as np
import sounddevice as sd

from PySide6.QtCore import QObject, Signal


class MicrophoneLevelMonitor(QObject):
    level_changed = Signal(int)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.stream = None
        self.device_index = None
        self.sample_rate = None
        self._smoothed_level = 0.0

    @property
    def running(self):
        return self.stream is not None

    def start(self, device_index: int):
        self.stop()

        try:
            info = sd.query_devices(
                device_index,
                "input",
            )

            self.device_index = device_index
            self.sample_rate = int(
                info["default_samplerate"]
            )

            self._smoothed_level = 0.0

            self.stream = sd.InputStream(
                device=device_index,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=1024,
                callback=self._callback,
            )

            self.stream.start()

        except Exception as exc:
            self.stream = None
            self.error.emit(str(exc))
            raise

    def stop(self):
        stream = self.stream
        self.stream = None

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass

            try:
                stream.close()
            except Exception:
                pass

        self._smoothed_level = 0.0
        self.level_changed.emit(0)

    def _callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        try:
            samples = np.asarray(
                indata[:, 0],
                dtype=np.float32,
            )

            if samples.size == 0:
                return

            rms = float(
                np.sqrt(
                    np.mean(
                        samples * samples
                    )
                )
            )

            db = 20.0 * math.log10(
                max(rms, 1e-8)
            )

            # -55 dB ~= тишина, -5 dB ~= почти максимум.
            level = (
                (db + 55.0)
                / 50.0
                * 100.0
            )

            level = max(
                0.0,
                min(
                    100.0,
                    level,
                ),
            )

            self._smoothed_level = (
                self._smoothed_level
                * 0.70
                + level
                * 0.30
            )

            self.level_changed.emit(
                int(
                    round(
                        self._smoothed_level
                    )
                )
            )

        except Exception as exc:
            self.error.emit(
                str(exc)
            )
