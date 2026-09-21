from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.audio.mic_level import (
    MicrophoneLevelMonitor,
)
from src.input.hotkeys import humanize_bind
from src.utils.app_icon import get_app_icon


ONBOARDING_STYLE = """
QDialog {
    background-color: #101216;
    color: #F2F3F5;
}

QWidget {
    background-color: #101216;
    color: #F2F3F5;
    font-family: "Segoe UI";
    font-size: 14px;
}

QLabel#pageTitle {
    color: #FFFFFF;
    font-size: 25px;
    font-weight: 700;
}

QLabel#pageText {
    color: #A7ADB8;
    font-size: 14px;
}

QLabel#stepLabel {
    color: #7E8591;
    font-size: 12px;
}

QLabel#micState {
    color: #A7ADB8;
    font-size: 13px;
}

QComboBox,
QPushButton {
    background-color: #20242C;
    color: #FFFFFF;
    border: 1px solid #343B47;
    border-radius: 7px;
    padding: 8px 11px;
    min-height: 28px;
}

QComboBox:hover,
QPushButton:hover {
    border-color: #5865F2;
}

QPushButton#primaryButton {
    background-color: #5865F2;
    border: none;
    min-width: 105px;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background-color: #6874F5;
}

QProgressBar {
    background-color: #20242C;
    border: 1px solid #343B47;
    border-radius: 7px;
    min-height: 16px;
    max-height: 16px;
}

QProgressBar::chunk {
    background-color: #5865F2;
    border-radius: 6px;
}
"""


class OnboardingDialog(QDialog):
    def __init__(
        self,
        devices,
        selected_device_key="",
        team_bind="mouse:x2",
        all_bind="mouse:x1",
        parent=None,
    ):
        super().__init__(parent)

        self.devices = devices
        self.selected_device_key_value = (
            selected_device_key
        )
        self.team_bind = team_bind
        self.all_bind = all_bind

        self.monitor = (
            MicrophoneLevelMonitor(
                self
            )
        )

        self.monitor.level_changed.connect(
            self._on_level
        )

        self.monitor.error.connect(
            self._on_mic_error
        )

        self.setWindowTitle(
            "Первичная настройка"
        )
        self.setWindowIcon(
            get_app_icon()
        )

        self.setModal(True)
        self.resize(620, 430)
        self.setMinimumSize(
            560,
            400,
        )

        self.setStyleSheet(
            ONBOARDING_STYLE
        )

        self._build_ui()
        self._populate_devices()
        self._update_navigation()

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.setContentsMargins(
            26,
            24,
            26,
            22,
        )

        root.setSpacing(18)

        self.step_label = QLabel()
        self.step_label.setObjectName(
            "stepLabel"
        )

        root.addWidget(
            self.step_label
        )

        self.pages = QStackedWidget()
        root.addWidget(
            self.pages,
            1,
        )

        self.pages.addWidget(
            self._build_welcome_page()
        )

        self.pages.addWidget(
            self._build_microphone_page()
        )

        self.pages.addWidget(
            self._build_finish_page()
        )

        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.back_button = QPushButton(
            "Назад"
        )

        self.back_button.clicked.connect(
            self._back
        )

        self.next_button = QPushButton(
            "Далее"
        )

        self.next_button.setObjectName(
            "primaryButton"
        )

        self.next_button.clicked.connect(
            self._next
        )

        footer.addWidget(
            self.back_button
        )

        footer.addStretch()

        footer.addWidget(
            self.next_button
        )

        root.addLayout(
            footer
        )

        self.pages.currentChanged.connect(
            self._page_changed
        )

    def _build_welcome_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.setContentsMargins(
            0,
            4,
            0,
            4,
        )

        layout.setSpacing(14)

        title = QLabel(
            "Добро пожаловать"
        )
        title.setObjectName(
            "pageTitle"
        )

        text = QLabel(
            "За минуту настроим Dota2voice2text.\n\n"
            "• выберем правильный микрофон;\n"
            "• проверим его живой уровень;\n"
            "• покажем текущие кнопки чата.\n\n"
            "После мастера всё можно изменить "
            "в главном окне."
        )

        text.setObjectName(
            "pageText"
        )
        text.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(text)
        layout.addStretch()

        return page

    def _build_microphone_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.setContentsMargins(
            0,
            4,
            0,
            4,
        )

        layout.setSpacing(14)

        title = QLabel(
            "Проверь микрофон"
        )
        title.setObjectName(
            "pageTitle"
        )

        text = QLabel(
            "Выбери микрофон и скажи несколько слов. "
            "Полоска должна двигаться вместе с голосом."
        )
        text.setObjectName(
            "pageText"
        )
        text.setWordWrap(True)

        self.device_combo = QComboBox()

        self.device_combo.currentIndexChanged.connect(
            self._device_changed
        )

        self.level_bar = QProgressBar()
        self.level_bar.setRange(
            0,
            100,
        )
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(
            False
        )

        self.mic_state = QLabel(
            "Подготовка..."
        )
        self.mic_state.setObjectName(
            "micState"
        )

        self.test_button = QPushButton(
            "Остановить тест"
        )

        self.test_button.clicked.connect(
            self._toggle_test
        )

        layout.addWidget(title)
        layout.addWidget(text)
        layout.addSpacing(6)
        layout.addWidget(
            self.device_combo
        )
        layout.addWidget(
            self.level_bar
        )
        layout.addWidget(
            self.mic_state
        )
        layout.addWidget(
            self.test_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addStretch()

        return page

    def _build_finish_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.setContentsMargins(
            0,
            4,
            0,
            4,
        )

        layout.setSpacing(14)

        title = QLabel(
            "Почти готово"
        )
        title.setObjectName(
            "pageTitle"
        )

        text = QLabel(
            "Текущие кнопки Push-to-Talk:\n\n"
            f"Командный чат:  "
            f"{humanize_bind(self.team_bind)}\n"
            f"Общий чат:       "
            f"{humanize_bind(self.all_bind)}\n\n"
            "Нажми «Готово». После этого в главном "
            "окне можно изменить бинды, перевод, "
            "автоотправку и другие параметры."
        )

        text.setObjectName(
            "pageText"
        )
        text.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(text)
        layout.addStretch()

        return page

    def _populate_devices(self):
        self.device_combo.blockSignals(
            True
        )

        self.device_combo.clear()

        selected = -1

        for position, device in enumerate(
            self.devices
        ):
            key = (
                f'{device["name"]}|'
                f'{device["sample_rate"]}'
            )

            label = device["name"]

            if device.get(
                "default",
                False,
            ):
                label += " (по умолчанию)"

            data = {
                "index":
                    device["index"],
                "key":
                    key,
            }

            self.device_combo.addItem(
                label,
                data,
            )

            if (
                key
                == self.selected_device_key_value
            ):
                selected = position

        if selected >= 0:
            self.device_combo.setCurrentIndex(
                selected
            )

        self.device_combo.blockSignals(
            False
        )

        if self.device_combo.count() == 0:
            self.mic_state.setText(
                "Микрофоны не найдены."
            )

    def selected_device_key(self):
        data = self.device_combo.currentData()

        if not data:
            return ""

        return data.get(
            "key",
            "",
        )

    def _page_changed(self, index):
        if index == 1:
            self._start_test()
        else:
            self._stop_test()

        self._update_navigation()

    def _update_navigation(self):
        index = self.pages.currentIndex()
        total = self.pages.count()

        self.step_label.setText(
            f"Шаг {index + 1} из {total}"
        )

        self.back_button.setVisible(
            index > 0
        )

        if index == total - 1:
            self.next_button.setText(
                "Готово"
            )
        else:
            self.next_button.setText(
                "Далее"
            )

    def _back(self):
        index = self.pages.currentIndex()

        if index > 0:
            self.pages.setCurrentIndex(
                index - 1
            )

    def _next(self):
        index = self.pages.currentIndex()

        if index == 1:
            if not self.device_combo.currentData():
                QMessageBox.warning(
                    self,
                    "Микрофон",
                    "Сначала выбери микрофон.",
                )
                return

            self.selected_device_key_value = (
                self.selected_device_key()
            )

        if index >= (
            self.pages.count() - 1
        ):
            self._stop_test()
            self.accept()
            return

        self.pages.setCurrentIndex(
            index + 1
        )

    def _toggle_test(self):
        if self.monitor.running:
            self._stop_test()
        else:
            self._start_test()

    def _start_test(self):
        data = self.device_combo.currentData()

        if not data:
            self.mic_state.setText(
                "Микрофон не выбран."
            )
            return

        try:
            self.monitor.start(
                data["index"]
            )

            self.test_button.setText(
                "Остановить тест"
            )

            self.mic_state.setText(
                "Говори — уровень должен двигаться."
            )

        except Exception:
            self.test_button.setText(
                "Запустить тест"
            )

    def _stop_test(self):
        self.monitor.stop()

        if hasattr(
            self,
            "test_button",
        ):
            self.test_button.setText(
                "Запустить тест"
            )

        if hasattr(
            self,
            "level_bar",
        ):
            self.level_bar.setValue(0)

    def _device_changed(self):
        self.selected_device_key_value = (
            self.selected_device_key()
        )

        if (
            self.pages.currentIndex() == 1
            and self.monitor.running
        ):
            self._start_test()

    def _on_level(self, value):
        self.level_bar.setValue(
            value
        )

        if value >= 65:
            state = "Громко — микрофон работает отлично."
        elif value >= 25:
            state = "Микрофон слышит голос."
        elif value >= 7:
            state = "Сигнал есть, говори чуть громче."
        else:
            state = "Ожидаю голос..."

        self.mic_state.setText(
            state
        )

    def _on_mic_error(self, error):
        self.mic_state.setText(
            f"Ошибка микрофона: {error}"
        )

    def reject(self):
        self._stop_test()
        super().reject()

    def accept(self):
        self._stop_test()
        super().accept()

    def closeEvent(self, event):
        self._stop_test()
        super().closeEvent(event)
