import json
import os
import re
from pathlib import Path


APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "Dota2voice2text"
CUSTOM_DICTIONARY_FILE = APP_DIR / "custom_dictionary.json"


def load_custom_dictionary() -> dict[str, str]:
    if not CUSTOM_DICTIONARY_FILE.exists():
        return {}

    try:
        data = json.loads(CUSTOM_DICTIONARY_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    result = {}
    for source, target in data.items():
        source = str(source).strip()
        target = str(target).strip()
        if source and target:
            result[source] = target
    return result


def save_custom_dictionary(entries: dict[str, str]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)

    clean = {
        str(source).strip(): str(target).strip()
        for source, target in entries.items()
        if str(source).strip() and str(target).strip()
    }

    CUSTOM_DICTIONARY_FILE.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def apply_custom_dictionary(text: str, entries: dict[str, str]) -> str:
    result = text

    for source, target in sorted(
        entries.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = r"(?<!\w)" + re.escape(source) + r"(?!\w)"
        result = re.sub(pattern, target, result, flags=re.IGNORECASE)

    return result
