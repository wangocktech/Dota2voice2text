import ctypes
import sys


APP_USER_MODEL_ID = "wangocktech.Dota2voice2text"


def configure_windows_app() -> None:
    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except Exception:
        pass
