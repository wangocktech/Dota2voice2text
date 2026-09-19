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

    controller_ready = Signal(object)
    controller_error = Signal(str)

    def __init__(self):
        super().__init__()

        self.controller = None
        self.loading = False
        self.force_quit = False

        self.settings = load_settings()

        self.team_bind = self.settings[
            "team_bind"
        ]

        self.all_bind = self.settings[
            "all_bind"
        ]

        self.capture_target = None
        self.capture_mouse = None
        self.capture_keyboard = None

        self.setWindowTitle(
            "Dota2voice2text"
        )

        self.resize(
            540,
            470,
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

        self.controller_ready.connect(
            self._controller_loaded
        )

        self.controller_error.connect(
            self._controller_load_failed
        )

        self.build_ui()
        self.load_devices()
        self.setup_tray()

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
            "font-size: 25px;"
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
                self.settings.get(
                    "auto_send",
                    False,
                )
            )
        )

        form.addRow(
            "",
            self.auto_send,
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

        form.addRow(
            "",
            self.minimize_to_tray,
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

        self.status_label.setStyleSheet(
            "font-size: 14px;"
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
    # Tray
    # ========================================================

    def setup_tray(self):
        icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )

        self.tray = QSystemTrayIcon(
            icon,
            self,
        )

        self.tray.setToolTip(
            "Dota2voice2text"
        )

        menu = QMenu()

        show_action = QAction(
            "Открыть",
            self,
        )

        show_action.triggered.connect(
            self.show_from_tray
        )

        menu.addAction(
            show_action
        )

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

        menu.addAction(
            quit_action
        )

        self.tray.setContextMenu(
            menu
        )

        self.tray.activated.connect(
            self.tray_activated
        )

        self.tray.show()

    def tray_activated(
        self,
        reason,
    ):
        if reason == (
            QSystemTrayIcon.ActivationReason.DoubleClick
        ):
            self.show_from_tray()

    def show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

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
        if self.loading:
            return

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
                    self.auto_send
                    .isChecked(),

                on_status=
                    self.status_signal.emit,

                on_text=
                    self.text_signal.emit,
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

                "minimize_to_tray":
                    self.minimize_to_tray
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

     # ========================================================
    # Tray notifications
    # ========================================================

    def show_tray_notification(self):
        self.tray.showMessage(
            "Dota2voice2text",
            (
                "Программа свёрнута в системный трей "
                "и продолжает работать в фоне."
            ),
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    # ========================================================
    # Minimize
    # ========================================================

    def changeEvent(self, event):
        super().changeEvent(event)

        if event.type() != QEvent.Type.WindowStateChange:
            return

        if not self.isMinimized():
            return

        if not self.minimize_to_tray.isChecked():
            return

        # Даём Windows сначала обработать минимизацию,
        # потом скрываем окно из панели задач.
        self.hide()

        self.show_tray_notification()

    # ========================================================
    # Close
    # ========================================================

    def closeEvent(self, event):
        self.save_current_settings()

        # Галка включена:
        # X = спрятать в трей, но НЕ закрывать приложение.
        if (
            self.minimize_to_tray.isChecked()
            and not self.force_quit
        ):
            event.ignore()

            self.hide()

            self.show_tray_notification()

            return

        # Галка выключена:
        # X = полный выход.
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
