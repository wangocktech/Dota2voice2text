import threading

from pynput import keyboard, mouse

from PySide6.QtCore import QEvent, QTimer, Signal
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
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.audio.devices import get_input_devices
from src.gui.about_dialog import AboutDialog
from src.config.autostart import set_autostart
from src.config.settings import load_settings, save_settings
from src.core.controller import VoiceController
from src.input.hotkeys import (
    humanize_bind,
    keyboard_to_bind,
    mouse_to_bind,
)
from src.version import APP_VERSION
from src.utils.paths import resource_path
from src.update.update_manager import (
    check_for_update,
)
from src.text.translation_model_manager import (
    download_and_install_translation_model,
    is_translation_model_installed,
    manifest_download_size_bytes,
    remove_translation_model,
    translation_model_size_bytes,
)


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

QPushButton#headerButton {
    background-color: transparent;
    color: #9299A6;
    border: 1px solid #2A2F39;
    border-radius: 7px;
    min-height: 22px;
    padding: 4px 9px;
    font-size: 12px;
}

QPushButton#headerButton:hover {
    color: #FFFFFF;
    border-color: #5865F2;
    background-color: #171A20;
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


QLabel#modelStatus {
    color: #9299A6;
    font-size: 13px;
    min-height: 20px;
}

QProgressBar {
    background-color: #20242C;
    border: 1px solid #343B47;
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #5865F2;
    border-radius: 5px;
}

QPushButton#modelButton {
    min-width: 76px;
    min-height: 24px;
    padding: 5px 10px;
    font-size: 12px;
}

QPushButton#modelCancelButton {
    min-width: 88px;
    padding: 0px 12px;
    font-size: 12px;
}

QPushButton#startButton:disabled {
    background-color: #3A418E;
    color: #D9DCFF;
    border: none;
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
from src.utils.app_icon import get_app_icon



class MainWindow(QMainWindow):
    status_signal = Signal(str)
    text_signal = Signal(str)
    timing_signal = Signal(float)

    bind_signal = Signal(str, str)

    controller_ready = Signal(object)
    controller_error = Signal(str)

    model_progress_signal = Signal(
        int,
        str,
    )
    model_download_finished = Signal(
        bool,
        str,
    )

    update_check_finished = Signal(
        object,
    )

    def __init__(self, start_hidden=False):
        super().__init__()

        self.controller = None
        self.loading = False
        self.force_quit = False

        self.model_downloading = False
        self.model_download_cancel = None
        self.start_after_model_install = False

        self.update_info = None
        self.update_check_running = False

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

        self.resize(720, 840)
        self.setMinimumSize(680, 760)

        combo_arrow = resource_path(
            "assets/icons/chevron-down.svg"
        ).as_posix()

        self.setStyleSheet(
            STYLE.replace(
                "assets/icons/chevron-down.svg",
                combo_arrow,
            )
        )

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

        self.model_progress_signal.connect(
            self._on_model_progress
        )

        self.model_download_finished.connect(
            self._on_model_download_finished
        )

        self.update_check_finished.connect(
            self._on_background_update_checked
        )

        self.build_ui()
        self.load_devices()
        self.setup_tray()

        QTimer.singleShot(
            1800,
            self.check_updates_background,
        )

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

        self.about_button = QPushButton(
            "О программе"
        )
        self.about_button.setObjectName(
            "headerButton"
        )
        self.about_button.clicked.connect(
            self.show_about_dialog
        )

        header.addLayout(title_layout)
        header.addStretch()
        header.addWidget(version)
        header.addWidget(
            self.about_button
        )

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

        behavior_layout.setSpacing(8)

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

        self.translate_to_english.stateChanged.connect(
            self._translation_checkbox_changed
        )

        self.translation_model_status = QLabel()
        self.translation_model_status.setObjectName(
            "modelStatus"
        )

        self.translation_model_progress = QProgressBar()
        self.translation_model_progress.setRange(
            0,
            100,
        )
        self.translation_model_progress.setTextVisible(
            False
        )

        self.translation_model_cancel_button = QPushButton(
            "Отмена"
        )
        self.translation_model_cancel_button.setObjectName(
            "modelCancelButton"
        )
        self.translation_model_cancel_button.clicked.connect(
            self._cancel_translation_model_download
        )
        self.translation_model_cancel_button.setFixedHeight(
            30
        )
        self.translation_model_cancel_button.setMinimumWidth(
            88
        )

        self.translation_download_row = QWidget()
        self.translation_download_row.setObjectName(
            "translationDownloadRow"
        )
        self.translation_download_row.setStyleSheet(
            "background: transparent;"
        )
        self.translation_download_row.setFixedHeight(
            36
        )

        translation_download_layout = QHBoxLayout(
            self.translation_download_row
        )
        translation_download_layout.setContentsMargins(
            0,
            3,
            0,
            3,
        )
        translation_download_layout.setSpacing(
            10
        )

        translation_download_layout.addWidget(
            self.translation_model_progress,
            1,
        )
        translation_download_layout.addWidget(
            self.translation_model_cancel_button,
            0,
        )

        self.translation_download_row.hide()

        self.translation_model_button = QPushButton()
        self.translation_model_button.setObjectName(
            "modelButton"
        )
        self.translation_model_button.clicked.connect(
            self._translation_model_button_clicked
        )
        self.translation_model_button.setMinimumWidth(
            78
        )

        self.translation_model_delete_button = QPushButton(
            "Удалить"
        )
        self.translation_model_delete_button.setObjectName(
            "modelButton"
        )
        self.translation_model_delete_button.clicked.connect(
            self._delete_translation_model
        )
        self.translation_model_delete_button.setMinimumWidth(
            78
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

        model_row = QHBoxLayout()
        model_row.setSpacing(10)
        model_row.setContentsMargins(
            0,
            1,
            0,
            1,
        )

        model_row.addWidget(
            self.translation_model_status,
            1,
        )

        model_row.addWidget(
            self.translation_model_button
        )

        model_row.addWidget(
            self.translation_model_delete_button
        )

        behavior_layout.addLayout(
            model_row
        )

        behavior_layout.addWidget(
            self.translation_download_row
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

        self.refresh_translation_model_ui()

    # ========================================================
    # Translation model
    # ========================================================

    def refresh_translation_model_ui(self):
        installed = (
            is_translation_model_installed()
        )

        if self.model_downloading:
            self.translation_model_button.hide()
            self.translation_model_delete_button.hide()
            self.translation_download_row.show()
            self.translation_model_cancel_button.setEnabled(
                True
            )
            return

        self.translation_download_row.hide()
        self.translation_model_button.show()

        if installed:
            size_mb = (
                translation_model_size_bytes()
                / 1024
                / 1024
            )

            self.translation_model_status.setText(
                f"● Модель установлена • "
                f"{size_mb:.0f} МБ"
            )

            self.translation_model_status.setStyleSheet(
                "color: #57F287;"
            )

            self.translation_model_button.setText(
                "Переустановить"
            )

            self.translation_model_delete_button.show()
        else:
            size_bytes = (
                manifest_download_size_bytes()
            )

            if size_bytes > 0:
                size_text = (
                    f" • ~"
                    f"{size_bytes / 1024 / 1024:.0f} МБ"
                )
            else:
                size_text = ""

            self.translation_model_status.setText(
                "○ Модель не установлена"
                + size_text
            )

            self.translation_model_status.setStyleSheet(
                "color: #9299A6;"
            )

            self.translation_model_button.setText(
                "Скачать"
            )

            self.translation_model_delete_button.hide()

        enabled = (
            self.controller is None
            and not self.loading
            and not self.model_downloading
        )

        self.translation_model_button.setEnabled(
            enabled
        )

        self.translation_model_delete_button.setEnabled(
            enabled
        )

    def _translation_checkbox_changed(
        self,
        state,
    ):
        if not self.translate_to_english.isChecked():
            return

        if is_translation_model_installed():
            return

        if self.model_downloading:
            return

        size_bytes = manifest_download_size_bytes()

        if size_bytes > 0:
            size_text = (
                f" (~"
                f"{size_bytes / 1024 / 1024:.0f} МБ)"
            )
        else:
            size_text = ""

        answer = QMessageBox.question(
            self,
            "Модель перевода",
            "Для перевода на английский нужна "
            f"локальная модель{size_text}.\n\n"
            "Скачать её сейчас?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.download_translation_model()
        else:
            self.translate_to_english.blockSignals(
                True
            )
            self.translate_to_english.setChecked(
                False
            )
            self.translate_to_english.blockSignals(
                False
            )

    def _translation_model_button_clicked(self):
        if self.model_downloading:
            return

        if is_translation_model_installed():
            answer = QMessageBox.question(
                self,
                "Переустановить модель",
                "Скачать модель перевода заново?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        self.download_translation_model(
            force=True
        )

    def _cancel_translation_model_download(self):
        if not self.model_downloading:
            return

        if self.model_download_cancel:
            self.model_download_cancel.set()

        self.translation_model_cancel_button.setEnabled(
            False
        )
        self.translation_model_status.setText(
            "Отмена загрузки..."
        )

    def download_translation_model(
        self,
        force=False,
        start_after=False,
    ):
        if self.model_downloading:
            return

        if (
            is_translation_model_installed()
            and not force
        ):
            if start_after:
                self.start_controller()
            return

        if (
            self.controller is not None
            or self.loading
        ):
            QMessageBox.information(
                self,
                "Модель перевода",
                "Сначала остановите распознавание.",
            )
            return

        self.model_downloading = True
        self.start_after_model_install = (
            start_after
        )
        self.model_download_cancel = (
            threading.Event()
        )

        self.translation_model_progress.setValue(
            0
        )
        self.translation_download_row.show()
        self.translation_model_cancel_button.setEnabled(
            True
        )

        self.start_button.setEnabled(
            False
        )
        self.start_button.setText(
            "Скачивание модели..."
        )

        self.translation_model_status.setText(
            "Подготовка загрузки..."
        )
        self.translation_model_status.setStyleSheet(
            "color: #FFB74D;"
        )

        self.refresh_translation_model_ui()

        threading.Thread(
            target=self._download_model_worker,
            daemon=True,
        ).start()

    def _download_model_worker(self):
        try:
            download_and_install_translation_model(
                progress_callback=
                    self._model_progress_from_worker,
                cancel_event=
                    self.model_download_cancel,
            )

            self.model_download_finished.emit(
                True,
                "",
            )

        except Exception as exc:
            self.model_download_finished.emit(
                False,
                str(exc),
            )

    def _model_progress_from_worker(
        self,
        percent,
        received,
        total,
    ):
        received_mb = (
            received
            / 1024
            / 1024
        )

        if total > 0:
            total_mb = (
                total
                / 1024
                / 1024
            )

            detail = (
                f"{received_mb:.0f} / "
                f"{total_mb:.0f} МБ"
            )
        else:
            detail = (
                f"{received_mb:.0f} МБ"
            )

        self.model_progress_signal.emit(
            percent,
            detail,
        )

    def _on_model_progress(
        self,
        percent,
        detail,
    ):
        if percent >= 0:
            self.translation_model_progress.setRange(
                0,
                100,
            )
            self.translation_model_progress.setValue(
                min(
                    100,
                    percent,
                )
            )

            self.translation_model_status.setText(
                f"Скачивание: {percent}%"
                f" • {detail}"
            )

            self.start_button.setText(
                f"Скачивание модели — {percent}%"
            )
        else:
            self.translation_model_progress.setRange(
                0,
                0,
            )
            self.translation_model_status.setText(
                f"Скачивание • {detail}"
            )
            self.start_button.setText(
                "Скачивание модели..."
            )

    def _on_model_download_finished(
        self,
        success,
        error,
    ):
        start_after = (
            self.start_after_model_install
        )

        self.model_downloading = False
        self.start_after_model_install = False
        self.model_download_cancel = None

        self.translation_download_row.hide()
        self.translation_model_progress.setRange(
            0,
            100,
        )

        self.start_button.setEnabled(
            True
        )
        self.start_button.setText(
            "Запустить"
        )

        self.refresh_translation_model_ui()

        if success:
            self.set_status(
                "Модель перевода установлена"
            )

            if start_after:
                self.start_controller()

            return

        cancelled = (
            "отменена" in error.lower()
        )

        if cancelled:
            self.set_status(
                "Загрузка модели отменена"
            )
            return

        self.translate_to_english.blockSignals(
            True
        )
        self.translate_to_english.setChecked(
            False
        )
        self.translate_to_english.blockSignals(
            False
        )

        self.set_status(
            "Ошибка загрузки модели"
        )

        QMessageBox.critical(
            self,
            "Не удалось скачать модель",
            error,
        )

    def _delete_translation_model(self):
        if (
            self.controller is not None
            or self.loading
            or self.model_downloading
        ):
            return

        answer = QMessageBox.question(
            self,
            "Удалить модель",
            "Удалить локальную модель перевода?\n\n"
            "При следующем включении перевода "
            "её можно будет скачать снова.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            remove_translation_model()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                str(exc),
            )
            return

        self.translate_to_english.blockSignals(
            True
        )
        self.translate_to_english.setChecked(
            False
        )
        self.translate_to_english.blockSignals(
            False
        )

        self.refresh_translation_model_ui()
        self.set_status(
            "Модель перевода удалена"
        )

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

        translate_enabled = (
            self.translate_to_english.isChecked()
        )

        if (
            translate_enabled
            and not is_translation_model_installed()
        ):
            self.download_translation_model(
                start_after=True
            )
            return

        auto_send_enabled = (
            self.auto_send.isChecked()
        )

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
            args=(
                device,
                auto_send_enabled,
                translate_enabled,
            ),
            daemon=True,
        ).start()

    def _load_controller_worker(
        self,
        device,
        auto_send_enabled,
        translate_enabled,
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
                    auto_send_enabled,

                translate_to_english=
                    translate_enabled,

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

        self.refresh_translation_model_ui()

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

        self.refresh_translation_model_ui()

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

        self.refresh_translation_model_ui()

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

        self.refresh_translation_model_ui()

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
    # About / Updates
    # ========================================================

    def show_about_dialog(self):
        dialog = AboutDialog(
            self,
            update_info=self.update_info,
        )

        dialog.exec()

    def check_updates_background(self):
        if self.update_check_running:
            return

        self.update_check_running = True

        threading.Thread(
            target=self._background_update_worker,
            daemon=True,
        ).start()

    def _background_update_worker(self):
        try:
            info = check_for_update(
                APP_VERSION
            )
        except Exception:
            info = None

        self.update_check_finished.emit(
            info
        )

    def _on_background_update_checked(
        self,
        info,
    ):
        self.update_check_running = False

        if not info:
            return

        self.update_info = info

        version = info.get(
            "version",
            "",
        )

        if version:
            self.about_button.setText(
                f"Доступна v{version}"
            )

            self.show_tray_notification(
                f"Доступно обновление "
                f"Dota2voice2text v{version}."
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
        self.tray.setIcon(get_app_icon())

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

        about_action = QAction(
            "О программе / обновления",
            self,
        )

        about_action.triggered.connect(
            self.show_about_dialog
        )

        menu.addAction(
            about_action
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

        if (
            self.model_downloading
            and self.model_download_cancel
        ):
            self.model_download_cancel.set()

        if self.controller:
            self.controller.stop()
            self.controller = None

        self.tray.hide()

        event.accept()

        QApplication.instance().quit()

    def quit_application(self):
        self.force_quit = True

        if (
            self.model_downloading
            and self.model_download_cancel
        ):
            self.model_download_cancel.set()

        self.save_current_settings()

        if self.controller:
            self.controller.stop()
            self.controller = None

        self.tray.hide()

        QApplication.instance().quit()
