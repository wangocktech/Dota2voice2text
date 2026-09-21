import platform
import sys

from src.config.settings import (
    load_settings,
)
from src.input.hotkeys import (
    humanize_bind,
)
from src.text.translation_model_manager import (
    is_translation_model_installed,
    translation_model_size_bytes,
)
from src.utils.dota_status import (
    get_dota_state,
)
from src.utils.logging_setup import get_log_dir
from src.utils.health_check import evaluate_app_health
from src.version import APP_NAME, APP_VERSION


def build_diagnostics_text() -> str:
    if is_translation_model_installed():
        model_text = (
            "installed "
            f"({translation_model_size_bytes() / 1024 / 1024:.0f} MB)"
        )
    else:
        model_text = "not installed"

    settings = load_settings()

    team_bind = settings.get(
        "team_bind",
        "",
    )
    all_bind = settings.get(
        "all_bind",
        "",
    )

    bind_conflict = bool(
        team_bind
        and all_bind
        and team_bind == all_bind
    )

    try:
        dota = get_dota_state()

        if dota.foreground:
            dota_text = "foreground"
        elif dota.running:
            dota_text = "running, not foreground"
        else:
            dota_text = "not running"

    except Exception as exc:
        dota_text = f"status error: {exc}"

    device_key = settings.get(
        "device_key",
        "",
    ) or "not selected"


    health = evaluate_app_health(
        device=(
            {"key": device_key}
            if device_key != "not selected"
            else None
        ),
        team_bind=team_bind,
        all_bind=all_bind,
        translate_enabled=bool(
            settings.get(
                "translate_to_english",
                False,
            )
        ),
    )

    return "\n".join([
        f"{APP_NAME} v{APP_VERSION}",
        f"OS: {platform.platform()}",
        f"Python: {sys.version.split()[0]}",
        f"Dota 2: {dota_text}",
        f"Microphone: {device_key}",
        f"Team bind: {humanize_bind(team_bind)}",
        f"All bind: {humanize_bind(all_bind)}",
        f"Bind conflict: {'yes' if bind_conflict else 'no'}",
        f"Auto send: {bool(settings.get('auto_send', False))}",
        f"Translate RU->EN: {bool(settings.get('translate_to_english', False))}",
        f"Translation model: {model_text}",
        f"Health ready: {health.ready}",
        f"Health issues: {len(health.issues)}",
        f"Logs: {get_log_dir()}",
    ])
