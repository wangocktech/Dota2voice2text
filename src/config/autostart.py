import subprocess
import sys
import winreg
from pathlib import Path

from src.version import APP_NAME


RUN_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Run"
)


def get_startup_command():
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)

        return (
            f'"{executable}" --minimized'
        )

    pythonw = (
        Path(sys.executable)
        .with_name("pythonw.exe")
    )

    app_file = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "app.py"
    )

    return (
        f'"{pythonw}" "{app_file}" --minimized'
    )


def set_autostart(enabled: bool):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    )

    try:
        if enabled:
            winreg.SetValueEx(
                key,
                APP_NAME,
                0,
                winreg.REG_SZ,
                get_startup_command(),
            )
        else:
            try:
                winreg.DeleteValue(
                    key,
                    APP_NAME,
                )
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def is_autostart_enabled():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_READ,
        )

        try:
            winreg.QueryValueEx(
                key,
                APP_NAME,
            )

            return True

        finally:
            winreg.CloseKey(key)

    except FileNotFoundError:
        return False
