import threading

from pynput import keyboard, mouse

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.audio.devices import get_input_devices
from src.config.autostart import set_autostart
from src.config.settings import load_settings, save_settings
from src.core.controller import VoiceController
from src.input.hotkeys import (
    humanize_bind,
    keyboard_to_bind,
    mouse_to_bind,
)
from src.version import APP_VERSION


STYLE = """
QWidget {
    background-color: #101216;
    color: #F2F3F5;
    font-family: "Segoe UI";
    font-size: 14px;
}

QMainWindow {
    background-color: #101216;
}

QLabel {
    background: transparent;
}

QLabel#title {
    font-size: 27px;
    font-weight: 700;
    color: #FFFFFF;
}

QLabel#subtitle {
    color: #9299A6;
    font-size: 13px;
}

QLabel#version {
    color: #9299A6;
    font-size: 12px;
}

QGroupBox {
    background-color: #171A20;
    border: 1px solid #2A2F39;
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 14px 12px 14px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 7px;
    background-color: #101216;
    color: #FFFFFF;
}

QComboBox {
    background-color: #20242C;
    color: #FFFFFF;
    border: 1px solid #343B47;
    border-radius: 7px;
    padding: 8px 36px 8px 10px;
    min-height: 26px;
}

QComboBox:hover {
    border-color: #5865F2;
}

QComboBox:focus {
    border-color: #5865F2;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;

    width: 32px;

    background-color: transparent;

    border: none;
    border-left: 1px solid #343B47;

    border-top-right-radius: 7px;
    border-bottom-right-radius: 7px;
}

QComboBox::down-arrow {
    image: url("assets/icons/chevron-down.svg");
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #20242C;
    color: #FFFFFF;
    border: 1px solid #343B47;
    selection-background-color: #5865F2;
    selection-color: #FFFFFF;
}

QPushButton {
    background-color: #20242C;
    color: #FFFFFF;
    border: 1px solid #343B47;
    border-radius: 7px;
    padding: 8px 12px;
    min-height: 26px;
}

QPushButton:hover {
    background-color: #292E38;
    border-color: #5865F2;
}

QPushButton:pressed {
    background-color: #1B1F26;
}

QPushButton:disabled {
    background-color: #191C22;
    color: #707681;
    border-color: #252A32;
}

QPushButton#startButton {
    background-color: #5865F2;
    border: none;
    border-radius: 9px;
    min-height: 36px;
    font-size: 15px;
    font-weight: 600;
}

QPushButton#startButton:hover {
    background-color: #6874F5;
}

QPushButton#startButton:pressed {
    background-color: #4752C4;
}

QCheckBox {
    background: transparent;
    color: #F2F3F5;
    spacing: 9px;
    padding: 3px 0;
    min-height: 20px;
}

QLabel#lastText {
    background-color: #20242C;
    border: 1px solid #303641;
    border-radius: 8px;
    padding: 12px;
    min-height: 38px;
}

QLabel#timing {
    color: #9299A6;
    font-size: 13px;
}

QMenu {
    background-color: #1B1F26;
    color: #FFFFFF;
    border: 1px solid #303641;
    padding: 5px;
}

QMenu::item {
    padding: 8px 26px 8px 10px;
    border-radius: 5px;
}

QMenu::item:selected {
    background-color: #5865F2;
}
"""


class MainWindow(QMainWindow):
    status_signal = Signal(str)
    text_signal = Signal(str)
    timing_signal = Signal(float)

    bind_signal = Signal(str, str)

    controller_ready = Signal(object)
    controller_error = Signal(str)

    def __init__(self, start_hidden=False):
        super().__init__()

        self.controller = None
        self.loading = False
        self.force_quit = False

        self.settings = load_settings()

        self.team_bind = self.settings.get(
            "team_bind",
            "mouse:x2",
        )

        self.all_bind = self.settings.get(
            "all_bind",
            "mouse:x1",
        )

        self.capture_target = None
        self.capture_mouse = None
        self.capture_keyboard = None

        self.setWindowTitle(
            f"Dota2voice2text v{APP_VERSION}"
        )

        self.resize(720, 790)
        self.setMinimumSize(680, 720)

        self.setStyleSheet(STYLE)

        self.status_signal.connect(
            self.set_status
        )

        self.text_signal.connect(
            self.set_last_text
        )

        self.timing_signal.connect(
            self.set_timing
        )

        self.bind_signal.connect(
            self._finish_bind_capture
        )

        self.controller_ready.connect(
            self._controller_loaded
        )

        self.controller_error.connect(
            self._controller_load_failed
        )

        self.build_ui()
        self.load_devices()
        self.setup_tray()

        self.start_hidden = (
            start_hidden
            or (
                self.settings.get(
                    "start_minimized",
                    False,
                )
                and self.settings.get(
                    "minimize_to_tray",
                    True,
                )
            )
        )

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):
        root = QWidget()

        layout = QVBoxLayout(root)

        layout.setContentsMargins(
            24,
            20,
            24,
            20,
        )

        layout.setSpacing(14)

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        header = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title = QLabel(
            "Dota2voice2text"
        )
        title.setObjectName("title")

        subtitle = QLabel(
            "Голос → текст → Dota 2"
        )
        subtitle.setObjectName(
            "subtitle"
        )

        version = QLabel(
            f"v{APP_VERSION}"
        )
        version.setObjectName(
            "version"
        )

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header.addLayout(title_layout)
        header.addStretch()
        header.addWidget(version)

        layout.addLayout(header)

        # ----------------------------------------------------
        # Основные настройки
        # ----------------------------------------------------

        settings_box = QGroupBox(
            "Основные настройки"
        )

        form = QFormLayout()

        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        form.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        self.device_combo = QComboBox()

        self.refresh_button = QPushButton(
            "Обновить"
        )

        self.refresh_button.setFixedWidth(
            100
        )

        self.refresh_button.clicked.connect(
            self.load_devices
        )

        device_row = QHBoxLayout()
        device_row.setSpacing(8)

        device_row.addWidget(
            self.device_combo,
            1,
        )

        device_row.addWidget(
            self.refresh_button,
        )

        form.addRow(
            "Микрофон:",
            device_row,
        )

        self.team_button = QPushButton(
            humanize_bind(
                self.team_bind
            )
        )

        self.team_button.clicked.connect(
            lambda: self.capture_bind(
                "team"
            )
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
            lambda: self.capture_bind(
                "all"
            )
        )

        form.addRow(
            "Общий чат:",
            self.all_button,
        )

        settings_box.setLayout(form)

        layout.addWidget(settings_box)

        # ----------------------------------------------------
        # Поведение
        # ----------------------------------------------------

        behavior_box = QGroupBox(
            "Поведение"
        )

        behavior_layout = QVBoxLayout()

        behavior_layout.setContentsMargins(
            10,
            8,
            10,
            8,
        )

        behavior_layout.setSpacing(5)

        self.auto_send = QCheckBox(
            "Автоматически отправлять сообщение"
        )

        self.auto_send.setChecked(
            bool(
                self.settings.get(
                    "auto_send",
                    False,
                )
            )
        )

        self.translate_to_english = QCheckBox(
            "Автоматически переводить на английский"
        )

        self.translate_to_english.setChecked(
            bool(
                self.settings.get(
                    "translate_to_english",
                    False,
                )
            )
        )

        self.minimize_to_tray = QCheckBox(
            "Сворачивать в системный трей"
        )

        self.minimize_to_tray.setChecked(
            bool(
                self.settings.get(
                    "minimize_to_tray",
                    True,
                )
            )
        )

        self.show_notifications = QCheckBox(
            "Показывать системные уведомления"
        )

        self.show_notifications.setChecked(
            bool(
                self.settings.get(
                    "show_notifications",
                    True,
                )
            )
        )

        self.autostart = QCheckBox(
            "Запускать вместе с Windows"
        )

        self.autostart.setChecked(
            bool(
                self.settings.get(
                    "autostart",
                    False,
                )
            )
        )

        self.start_minimized = QCheckBox(
            "При запуске сразу сворачивать в трей"
        )

        self.start_minimized.setChecked(
            bool(
                self.settings.get(
                    "start_minimized",
                    False,
                )
            )
        )

        behavior_layout.addWidget(
            self.auto_send
        )

        behavior_layout.addWidget(
            self.translate_to_english
        )

        behavior_layout.addWidget(
            self.minimize_to_tray
        )

        behavior_layout.addWidget(
            self.show_notifications
        )

        behavior_layout.addWidget(
            self.autostart
        )

        behavior_layout.addWidget(
            self.start_minimized
        )

        behavior_box.setLayout(
            behavior_layout
        )

        layout.addWidget(
            behavior_box
        )

        # ----------------------------------------------------
        # Start
        # ----------------------------------------------------

        self.start_button = QPushButton(
            "Запустить"
        )

        self.start_button.setObjectName(
            "startButton"
        )

        self.start_button.clicked.connect(
            self.toggle
        )

        layout.addWidget(
            self.start_button
        )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        self.status_label = QLabel(
            "● Остановлено"
        )

        self.status_label.setStyleSheet(
            "color: #9AA0AA;"
            "font-weight: 600;"
        )

        layout.addWidget(
            self.status_label
        )

        # ----------------------------------------------------
        # Последнее сообщение
        # ----------------------------------------------------

        last_box = QGroupBox(
            "Последнее сообщение"
        )

        last_layout = QVBoxLayout()

        last_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        last_layout.setSpacing(8)

        self.last_text = QLabel(
            "—"
        )

        self.last_text.setObjectName(
            "lastText"
        )

        self.last_text.setWordWrap(
            True
        )

        self.timing_label = QLabel(
            "Обработка: —"
        )

        self.timing_label.setObjectName(
            "timing"
        )

        last_layout.addWidget(
            self.last_text
        )

        last_layout.addWidget(
            self.timing_label
        )

        last_box.setLayout(
            last_layout
        )

        layout.addWidget(
            last_box
        )

        self.setCentralWidget(root)

    # ========================================================
    # Devices
    # ========================================================

    def load_devices(self):
        old = self.device_combo.currentData()

        saved_key = (
            old.get("key")
            if old
            else self.settings.get(
                "device_key",
                "",
            )
        )

        self.device_combo.clear()

        devices = get_input_devices()

        selected = -1

        for position, device in enumerate(
            devices
        ):
            device_key = (
                f'{device["name"]}|'
                f'{device["sample_rate"]}'
            )

            label = device["name"]

            if device.get(
                "default",
                False,
            ):
                label += " (по умолчанию)"

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

    def capture_bind(self, target):
        if (
            self.controller is not None
            or self.loading
        ):
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

        bind = mouse_to_bind(button)

        if bind:
            self.bind_signal.emit(
                self.capture_target,
                bind,
            )

    def _capture_key(self, key):
        bind = keyboard_to_bind(key)

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
    # Controller
    # ========================================================

    def toggle(self):
        if self.loading:
            return

        if self.controller is None:
            self.start_controller()
        else:
            self.stop_controller()

    def start_controller(self):
        if self.team_bind == self.all_bind:
            self.set_status(
                "Ошибка: бинды совпадают"
            )
            return

        device = (
            self.device_combo.currentData()
        )

        if not device:
            self.set_status(
                "Ошибка: микрофон не выбран"
            )
            return

        self.save_current_settings()

        self.loading = True

        self.set_controls_enabled(
            False
        )

        self.start_button.setEnabled(
            False
        )

        self.start_button.setText(
            "Загрузка моделей..."
        )

        self.set_status(
            "Загрузка моделей..."
        )

        threading.Thread(
            target=self._load_controller_worker,
            args=(device,),
            daemon=True,
        ).start()

    def _load_controller_worker(
        self,
        device,
    ):
        try:
            controller = VoiceController(
                device_index=
                    device["index"],

                team_bind=
                    self.team_bind,

                all_bind=
                    self.all_bind,

                auto_send=
                    self.auto_send.isChecked(),

                translate_to_english=
                    self.translate_to_english.isChecked(),

                on_status=
                    self.status_signal.emit,

                on_text=
                    self.text_signal.emit,

                on_timing=
                    self.timing_signal.emit,
            )

            self.controller_ready.emit(
                controller
            )

        except Exception as exc:
            self.controller_error.emit(
                str(exc)
            )

    def _controller_loaded(
        self,
        controller,
    ):
        self.loading = False
        self.controller = controller

        self.controller.start()

        self.start_button.setEnabled(
            True
        )

        self.start_button.setText(
            "Остановить"
        )

        self.tray_toggle_action.setText(
            "Остановить"
        )

    def _controller_load_failed(
        self,
        error,
    ):
        self.loading = False
        self.controller = None

        self.set_controls_enabled(
            True
        )

        self.start_button.setEnabled(
            True
        )

        self.start_button.setText(
            "Запустить"
        )

        self.set_status(
            f"Ошибка: {error}"
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

        self.tray_toggle_action.setText(
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

        self.refresh_button.setEnabled(
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

        self.translate_to_english.setEnabled(
            enabled
        )

    # ========================================================
    # Status
    # ========================================================

    def set_status(self, text):
        lower = text.lower()

        if "слушаю" in lower:
            color = "#FF5252"

        elif (
            "распозна" in lower
            or "перевожу" in lower
        ):
            color = "#FFB74D"

        elif "ошибка" in lower:
            color = "#FF5252"

        elif "готов" in lower:
            color = "#66BB6A"

        else:
            color = "#9AA0AA"

        self.status_label.setText(
            f"● {text}"
        )

        self.status_label.setStyleSheet(
            f"color: {color};"
            "font-weight: 600;"
        )

    def set_last_text(self, text):
        self.last_text.setText(text)

    def set_timing(self, seconds):
        self.timing_label.setText(
            f"Обработка: {seconds:.3f} сек."
        )

    # ========================================================
    # Settings
    # ========================================================

    def save_current_settings(self):
        device = (
            self.device_combo.currentData()
        )

        settings = {
            "device_key":
                device["key"]
                if device
                else "",

            "team_bind":
                self.team_bind,

            "all_bind":
                self.all_bind,

            "auto_send":
                self.auto_send.isChecked(),

            "translate_to_english":
                self.translate_to_english
                .isChecked(),

            "minimize_to_tray":
                self.minimize_to_tray
                .isChecked(),

            "show_notifications":
                self.show_notifications
                .isChecked(),

            "autostart":
                self.autostart.isChecked(),

            "start_minimized":
                self.start_minimized
                .isChecked(),
        }

        save_settings(settings)

        set_autostart(
            settings["autostart"]
        )

    # ========================================================
    # Tray
    # ========================================================

    def setup_tray(self):
        icon = self.style().standardIcon(
            QStyle.StandardPixmap
            .SP_ComputerIcon
        )

        self.tray = QSystemTrayIcon(
            icon,
            self,
        )

        self.tray.setToolTip(
            "Dota2voice2text"
        )

        menu = QMenu()

        open_action = QAction(
            "Открыть",
            self,
        )

        open_action.triggered.connect(
            self.show_from_tray
        )

        menu.addAction(open_action)

        self.tray_toggle_action = QAction(
            "Запустить",
            self,
        )

        self.tray_toggle_action.triggered.connect(
            self.toggle
        )

        menu.addAction(
            self.tray_toggle_action
        )

        menu.addSeparator()

        quit_action = QAction(
            "Выход",
            self,
        )

        quit_action.triggered.connect(
            self.quit_application
        )

        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

        self.tray.activated.connect(
            self.tray_activated
        )

        self.tray.show()

    def tray_activated(
        self,
        reason,
    ):
        if reason == (
            QSystemTrayIcon
            .ActivationReason
            .DoubleClick
        ):
            self.show_from_tray()

    def show_from_tray(self):
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def show_tray_notification(
        self,
        message,
    ):
        if not (
            self.show_notifications
            .isChecked()
        ):
            return

        self.tray.showMessage(
            "Dota2voice2text",
            message,
            QSystemTrayIcon
            .MessageIcon
            .Information,
            3000,
        )

    # ========================================================
    # Window behavior
    # ========================================================

    def changeEvent(self, event):
        super().changeEvent(event)

        if event.type() != (
            QEvent.Type.WindowStateChange
        ):
            return

        if not self.isMinimized():
            return

        if not (
            self.minimize_to_tray
            .isChecked()
        ):
            return

        self.hide()

        self.show_tray_notification(
            "Программа свёрнута в системный трей "
            "и продолжает работать в фоне."
        )

    def closeEvent(self, event):
        self.save_current_settings()

        if (
            self.minimize_to_tray
            .isChecked()
            and not self.force_quit
        ):
            event.ignore()
            self.hide()

            self.show_tray_notification(
                "Программа свёрнута в системный трей "
                "и продолжает работать в фоне."
            )

            return

        if self.controller:
            self.controller.stop()
            self.controller = None

        self.tray.hide()

        event.accept()

        QApplication.instance().quit()

    def quit_application(self):
        self.force_quit = True

        self.save_current_settings()

        if self.controller:
            self.controller.stop()
            self.controller = None

        self.tray.hide()

        QApplication.instance().quit()
