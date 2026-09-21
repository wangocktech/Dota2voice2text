from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
import sounddevice as sd

from src.input.dota_sender import DotaChatSender
from src.input.hotkeys import humanize_bind
from src.speech.gigaam_engine import GigaAMEngine
from src.text.postprocessor import TextPostProcessor
from src.text.translation_model_manager import (
    is_translation_model_installed,
)
from src.text.translator import EnglishTranslator
from src.utils.dota_status import get_dota_state


@dataclass
class SelfTestItem:
    key: str
    title: str
    status: str
    detail: str
    elapsed: float = 0.0


@dataclass
class SelfTestReport:
    items: list[SelfTestItem]
    pipeline_seconds: float | None = None

    @property
    def errors(self) -> list[SelfTestItem]:
        return [item for item in self.items if item.status == "error"]

    @property
    def warnings(self) -> list[SelfTestItem]:
        return [item for item in self.items if item.status == "warning"]

    @property
    def summary(self) -> str:
        if self.errors:
            return f"Ошибок: {len(self.errors)}"
        if self.warnings:
            return f"Готово с предупреждениями: {len(self.warnings)}"
        return "Все проверки пройдены"


APP_DATA_DIR = Path(
    os.getenv(
        "LOCALAPPDATA",
        os.getenv("APPDATA", Path.home()),
    )
) / "Dota2voice2text"

SELF_TEST_REPORT_FILE = APP_DATA_DIR / "self_test_latest.txt"


def _item(
    key: str,
    title: str,
    status: str,
    detail: str,
    elapsed: float = 0.0,
) -> SelfTestItem:
    return SelfTestItem(
        key=key,
        title=title,
        status=status,
        detail=detail,
        elapsed=elapsed,
    )


def format_self_test_report(report: SelfTestReport) -> str:
    labels = {
        "pass": "OK",
        "warning": "WARN",
        "error": "ERROR",
        "skip": "SKIP",
    }

    lines = [
        "Dota2voice2text — самотест",
        f"Система: {platform.platform()}",
        f"Итог: {report.summary}",
        "",
    ]

    for item in report.items:
        elapsed = (
            f" • {item.elapsed:.3f} сек."
            if item.elapsed > 0
            else ""
        )
        lines.append(
            f"[{labels.get(item.status, item.status.upper())}] "
            f"{item.title}{elapsed}"
        )
        lines.append(f"    {item.detail}")

    if report.pipeline_seconds is not None:
        lines.extend([
            "",
            "Синтетический benchmark текущего pipeline: "
            f"{report.pipeline_seconds:.3f} сек.",
            "Цель после отпускания PTT: < 5 сек.",
        ])

    return "\n".join(lines)


def save_self_test_report(report: SelfTestReport) -> Path:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SELF_TEST_REPORT_FILE.write_text(
        format_self_test_report(report),
        encoding="utf-8",
    )
    return SELF_TEST_REPORT_FILE


def run_self_test(
    *,
    device_index: int | None,
    team_bind: str,
    all_bind: str,
    translate_enabled: bool,
    controller=None,
    on_item=None,
) -> SelfTestReport:
    callback = on_item or (lambda item: None)
    items: list[SelfTestItem] = []

    def emit(item: SelfTestItem):
        items.append(item)
        callback(item)

    # --------------------------------------------------------
    # Microphone
    # --------------------------------------------------------
    if device_index is None:
        emit(_item(
            "microphone",
            "Микрофон",
            "error",
            "Устройство ввода не выбрано.",
        ))
    else:
        started = perf_counter()
        try:
            device = sd.query_devices(
                device_index,
                "input",
            )
            sample_rate = int(
                device["default_samplerate"]
            )

            # Если основной controller уже работает, не открываем второй
            # audio stream. Сам факт доступности устройства уже проверен.
            if controller is None:
                frames = max(
                    1,
                    int(sample_rate * 0.20),
                )
                audio = sd.rec(
                    frames,
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                    device=device_index,
                    blocking=True,
                )
                peak = float(
                    np.max(np.abs(audio))
                ) if audio.size else 0.0
                detail = (
                    f'{device["name"]} • {sample_rate} Hz • '
                    f"peak {peak:.3f}"
                )
            else:
                detail = (
                    f'{device["name"]} • {sample_rate} Hz • '
                    "controller уже запущен"
                )

            emit(_item(
                "microphone",
                "Микрофон",
                "pass",
                detail,
                perf_counter() - started,
            ))
        except Exception as exc:
            emit(_item(
                "microphone",
                "Микрофон",
                "error",
                str(exc),
                perf_counter() - started,
            ))

    # --------------------------------------------------------
    # Hotkeys
    # --------------------------------------------------------
    started = perf_counter()
    if not team_bind or not all_bind:
        emit(_item(
            "hotkeys",
            "PTT-клавиши",
            "error",
            "Один или оба бинда не назначены.",
            perf_counter() - started,
        ))
    elif team_bind == all_bind:
        emit(_item(
            "hotkeys",
            "PTT-клавиши",
            "error",
            "Team Chat и All Chat назначены на одну кнопку.",
            perf_counter() - started,
        ))
    else:
        emit(_item(
            "hotkeys",
            "PTT-клавиши",
            "pass",
            f"Team: {humanize_bind(team_bind)} • "
            f"All: {humanize_bind(all_bind)}",
            perf_counter() - started,
        ))

    # --------------------------------------------------------
    # Dota state
    # --------------------------------------------------------
    started = perf_counter()
    try:
        dota = get_dota_state()
        if dota.foreground:
            status = "pass"
        elif dota.running:
            status = "warning"
        else:
            status = "warning"

        emit(_item(
            "dota",
            "Dota 2",
            status,
            dota.text,
            perf_counter() - started,
        ))
    except Exception as exc:
        dota = None
        emit(_item(
            "dota",
            "Dota 2",
            "warning",
            f"Не удалось определить статус: {exc}",
            perf_counter() - started,
        ))

    # --------------------------------------------------------
    # Safe SendInput check — does NOT press/type anything.
    # --------------------------------------------------------
    started = perf_counter()
    try:
        user32 = ctypes.WinDLL(
            "user32",
            use_last_error=True,
        )
        send_input = getattr(
            user32,
            "SendInput",
            None,
        )
        if send_input is None:
            raise RuntimeError(
                "WinAPI SendInput не найден."
            )

        sender = (
            controller.sender
            if controller is not None
            and hasattr(controller, "sender")
            else DotaChatSender(auto_send=False)
        )
        title = sender.get_foreground_window_title()

        if dota is not None and dota.foreground:
            detail = (
                "SendInput доступен; Dota активна. "
                "Тест безопасный — клавиши не отправлялись."
            )
            status = "pass"
        else:
            detail = (
                "SendInput доступен; активное окно: "
                f'"{title or "без заголовка"}". '
                "Клавиши не отправлялись."
            )
            status = "warning"

        emit(_item(
            "sendinput",
            "Windows SendInput",
            status,
            detail,
            perf_counter() - started,
        ))
    except Exception as exc:
        emit(_item(
            "sendinput",
            "Windows SendInput",
            "error",
            str(exc),
            perf_counter() - started,
        ))

    # --------------------------------------------------------
    # GigaAM
    # --------------------------------------------------------
    speech = None
    asr_seconds = None
    started = perf_counter()
    try:
        if (
            controller is not None
            and hasattr(controller, "speech")
        ):
            speech = controller.speech
            source = "уже загруженная модель"
        else:
            speech = GigaAMEngine()
            source = "модель загружена для теста"

        silence = np.zeros(
            4000,
            dtype=np.float32,
        )
        _, asr_seconds = speech.transcribe(
            silence,
            16000,
        )

        emit(_item(
            "gigaam",
            "GigaAM v2",
            "pass",
            f"{source} • inference {asr_seconds:.3f} сек.",
            perf_counter() - started,
        ))
    except Exception as exc:
        emit(_item(
            "gigaam",
            "GigaAM v2",
            "error",
            str(exc),
            perf_counter() - started,
        ))

    # --------------------------------------------------------
    # RUPunct + Dota correction
    # --------------------------------------------------------
    post = None
    post_seconds = None
    started = perf_counter()
    try:
        if (
            controller is not None
            and hasattr(controller, "postprocessor")
        ):
            post = controller.postprocessor
            source = "уже загруженная модель"
        else:
            post = TextPostProcessor()
            source = "модель загружена для теста"

        processed, post_seconds = post.process(
            "поставь варды на рошане"
        )
        emit(_item(
            "postprocessor",
            "RUPunct + Dota-коррекция",
            "pass",
            f'{source} • "{processed}" • '
            f"{post_seconds:.3f} сек.",
            perf_counter() - started,
        ))
    except Exception as exc:
        emit(_item(
            "postprocessor",
            "RUPunct + Dota-коррекция",
            "error",
            str(exc),
            perf_counter() - started,
        ))

    # --------------------------------------------------------
    # RU -> EN
    # --------------------------------------------------------
    translation_seconds = 0.0
    started = perf_counter()
    if not is_translation_model_installed():
        emit(_item(
            "translation",
            "RU → EN",
            "warning" if translate_enabled else "skip",
            (
                "Перевод включён, но модель не установлена."
                if translate_enabled
                else "Модель не установлена; перевод выключен."
            ),
            perf_counter() - started,
        ))
    else:
        try:
            if (
                controller is not None
                and getattr(controller, "translator", None)
                is not None
            ):
                translator = controller.translator
                source = "уже загруженная модель"
            else:
                translator = EnglishTranslator()
                source = "модель загружена для теста"

            translated, translation_seconds = translator.translate(
                "Поставьте варды."
            )
            emit(_item(
                "translation",
                "RU → EN",
                "pass",
                f'{source} • "{translated}" • '
                f"{translation_seconds:.3f} сек.",
                perf_counter() - started,
            ))
        except Exception as exc:
            emit(_item(
                "translation",
                "RU → EN",
                "error" if translate_enabled else "warning",
                str(exc),
                perf_counter() - started,
            ))

    # --------------------------------------------------------
    # Synthetic latency benchmark
    # --------------------------------------------------------
    if asr_seconds is None or post_seconds is None:
        emit(_item(
            "latency",
            "Pipeline latency",
            "error",
            "Benchmark невозможен: ASR или postprocessor не прошёл тест.",
        ))
        pipeline_seconds = None
    else:
        pipeline_seconds = (
            asr_seconds
            + post_seconds
            + (
                translation_seconds
                if translate_enabled
                else 0.0
            )
        )
        status = (
            "pass"
            if pipeline_seconds < 5.0
            else "warning"
        )
        emit(_item(
            "latency",
            "Pipeline latency",
            status,
            (
                f"Синтетический inference: {pipeline_seconds:.3f} сек. • "
                "цель < 5 сек. после отпускания PTT"
            ),
            pipeline_seconds,
        ))

    report = SelfTestReport(
        items=items,
        pipeline_seconds=pipeline_seconds,
    )

    try:
        save_self_test_report(report)
    except Exception:
        pass

    return report
