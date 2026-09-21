import json
import os
from datetime import datetime
from pathlib import Path


APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "Dota2voice2text"
HISTORY_FILE = APP_DIR / "history.json"
MAX_HISTORY = 50


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)][-MAX_HISTORY:]


def add_history_entry(text: str, total_time: float) -> None:
    text = str(text).strip()
    if not text:
        return

    history = load_history()
    history.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "text": text,
        "total_time": round(float(total_time), 4),
    })

    APP_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_history() -> None:
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
