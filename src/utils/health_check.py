from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.input.hotkeys import humanize_bind
from src.text.translation_model_manager import (
    is_translation_model_installed,
)
from src.utils.dota_status import get_dota_state
from src.utils.paths import resource_path


@dataclass
class HealthIssue:
    level: str
    title: str
    detail: str


@dataclass
class HealthReport:
    ready: bool
    summary: str
    issues: list[HealthIssue]

    @property
    def blockers(self) -> list[HealthIssue]:
        return [
            issue
            for issue in self.issues
            if issue.level == "error"
        ]

    @property
    def warnings(self) -> list[HealthIssue]:
        return [
            issue
            for issue in self.issues
            if issue.level == "warning"
        ]


RISKY_BINDS = {
    "key:esc": "Esc часто используется для закрытия меню.",
    "key:enter": "Enter используется для отправки сообщения в чат.",
    "key:tab": "Tab часто используется для таблицы счёта.",
    "key:shift": "Shift используется во многих игровых действиях.",
    "key:shift_l": "Left Shift используется во многих игровых действиях.",
    "key:shift_r": "Right Shift используется во многих игровых действиях.",
    "key:ctrl": "Ctrl используется во многих игровых действиях.",
    "key:ctrl_l": "Left Ctrl используется во многих игровых действиях.",
    "key:ctrl_r": "Right Ctrl используется во многих игровых действиях.",
    "key:alt": "Alt используется во многих игровых действиях.",
    "key:alt_l": "Left Alt используется во многих игровых действиях.",
    "key:alt_r": "Right Alt используется во многих игровых действиях.",
    "key:space": "Space часто занят управлением камерой/предметами.",
}


def _core_model_issues() -> list[HealthIssue]:
    required = [
        (
            resource_path(
                "models/sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19/model.int8.onnx"
            ),
            "GigaAM model.int8.onnx",
        ),
        (
            resource_path(
                "models/sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19/tokens.txt"
            ),
            "GigaAM tokens.txt",
        ),
        (
            resource_path(
                "models/rupunct-small-onnx/rupunct_small_int8.onnx"
            ),
            "RUPunct model",
        ),
        (
            resource_path(
                "models/rupunct-small-onnx/tokenizer.json"
            ),
            "RUPunct tokenizer",
        ),
        (
            resource_path(
                "models/rupunct-small-onnx/config.json"
            ),
            "RUPunct config",
        ),
    ]

    issues = []

    for path, label in required:
        if not Path(path).exists():
            issues.append(
                HealthIssue(
                    level="error",
                    title=f"Не найден {label}",
                    detail=str(path),
                )
            )

    return issues


def _bind_warning(
    label: str,
    bind: str,
) -> HealthIssue | None:
    detail = RISKY_BINDS.get(bind)

    if not detail:
        return None

    return HealthIssue(
        level="warning",
        title=(
            f"{label}: "
            f"{humanize_bind(bind)} может конфликтовать"
        ),
        detail=detail,
    )


def evaluate_app_health(
    *,
    device: dict | None,
    team_bind: str,
    all_bind: str,
    translate_enabled: bool,
) -> HealthReport:
    issues: list[HealthIssue] = []

    if not device:
        issues.append(
            HealthIssue(
                level="error",
                title="Микрофон не выбран",
                detail="Выбери устройство ввода в основных настройках.",
            )
        )

    if not team_bind:
        issues.append(
            HealthIssue(
                level="error",
                title="Не назначен Team Chat bind",
                detail="Назначь кнопку командного чата.",
            )
        )

    if not all_bind:
        issues.append(
            HealthIssue(
                level="error",
                title="Не назначен All Chat bind",
                detail="Назначь кнопку общего чата.",
            )
        )

    if (
        team_bind
        and all_bind
        and team_bind == all_bind
    ):
        issues.append(
            HealthIssue(
                level="error",
                title="Team Chat и All Chat используют одну кнопку",
                detail="Назначь разные кнопки.",
            )
        )

    for label, bind in (
        ("Team Chat", team_bind),
        ("All Chat", all_bind),
    ):
        warning = _bind_warning(label, bind)

        if warning is not None:
            issues.append(warning)

    issues.extend(_core_model_issues())

    if (
        translate_enabled
        and not is_translation_model_installed()
    ):
        issues.append(
            HealthIssue(
                level="warning",
                title="Модель RU → EN ещё не установлена",
                detail=(
                    "Она будет предложена к скачиванию "
                    "при запуске распознавания."
                ),
            )
        )

    try:
        dota = get_dota_state()

        if not dota.running:
            issues.append(
                HealthIssue(
                    level="warning",
                    title="Dota 2 не запущена",
                    detail=(
                        "Распознавание можно запустить заранее, "
                        "но текст отправится только в активное окно Dota 2."
                    ),
                )
            )
        elif not dota.foreground:
            issues.append(
                HealthIssue(
                    level="warning",
                    title="Dota 2 сейчас не активна",
                    detail=(
                        "Перед голосовой командой переключись "
                        "в окно Dota 2."
                    ),
                )
            )

    except Exception as exc:
        issues.append(
            HealthIssue(
                level="warning",
                title="Не удалось проверить статус Dota 2",
                detail=str(exc),
            )
        )

    blockers = [
        issue
        for issue in issues
        if issue.level == "error"
    ]

    warnings = [
        issue
        for issue in issues
        if issue.level == "warning"
    ]

    ready = not blockers

    if blockers:
        summary = (
            f"Не готово: {len(blockers)} "
            "критическая проблема"
            if len(blockers) == 1
            else f"Не готово: {len(blockers)} критических проблем"
        )
    elif warnings:
        summary = (
            f"Готово с предупреждениями: {len(warnings)}"
        )
    else:
        summary = "Всё готово"

    return HealthReport(
        ready=ready,
        summary=summary,
        issues=issues,
    )


def format_health_report(report: HealthReport) -> str:
    if not report.issues:
        return (
            "✅ Всё готово.\n\n"
            "Микрофон, бинды и локальные модели "
            "выглядят корректно."
        )

    lines = []

    for issue in report.issues:
        prefix = (
            "❌"
            if issue.level == "error"
            else "⚠"
        )

        lines.append(
            f"{prefix} {issue.title}"
        )

        if issue.detail:
            lines.append(
                f"   {issue.detail}"
            )

    return "\n".join(lines)
