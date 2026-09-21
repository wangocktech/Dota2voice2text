from pathlib import Path

from PySide6.QtGui import QIcon

from src.utils.paths import resource_path


def get_app_icon_path() -> str:
    ico = Path(resource_path("assets/icons/app_icon.ico"))
    png = Path(resource_path("assets/icons/app_icon.png"))

    if ico.exists():
        return str(ico)

    return str(png)


def get_app_icon() -> QIcon:
    return QIcon(get_app_icon_path())
