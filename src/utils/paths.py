import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]

    return base / relative_path
