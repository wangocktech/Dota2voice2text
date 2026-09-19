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
from src.core.controller import VoiceController


class MainWindow(QMainWindow):
    status_signal = Signal(str)
    text_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.controller = None

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

        self.build_ui()
        self.load_devices()

    def build_ui(self):
        root = QWidget()

        layout = QVBoxLayout(root)

        title = QLabel(
            "Dota2voice2text"
        )

        title.setStyleSheet(
            "font-size: 24px;"
            "font-weight: bold;"
        )

        subtitle = QLabel(
            "Voice-to-text для чата Dota 2"
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

        self.model_combo = QComboBox()

        self.model_combo.addItem(
            "Точный — Turbo",
            "turbo",
        )

        self.model_combo.addItem(
            "Быстрый — Small",
            "small",
        )

        form.addRow(
            "Распознавание:",
            self.model_combo,
        )

        self.team_bind = QLabel(
            "MOUSE5"
        )

        self.all_bind = QLabel(
            "MOUSE4"
        )

        form.addRow(
            "Командный чат:",
            self.team_bind,
        )

        form.addRow(
            "Общий чат:",
            self.all_bind,
        )

        self.auto_send = QCheckBox(
            "Автоматически отправлять сообщение"
        )

        self.auto_send.setChecked(
            False
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

        self.start_button.clicked.connect(
            self.toggle
        )

        self.start_button.setMinimumHeight(
            44
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
            "Последнее распознавание"
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

    def load_devices(self):
        self.device_combo.clear()

        devices = get_input_devices()

        for device in devices:
            text = (
                f'{device["name"]} '
                f'[{device["index"]}]'
            )

            self.device_combo.addItem(
                text,
                device["index"],
            )

    def toggle(self):
        if self.controller is None:
            self.start_controller()
        else:
            self.stop_controller()

    def start_controller(self):
        device_index = (
            self.device_combo.currentData()
        )

        model_size = (
            self.model_combo.currentData()
        )

        if device_index is None:
            self.set_status(
                "Микрофон не выбран"
            )
            return

        self.set_status(
            "Загрузка модели..."
        )

        try:
            self.controller = VoiceController(
                device_index=device_index,
                auto_send=self.auto_send.isChecked(),
                on_status=self.status_signal.emit,
                on_text=self.text_signal.emit,
            )

            self.controller.start()

            self.device_combo.setEnabled(
                False
            )

            self.model_combo.setEnabled(
                False
            )

            self.auto_send.setEnabled(
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
        if self.controller is not None:
            self.controller.stop()

        self.controller = None

        self.device_combo.setEnabled(
            True
        )

        self.model_combo.setEnabled(
            True
        )

        self.auto_send.setEnabled(
            True
        )

        self.start_button.setText(
            "Запустить"
        )

        self.set_status(
            "Остановлено"
        )

    def set_status(
        self,
        text: str,
    ):
        self.status_label.setText(
            f"Статус: {text}"
        )

    def set_last_text(
        self,
        text: str,
    ):
        self.last_text.setText(
            text
        )

    def closeEvent(
        self,
        event,
    ):
        if self.controller is not None:
            self.controller.stop()

        event.accept()

