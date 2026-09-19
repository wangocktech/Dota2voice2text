import ctypes
import time
from ctypes import wintypes


# ============================================================
# WinAPI
# ============================================================

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MAPVK_VK_TO_VSC = 0

VK_RETURN = 0x0D
VK_SHIFT = 0x10


ULONG_PTR = wintypes.WPARAM


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)

    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]


user32.SendInput.argtypes = (
    wintypes.UINT,
    ctypes.POINTER(INPUT),
    ctypes.c_int,
)
user32.SendInput.restype = wintypes.UINT

user32.MapVirtualKeyW.argtypes = (
    wintypes.UINT,
    wintypes.UINT,
)
user32.MapVirtualKeyW.restype = wintypes.UINT


# ============================================================
# Low-level input
# ============================================================

def _send(inputs):
    if not inputs:
        return

    array_type = INPUT * len(inputs)
    array = array_type(*inputs)

    sent = user32.SendInput(
        len(inputs),
        array,
        ctypes.sizeof(INPUT),
    )

    if sent != len(inputs):
        error = ctypes.get_last_error()

        raise RuntimeError(
            f"SendInput отправил {sent}/{len(inputs)} событий. "
            f"WinError={error}. "
            f"Если Dota запущена от администратора, "
            f"запусти программу тоже от администратора."
        )


def _scan_input(vk: int, key_up: bool = False):
    scan = user32.MapVirtualKeyW(
        vk,
        MAPVK_VK_TO_VSC,
    )

    flags = KEYEVENTF_SCANCODE

    if key_up:
        flags |= KEYEVENTF_KEYUP

    return INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(
            wVk=0,
            wScan=scan,
            dwFlags=flags,
            time=0,
            dwExtraInfo=0,
        ),
    )


def press_key(vk: int):
    _send([
        _scan_input(vk, False),
        _scan_input(vk, True),
    ])


def hotkey(*keys: int):
    inputs = []

    for key in keys:
        inputs.append(
            _scan_input(key, False)
        )

    for key in reversed(keys):
        inputs.append(
            _scan_input(key, True)
        )

    _send(inputs)


def type_unicode(text: str):
    inputs = []

    # KEYEVENTF_UNICODE принимает UTF-16 code units
    encoded = text.encode(
        "utf-16-le",
        errors="surrogatepass",
    )

    for i in range(0, len(encoded), 2):
        code_unit = int.from_bytes(
            encoded[i:i + 2],
            "little",
        )

        inputs.append(
            INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(
                    wVk=0,
                    wScan=code_unit,
                    dwFlags=KEYEVENTF_UNICODE,
                    time=0,
                    dwExtraInfo=0,
                ),
            )
        )

        inputs.append(
            INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(
                    wVk=0,
                    wScan=code_unit,
                    dwFlags=(
                        KEYEVENTF_UNICODE
                        | KEYEVENTF_KEYUP
                    ),
                    time=0,
                    dwExtraInfo=0,
                ),
            )
        )

    _send(inputs)


# ============================================================
# Dota
# ============================================================

class DotaChatSender:
    def __init__(self, auto_send: bool = False):
        self.auto_send = auto_send

    @staticmethod
    def get_foreground_window_title() -> str:
        hwnd = user32.GetForegroundWindow()

        length = user32.GetWindowTextLengthW(hwnd)

        buffer = ctypes.create_unicode_buffer(
            length + 1
        )

        user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1,
        )

        return buffer.value

    def is_dota_foreground(self) -> bool:
        title = (
            self.get_foreground_window_title()
            .lower()
        )

        return "dota 2" in title or title == "dota"

    @staticmethod
    def _open_team_chat():
        press_key(VK_RETURN)

    @staticmethod
    def _open_all_chat():
        hotkey(
            VK_SHIFT,
            VK_RETURN,
        )

    def insert_text(
        self,
        text: str,
        chat_type: str,
    ):
        if not text:
            return False

        title = self.get_foreground_window_title()

        print(
            f'🪟 Активное окно: "{title}"'
        )

        if not self.is_dota_foreground():
            print(
                "⚠ Dota 2 сейчас не активна."
            )
            return False

        if chat_type == "team":
            print(
                "💬 Открываю командный чат..."
            )

            self._open_team_chat()

        elif chat_type == "all":
            print(
                "🌐 Открываю общий чат..."
            )

            self._open_all_chat()

        else:
            raise ValueError(
                f"Неизвестный тип чата: "
                f"{chat_type}"
            )

        # Dota должна успеть открыть поле ввода
        time.sleep(0.20)

        print(
            f"⌨️ Печатаю: {text}"
        )

        type_unicode(text)

        if self.auto_send:
            time.sleep(0.05)

            press_key(VK_RETURN)

            print(
                "✅ Сообщение отправлено."
            )
        else:
            print(
                "✅ Текст введён. "
                "Enter нажимаешь сам."
            )

        return True
