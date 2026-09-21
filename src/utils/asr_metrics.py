from __future__ import annotations

import json
import os
from pathlib import Path


APP_DIR = Path(
    os.getenv(
        "LOCALAPPDATA",
        os.getenv("APPDATA", Path.home()),
    )
) / "Dota2voice2text"

ASR_METRICS_FILE = APP_DIR / "asr_latest.json"


def save_asr_metrics(data: dict) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        ASR_METRICS_FILE.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_asr_metrics() -> dict:
    if not ASR_METRICS_FILE.exists():
        return {}

    try:
        data = json.loads(
            ASR_METRICS_FILE.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}
