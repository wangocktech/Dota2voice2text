from pynput import keyboard, mouse

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.audio.devices import get_input_devices
from src.config.settings import (
    load_settings,
    save_settings,
)
from src.core.controller import VoiceController
from src.input.hotkeys import (
    humanize_bind,
    keyboard_to_bind,
    mouse_to_bind,
)


class MainWindow(QMainWindow):
    status_signal = Signal(str)
    text_signal = Signal(str)

    bind_signal = Signal(
        str,
        str,
    )

    def __init__(self):
        super().__init__()

        self.controller = None

        self.settings = (
            load_settings()
        )

        self.team_bind = (
            self.settings["team_bind"]
        )

        self.all_bind = (
            self.settings["all_bind"]
        )

        self.capture_target = None

        self.capture_mouse = None
        self.capture_keyboard = None

        self.setWindowTitle(
            "Dota2voice2text"
        )

        self.resize(
            520,
            430,
        )

        self.status_signal.connect(
            self.set_status
        )

        self.text_signal.connect(
            self.set_last_text
        )

        self.bind_signal.connect(
            self._finish_bind_capture
        )

        self.build_ui()
        self.load_devices()

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):
        root = QWidget()

        layout = QVBoxLayout(root)

        title = QLabel(
            "Dota2voice2text"
        )

        title.setStyleSheet(
            "font-size: 24px;"
            "font-weight: 700;"
        )

        subtitle = QLabel(
            "Голос → текст → Dota 2"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        settings_box = QGroupBox(
            "Настройки"
        )

        form = QFormLayout()

        self.device_combo = QComboBox()

        form.addRow(
            "Микрофон:",
            self.device_combo,
        )

        self.team_button = QPushButton(
            humanize_bind(
                self.team_bind
            )
        )

        self.team_button.clicked.connect(
            lambda:
            self.capture_bind("team")
        )

        form.addRow(
            "Командный чат:",
            self.team_button,
        )

        self.all_button = QPushButton(
            humanize_bind(
                self.all_bind
            )
        )

        self.all_button.clicked.connect(
            lambda:
            self.capture_bind("all")
        )

        form.addRow(
            "Общий чат:",
            self.all_button,
        )

        self.auto_send = QCheckBox(
            "Автоматически отправлять сообщение"
        )

        self.auto_send.setChecked(
            bool(
                self.settings[
                    "auto_send"
                ]
            )
        )

        form.addRow(
            "",
            self.auto_send,
        )

        settings_box.setLayout(form)

        layout.addWidget(
            settings_box
        )

        self.start_button = QPushButton(
            "Запустить"
        )

        self.start_button.setMinimumHeight(
            44
        )

        self.start_button.clicked.connect(
            self.toggle
        )

        layout.addWidget(
            self.start_button
        )

        self.status_label = QLabel(
            "Статус: Остановлено"
        )

        layout.addWidget(
            self.status_label
        )

        last_box = QGroupBox(
            "Последнее сообщение"
        )

        last_layout = QVBoxLayout()

        self.last_text = QLabel(
            "—"
        )

        self.last_text.setWordWrap(
            True
        )

        last_layout.addWidget(
            self.last_text
        )

        last_box.setLayout(
            last_layout
        )

        layout.addWidget(
            last_box
        )

        layout.addStretch()

        self.setCentralWidget(root)

    # ========================================================
    # Devices
    # ========================================================

    def load_devices(self):
        self.device_combo.clear()

        devices = get_input_devices()

        saved_key = self.settings.get(
            "device_key",
            "",
        )

        selected = -1

        for position, device in enumerate(
            devices
        ):
            device_key = (
                f'{device["name"]}|'
                f'{device["hostapi"]}|'
                f'{device["sample_rate"]}'
            )

            label = (
                f'{device["name"]} '
                f'[{device["hostapi"]}]'
            )

            self.device_combo.addItem(
                label,
                {
                    "index":
                        device["index"],

                    "key":
                        device_key,
                },
            )

            if device_key == saved_key:
                selected = position

        if selected >= 0:
            self.device_combo.setCurrentIndex(
                selected
            )

    # ========================================================
    # Bind capture
    # ========================================================

    def capture_bind(
        self,
        target,
    ):
        if self.controller is not None:
            return

        self.capture_target = target

        if target == "team":
            self.team_button.setText(
                "Нажмите кнопку..."
            )
        else:
            self.all_button.setText(
                "Нажмите кнопку..."
            )

        self.capture_mouse = mouse.Listener(
            on_click=self._capture_mouse
        )

        self.capture_keyboard = (
            keyboard.Listener(
                on_press=self._capture_key
            )
        )

        self.capture_mouse.start()
        self.capture_keyboard.start()

    def _capture_mouse(
        self,
        x,
        y,
        button,
        pressed,
    ):
        if not pressed:
            return

        bind = mouse_to_bind(
            button
        )

        if bind:
            self.bind_signal.emit(
                self.capture_target,
                bind,
            )

    def _capture_key(
        self,
        key,
    ):
        bind = keyboard_to_bind(
            key
        )

        if bind == "key:esc":
            self.bind_signal.emit(
                self.capture_target,
                "",
            )

            return False

        if bind:
            self.bind_signal.emit(
                self.capture_target,
                bind,
            )

            return False

    def _finish_bind_capture(
        self,
        target,
        bind,
    ):
        if self.capture_mouse:
            self.capture_mouse.stop()
            self.capture_mouse = None

        if self.capture_keyboard:
            self.capture_keyboard.stop()
            self.capture_keyboard = None

        if bind:
            if target == "team":
                self.team_bind = bind
            else:
                self.all_bind = bind

        self.team_button.setText(
            humanize_bind(
                self.team_bind
            )
        )

        self.all_button.setText(
            humanize_bind(
                self.all_bind
            )
        )

        self.capture_target = None

    # ========================================================
    # Start / Stop
    # ========================================================

    def toggle(self):
        if self.controller is None:
            self.start_controller()
        else:
            self.stop_controller()

    def start_controller(self):
        if (
            self.team_bind
            == self.all_bind
        ):
            self.set_status(
                "Бинды не могут совпадать"
            )
            return

        device = (
            self.device_combo.currentData()
        )

        if not device:
            self.set_status(
                "Микрофон не выбран"
            )
            return

        self.save_current_settings()

        self.set_status(
            "Загрузка моделей..."
        )

        try:
            self.controller = (
                VoiceController(
                    device_index=
                        device["index"],

                    team_bind=
                        self.team_bind,

                    all_bind=
                        self.all_bind,

                    auto_send=
                        self.auto_send
                        .isChecked(),

                    on_status=
                        self.status_signal.emit,

                    on_text=
                        self.text_signal.emit,
                )
            )

            self.controller.start()

            self.set_controls_enabled(
                False
            )

            self.start_button.setText(
                "Остановить"
            )

        except Exception as exc:
            self.controller = None

            self.set_status(
                f"Ошибка: {exc}"
            )

    def stop_controller(self):
        if self.controller:
            self.controller.stop()

        self.controller = None

        self.set_controls_enabled(
            True
        )

        self.start_button.setText(
            "Запустить"
        )

        self.set_status(
            "Остановлено"
        )

    def set_controls_enabled(
        self,
        enabled,
    ):
        self.device_combo.setEnabled(
            enabled
        )

        self.team_button.setEnabled(
            enabled
        )

        self.all_button.setEnabled(
            enabled
        )

        self.auto_send.setEnabled(
            enabled
        )

    # ========================================================
    # Settings
    # ========================================================

    def save_current_settings(self):
        device = (
            self.device_combo.currentData()
        )

        save_settings(
            {
                "device_key":
                    device["key"]
                    if device
                    else "",

                "team_bind":
                    self.team_bind,

                "all_bind":
                    self.all_bind,

                "auto_send":
                    self.auto_send
                    .isChecked(),
            }
        )

    # ========================================================
    # Status
    # ========================================================

    def set_status(
        self,
        text,
    ):
        self.status_label.setText(
            f"Статус: {text}"
        )

    def set_last_text(
        self,
        text,
    ):
        self.last_text.setText(
            text
        )

    def closeEvent(
        self,
        event,
    ):
        self.save_current_settings()

        if self.controller:
            self.controller.stop()

        event.accept()
