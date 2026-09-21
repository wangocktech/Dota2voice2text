import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from src.utils.paths import resource_path


DOTA_PROCESS_NAMES = {
    "dota2.exe",
    "dota.exe",
}

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


if sys.platform == "win32":
    user32 = ctypes.WinDLL(
        "user32",
        use_last_error=True,
    )
    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )

    user32.GetForegroundWindow.restype = wintypes.HWND

    user32.GetWindowThreadProcessId.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    user32.IsWindowVisible.argtypes = (
        wintypes.HWND,
    )
    user32.IsWindowVisible.restype = wintypes.BOOL

    user32.IsIconic.argtypes = (
        wintypes.HWND,
    )
    user32.IsIconic.restype = wintypes.BOOL

    user32.GetClientRect.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.RECT),
    )
    user32.GetClientRect.restype = wintypes.BOOL

    user32.ClientToScreen.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.POINT),
    )
    user32.ClientToScreen.restype = wintypes.BOOL

    user32.SetWindowPos.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    )
    user32.SetWindowPos.restype = wintypes.BOOL

    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE

    kernel32.CloseHandle.argtypes = (
        wintypes.HANDLE,
    )
    kernel32.CloseHandle.restype = wintypes.BOOL

    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def _foreground_process_name() -> tuple[int, str]:
    if sys.platform != "win32":
        return 0, ""

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return 0, ""

    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(pid),
    )

    if not pid.value:
        return int(hwnd), ""

    process = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid.value,
    )

    if not process:
        return int(hwnd), ""

    try:
        buffer = ctypes.create_unicode_buffer(
            32768
        )
        size = wintypes.DWORD(
            len(buffer)
        )

        ok = kernel32.QueryFullProcessImageNameW(
            process,
            0,
            buffer,
            ctypes.byref(size),
        )

        if not ok:
            return int(hwnd), ""

        return (
            int(hwnd),
            os.path.basename(
                buffer.value
            ).lower(),
        )

    finally:
        kernel32.CloseHandle(
            process
        )


def get_foreground_dota_client_rect():
    """Return Dota client bounds in screen coordinates.

    The overlay is deliberately allowed only when the foreground process is
    dota2.exe/dota.exe. That guarantees the always-on-top indicator cannot
    leak over another application when Dota loses focus.
    """
    if sys.platform != "win32":
        return None

    hwnd, process_name = (
        _foreground_process_name()
    )

    if (
        not hwnd
        or process_name
        not in DOTA_PROCESS_NAMES
    ):
        return None

    hwnd_value = wintypes.HWND(hwnd)

    if not user32.IsWindowVisible(
        hwnd_value
    ):
        return None

    if user32.IsIconic(
        hwnd_value
    ):
        return None

    rect = wintypes.RECT()

    if not user32.GetClientRect(
        hwnd_value,
        ctypes.byref(rect),
    ):
        return None

    top_left = wintypes.POINT(
        rect.left,
        rect.top,
    )
    bottom_right = wintypes.POINT(
        rect.right,
        rect.bottom,
    )

    if not user32.ClientToScreen(
        hwnd_value,
        ctypes.byref(top_left),
    ):
        return None

    if not user32.ClientToScreen(
        hwnd_value,
        ctypes.byref(bottom_right),
    ):
        return None

    width = (
        bottom_right.x
        - top_left.x
    )
    height = (
        bottom_right.y
        - top_left.y
    )

    if width <= 0 or height <= 0:
        return None

    return (
        top_left.x,
        top_left.y,
        width,
        height,
    )


class DotaPttOverlay(QWidget):
    OVERLAY_SIZE = 64
    ICON_SIZE = 48
    RIGHT_MARGIN = 18

    def __init__(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        transparent_input = getattr(
            Qt.WindowType,
            "WindowTransparentForInput",
            None,
        )

        if transparent_input is not None:
            flags |= transparent_input

        super().__init__(
            None,
            flags,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.setFixedSize(
            self.OVERLAY_SIZE,
            self.OVERLAY_SIZE,
        )

        self._requested_visible = False
        self._chat_type = ""

        self._pixmap = QPixmap(
            str(
                resource_path(
                    "assets/icons/app_icon.png"
                )
            )
        )

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(
            self._sync_to_dota
        )

        self.hide()

    def set_ptt_active(
        self,
        active: bool,
        chat_type: str = "",
    ):
        self._requested_visible = bool(
            active
        )
        self._chat_type = (
            chat_type
            if active
            else ""
        )

        if self._requested_visible:
            if not self._timer.isActive():
                self._timer.start()

            self._sync_to_dota()
            return

        self.hide_overlay()

    def hide_overlay(self):
        self._requested_visible = False
        self._chat_type = ""
        self._timer.stop()
        self.hide()

    def _sync_to_dota(self):
        if not self._requested_visible:
            self.hide_overlay()
            return

        rect = (
            get_foreground_dota_client_rect()
        )

        if rect is None:
            self.hide()
            return

        left, top, width, height = rect

        x = (
            left
            + width
            - self.width()
            - self.RIGHT_MARGIN
        )
        y = (
            top
            + (
                height
                - self.height()
            ) // 2
        )

        self.move(x, y)

        if not self.isVisible():
            self.show()

        self._force_topmost()
        self.update()

    def _force_topmost(self):
        if sys.platform != "win32":
            return

        try:
            hwnd = wintypes.HWND(
                int(self.winId())
            )

            user32.SetWindowPos(
                hwnd,
                wintypes.HWND(
                    HWND_TOPMOST
                ),
                0,
                0,
                0,
                0,
                SWP_NOMOVE
                | SWP_NOSIZE
                | SWP_NOACTIVATE
                | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def paintEvent(self, event):
        del event

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        panel = QRectF(
            2.5,
            2.5,
            self.width() - 5.0,
            self.height() - 5.0,
        )

        painter.setPen(
            QPen(
                QColor(255, 255, 255, 45),
                1.0,
            )
        )
        painter.setBrush(
            QColor(12, 14, 18, 205)
        )
        painter.drawRoundedRect(
            panel,
            14.0,
            14.0,
        )

        if self._pixmap.isNull():
            return

        icon = self._pixmap.scaled(
            self.ICON_SIZE,
            self.ICON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = (
            self.width()
            - icon.width()
        ) // 2
        y = (
            self.height()
            - icon.height()
        ) // 2

        painter.drawPixmap(
            x,
            y,
            icon,
        )
