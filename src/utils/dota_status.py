import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass


TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

DOTA_PROCESS_NAMES = {
    "dota2.exe",
    "dota.exe",
}


@dataclass(frozen=True)
class DotaState:
    running: bool
    foreground: bool
    foreground_title: str

    @property
    def text(self) -> str:
        if self.foreground:
            return "Dota 2 активна"
        if self.running:
            return "Dota 2 запущена, но не активна"
        return "Dota 2 не запущена"


if sys.platform == "win32":
    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )
    user32 = ctypes.WinDLL(
        "user32",
        use_last_error=True,
    )

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.argtypes = (
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.CreateToolhelp32Snapshot.restype = (
        wintypes.HANDLE
    )

    kernel32.Process32FirstW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    )
    kernel32.Process32FirstW.restype = wintypes.BOOL

    kernel32.Process32NextW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    )
    kernel32.Process32NextW.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = (
        wintypes.HANDLE,
    )
    kernel32.CloseHandle.restype = wintypes.BOOL


def get_foreground_window_title() -> str:
    if sys.platform != "win32":
        return ""

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return ""

    length = user32.GetWindowTextLengthW(
        hwnd
    )

    if length <= 0:
        return ""

    buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1,
    )

    return buffer.value.strip()


def is_dota_foreground() -> bool:
    title = (
        get_foreground_window_title()
        .lower()
    )

    return (
        "dota 2" in title
        or title == "dota"
    )


def is_dota_running() -> bool:
    if sys.platform != "win32":
        return False

    snapshot = (
        kernel32.CreateToolhelp32Snapshot(
            TH32CS_SNAPPROCESS,
            0,
        )
    )

    if (
        snapshot is None
        or snapshot == INVALID_HANDLE_VALUE
    ):
        return False

    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(
            PROCESSENTRY32W
        )

        ok = kernel32.Process32FirstW(
            snapshot,
            ctypes.byref(entry),
        )

        while ok:
            name = (
                entry.szExeFile
                .lower()
            )

            if name in DOTA_PROCESS_NAMES:
                return True

            ok = kernel32.Process32NextW(
                snapshot,
                ctypes.byref(entry),
            )

        return False

    finally:
        kernel32.CloseHandle(
            snapshot
        )


def get_dota_state() -> DotaState:
    title = get_foreground_window_title()
    foreground = is_dota_foreground()

    if foreground:
        running = True
    else:
        running = is_dota_running()

    return DotaState(
        running=running,
        foreground=foreground,
        foreground_title=title,
    )
