import json
import os
from pathlib import Path


APP_DIR = (
    Path(
        os.getenv(
            "APPDATA",
            Path.home(),
        )
    )
    / "Dota2voice2text"
)

CONFIG_FILE = APP_DIR / "config.json"


DEFAULT_SETTINGS = {
    "device_key": "",
    "team_bind": "mouse:x2",
    "all_bind": "mouse:x1",

    "auto_send": False,

    "minimize_to_tray": True,
    "show_notifications": True,

    "autostart": False,
    "start_minimized": False,
}


def load_settings():
    if not CONFIG_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        data = json.loads(
            CONFIG_FILE.read_text(
                encoding="utf-8"
            )
        )

        settings = DEFAULT_SETTINGS.copy()
        settings.update(data)

        return settings

    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    APP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CONFIG_FILE.write_text(
        json.dumps(
            settings,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
