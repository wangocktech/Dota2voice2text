from pynput import keyboard, mouse


def mouse_to_bind(button):
    mapping = {
        mouse.Button.x1: "mouse:x1",
        mouse.Button.x2: "mouse:x2",
        mouse.Button.middle: "mouse:middle",
    }

    return mapping.get(button)


def keyboard_to_bind(key):
    char = getattr(key, "char", None)

    if char:
        return f"key:{char.lower()}"

    name = getattr(key, "name", None)

    if name:
        return f"key:{name}"

    vk = getattr(key, "vk", None)

    if vk is not None:
        return f"vk:{vk}"

    return None


def humanize_bind(bind):
    if not bind:
        return "Не назначено"

    mouse_names = {
        "mouse:x1": "MOUSE4",
        "mouse:x2": "MOUSE5",
        "mouse:middle": "MOUSE3",
    }

    if bind in mouse_names:
        return mouse_names[bind]

    special_keys = {
        "shift": "Shift",
        "shift_l": "Left Shift",
        "shift_r": "Right Shift",
        "ctrl": "Ctrl",
        "ctrl_l": "Left Ctrl",
        "ctrl_r": "Right Ctrl",
        "alt": "Alt",
        "alt_l": "Left Alt",
        "alt_r": "Right Alt",
        "space": "Space",
        "tab": "Tab",
        "caps_lock": "Caps Lock",
        "f1": "F1",
        "f2": "F2",
        "f3": "F3",
        "f4": "F4",
        "f5": "F5",
        "f6": "F6",
        "f7": "F7",
        "f8": "F8",
        "f9": "F9",
        "f10": "F10",
        "f11": "F11",
        "f12": "F12",
    }

    if bind.startswith("key:"):
        key = bind[4:]
        return special_keys.get(key, key.upper())

    if bind.startswith("vk:"):
        return bind.upper()

    return bind


class GlobalPTTListener:
    def __init__(self, callback):
        self.callback = callback

        self.mouse_listener = None
        self.keyboard_listener = None

    def start(self):
        if self.mouse_listener is not None:
            return

        self.mouse_listener = mouse.Listener(
            on_click=self._on_mouse
        )

        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )

        self.mouse_listener.start()
        self.keyboard_listener.start()

    def stop(self):
        if self.mouse_listener is not None:
            self.mouse_listener.stop()
            self.mouse_listener = None

        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

    def _on_mouse(
        self,
        x,
        y,
        button,
        pressed,
    ):
        bind = mouse_to_bind(button)

        if bind:
            self.callback(
                bind,
                pressed,
            )

    def _on_key_press(self, key):
        bind = keyboard_to_bind(key)

        if bind:
            self.callback(
                bind,
                True,
            )

    def _on_key_release(self, key):
        bind = keyboard_to_bind(key)

        if bind:
            self.callback(
                bind,
                False,
            )
