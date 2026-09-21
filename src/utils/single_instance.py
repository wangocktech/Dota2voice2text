import ctypes
import sys
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
SW_SHOW = 5
SW_RESTORE = 9

MUTEX_NAME = r"Local\wangocktech.Dota2voice2text.SingleInstance"
WINDOW_TITLE_PREFIX = "Dota2voice2text"


class SingleInstanceGuard:
    def __init__(self) -> None:
        self._handle = None
        self.already_running = False

        if sys.platform != "win32":
            return

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]

        kernel32.SetLastError(0)

        self._handle = kernel32.CreateMutexW(
            None,
            False,
            MUTEX_NAME,
        )

        if not self._handle:
            raise ctypes.WinError()

        self.already_running = (
            kernel32.GetLastError()
            == ERROR_ALREADY_EXISTS
        )

    def close(self) -> None:
        if (
            sys.platform == "win32"
            and self._handle
        ):
            try:
                ctypes.windll.kernel32.CloseHandle(
                    self._handle
                )
            finally:
                self._handle = None


def activate_existing_instance() -> bool:
    if sys.platform != "win32":
        return False

    user32 = ctypes.windll.user32

    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    found = {"hwnd": 0}

    def enum_callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)

        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(
            length + 1
        )

        user32.GetWindowTextW(
            hwnd,
            buffer,
            len(buffer),
        )

        if buffer.value.startswith(
            WINDOW_TITLE_PREFIX
        ):
            found["hwnd"] = int(hwnd)
            return False

        return True

    callback = enum_proc_type(enum_callback)

    user32.EnumWindows(
        callback,
        0,
    )

    hwnd = found["hwnd"]

    if not hwnd:
        return False

    if user32.IsIconic(hwnd):
        user32.ShowWindow(
            hwnd,
            SW_RESTORE,
        )
    else:
        user32.ShowWindow(
            hwnd,
            SW_SHOW,
        )

    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    return True
