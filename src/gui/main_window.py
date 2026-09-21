import threading

from pynput import keyboard, mouse

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
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
from src.audio.mic_level import MicrophoneLevelMonitor
from src.gui.about_dialog import AboutDialog
from src.gui.custom_dictionary_dialog import CustomDictionaryDialog
from src.gui.history_dialog import HistoryDialog
from src.gui.onboarding_dialog import OnboardingDialog
from src.gui.self_test_dialog import SelfTestDialog
from src.config.autostart import set_autostart
from src.config.settings import load_settings, save_settings
from src.core.controller import VoiceController
from src.history.history_store import add_history_entry
from src.input.hotkeys import (
    humanize_bind,
    keyboard_to_bind,
    mouse_to_bind,
)
from src.version import APP_VERSION
from src.utils.dota_status import get_dota_state
from src.utils.health_check import (
    evaluate_app_health,
    format_health_report,
)
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

QProgressBar#micLevel {
    min-height: 14px;
    max-height: 14px;
}

QProgressBar#micLevel::chunk {
    background-color: #5865F2;
    border-radius: 6px;
}

QLabel#micTestStatus {
    color: #9299A6;
    font-size: 12px;
}

QLabel#dotaStatus {
    background-color: #171A20;
    border: 1px solid #2A2F39;
    border-radius: 8px;
    padding: 8px 11px;
    font-size: 13px;
    font-weight: 600;
}

QLabel#healthStatus {
    background-color: #171A20;
    border: 1px solid #2A2F39;
    border-radius: 8px;
    padding: 8px 11px;
    font-size: 13px;
    font-weight: 600;
}

QLabel#bindWarning {
    color: #FFB74D;
    font-size: 12px;
    padding-top: 1px;
}

QPushButton[bindConflict="true"] {
    border-color: #FF5252;
    color: #FFB4B4;
}

QPushButton[bindConflict="true"]:hover {
    border-color: #FF7676;
}

/* Main settings: fixed geometry without Qt stylesheet box-model overflow. */
QComboBox#mainSettingsCombo {
    min-height: 0px;
    max-height: 36px;
    padding: 0px 36px 0px 10px;
}

QPushButton#mainSettingsSideButton,
QPushButton#mainSettingsBindButton {
    min-height: 0px;
    max-height: 36px;
    padding: 0px 12px;
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

        self.mic_monitor = (
            MicrophoneLevelMonitor(
                self
            )
        )

        self.mic_monitor.level_changed.connect(
            self._set_mic_level
        )

        self.mic_monitor.error.connect(
            self._mic_test_error
        )

        self.mic_test_running = False
        self.pending_history_text = ""
        self._initial_positioned = False

        self.dota_status_timer = QTimer(
            self
        )
        self.dota_status_timer.setInterval(
            1500
        )
        self.dota_status_timer.timeout.connect(
            self.refresh_dota_status
        )

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

        self.resize(720, 940)
        self.setMinimumSize(680, 860)

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

        self.refresh_dota_status()
        self.dota_status_timer.start()

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

        if (
            not self.settings.get(
                "onboarding_completed",
                False,
            )
            and not self.start_hidden
        ):
            QTimer.singleShot(
                650,
                self.show_onboarding,
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

        self.history_button = QPushButton(
            "История"
        )
        self.history_button.setObjectName(
            "headerButton"
        )
        self.history_button.clicked.connect(
            self.show_history_dialog
        )

        self.dictionary_button = QPushButton(
            "Словарь"
        )
        self.dictionary_button.setObjectName(
            "headerButton"
        )
        self.dictionary_button.clicked.connect(
            self.show_custom_dictionary
        )

        self.setup_button = QPushButton(
            "Настройка"
        )
        self.setup_button.setObjectName(
            "headerButton"
        )
        self.setup_button.clicked.connect(
            self.show_onboarding
        )

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
            self.history_button
        )
        header.addWidget(
            self.dictionary_button
        )
        header.addWidget(
            self.setup_button
        )
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
        settings_box.setMinimumHeight(
            220
        )

        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(
            12,
            12,
            12,
            10,
        )
        settings_layout.setSpacing(6)

        label_width = 108
        side_button_width = 140
        control_height = 36

        # -------------------------
        # Микрофон
        # -------------------------

        microphone_row = QWidget()
        microphone_row.setFixedHeight(
            38
        )
        microphone_row.setStyleSheet(
            "background: transparent;"
        )

        microphone_layout = QHBoxLayout(
            microphone_row
        )
        microphone_layout.setContentsMargins(
            0,
            1,
            0,
            1,
        )
        microphone_layout.setSpacing(10)

        microphone_label = QLabel(
            "Микрофон:"
        )
        microphone_label.setFixedWidth(
            label_width
        )

        self.device_combo = QComboBox()
        self.device_combo.setObjectName(
            "mainSettingsCombo"
        )
        self.device_combo.setFixedHeight(
            control_height
        )

        self.refresh_button = QPushButton(
            "Обновить"
        )
        self.refresh_button.setObjectName(
            "mainSettingsSideButton"
        )
        self.refresh_button.setFixedSize(
            side_button_width,
            control_height,
        )
        self.refresh_button.clicked.connect(
            self.load_devices
        )

        microphone_layout.addWidget(
            microphone_label
        )
        microphone_layout.addWidget(
            self.device_combo,
            1,
        )
        microphone_layout.addWidget(
            self.refresh_button
        )

        settings_layout.addWidget(
            microphone_row
        )

        # -------------------------
        # Уровень микрофона
        # -------------------------

        level_row = QWidget()
        level_row.setFixedHeight(
            44
        )
        level_row.setStyleSheet(
            "background: transparent;"
        )

        level_layout = QHBoxLayout(
            level_row
        )
        level_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        level_layout.setSpacing(10)

        level_label = QLabel(
            "Уровень:"
        )
        level_label.setFixedWidth(
            label_width
        )

        level_center = QWidget()
        level_center.setStyleSheet(
            "background: transparent;"
        )

        level_center_layout = QVBoxLayout(
            level_center
        )
        level_center_layout.setContentsMargins(
            0,
            2,
            0,
            1,
        )
        level_center_layout.setSpacing(3)

        self.mic_level_bar = QProgressBar()
        self.mic_level_bar.setObjectName(
            "micLevel"
        )
        self.mic_level_bar.setRange(
            0,
            100,
        )
        self.mic_level_bar.setValue(0)
        self.mic_level_bar.setTextVisible(
            False
        )

        self.mic_test_status = QLabel(
            "Проверь, слышит ли программа микрофон."
        )
        self.mic_test_status.setObjectName(
            "micTestStatus"
        )
        self.mic_test_status.setFixedHeight(
            16
        )

        level_center_layout.addWidget(
            self.mic_level_bar
        )
        level_center_layout.addWidget(
            self.mic_test_status
        )

        self.mic_test_button = QPushButton(
            "Тест микрофона"
        )
        self.mic_test_button.setObjectName(
            "mainSettingsSideButton"
        )
        self.mic_test_button.setFixedSize(
            side_button_width,
            control_height,
        )
        self.mic_test_button.clicked.connect(
            self.toggle_mic_test
        )

        level_layout.addWidget(
            level_label
        )
        level_layout.addWidget(
            level_center,
            1,
        )
        level_layout.addWidget(
            self.mic_test_button
        )

        settings_layout.addWidget(
            level_row
        )

        self.device_combo.currentIndexChanged.connect(
            self._device_selection_changed
        )

        # -------------------------
        # Командный чат
        # -------------------------

        team_row = QWidget()
        team_row.setFixedHeight(
            38
        )
        team_row.setStyleSheet(
            "background: transparent;"
        )

        team_layout = QHBoxLayout(
            team_row
        )
        team_layout.setContentsMargins(
            0,
            1,
            0,
            1,
        )
        team_layout.setSpacing(10)

        team_label = QLabel(
            "Командный чат:"
        )
        team_label.setFixedWidth(
            label_width
        )

        self.team_button = QPushButton(
            humanize_bind(
                self.team_bind
            )
        )
        self.team_button.setObjectName(
            "mainSettingsBindButton"
        )
        self.team_button.setFixedHeight(
            control_height
        )
        self.team_button.clicked.connect(
            lambda: self.capture_bind(
                "team"
            )
        )

        team_layout.addWidget(
            team_label
        )
        team_layout.addWidget(
            self.team_button,
            1,
        )

        settings_layout.addWidget(
            team_row
        )

        # -------------------------
        # Общий чат
        # -------------------------

        all_row = QWidget()
        all_row.setFixedHeight(
            38
        )
        all_row.setStyleSheet(
            "background: transparent;"
        )

        all_layout = QHBoxLayout(
            all_row
        )
        all_layout.setContentsMargins(
            0,
            1,
            0,
            1,
        )
        all_layout.setSpacing(10)

        all_label = QLabel(
            "Общий чат:"
        )
        all_label.setFixedWidth(
            label_width
        )

        self.all_button = QPushButton(
            humanize_bind(
                self.all_bind
            )
        )
        self.all_button.setObjectName(
            "mainSettingsBindButton"
        )
        self.all_button.setFixedHeight(
            control_height
        )
        self.all_button.clicked.connect(
            lambda: self.capture_bind(
                "all"
            )
        )

        all_layout.addWidget(
            all_label
        )
        all_layout.addWidget(
            self.all_button,
            1,
        )

        settings_layout.addWidget(
            all_row
        )

        self.bind_warning = QLabel()
        self.bind_warning.setObjectName(
            "bindWarning"
        )
        self.bind_warning.setWordWrap(
            True
        )
        self.bind_warning.hide()
        settings_layout.addWidget(
            self.bind_warning
        )

        settings_box.setLayout(
            settings_layout
        )
        layout.addWidget(
            settings_box
        )

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

        self.translate_to_english.toggled.connect(
            self.refresh_health_status
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
        # Dota 2
        # ----------------------------------------------------

        self.dota_status_label = QLabel(
            "● Dota 2: проверка..."
        )
        self.dota_status_label.setObjectName(
            "dotaStatus"
        )

        layout.addWidget(
            self.dota_status_label
        )

        health_row = QHBoxLayout()
        health_row.setSpacing(8)

        self.health_status_label = QLabel(
            "● Готовность: проверка..."
        )
        self.health_status_label.setObjectName(
            "healthStatus"
        )

        self.health_check_button = QPushButton(
            "Самотест"
        )
        self.health_check_button.setObjectName(
            "headerButton"
        )
        self.health_check_button.setFixedWidth(
            100
        )
        self.health_check_button.clicked.connect(
            self.show_health_check
        )

        health_row.addWidget(
            self.health_status_label,
            1,
        )
        health_row.addWidget(
            self.health_check_button,
        )

        layout.addLayout(
            health_row
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
        self.refresh_bind_conflict_ui()
        self.refresh_health_status()

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

        self.refresh_health_status()

    # ========================================================
    # Microphone test / onboarding
    # ========================================================

    def _select_device_by_key(
        self,
        device_key,
    ):
        if not device_key:
            return

        for index in range(
            self.device_combo.count()
        ):
            data = (
                self.device_combo.itemData(
                    index
                )
            )

            if (
                data
                and data.get("key") == device_key
            ):
                self.device_combo.setCurrentIndex(
                    index
                )
                return

    def _device_selection_changed(
        self,
        *args,
    ):
        self.refresh_health_status()

        if not self.mic_test_running:
            return

        self.stop_mic_test()
        self.start_mic_test()

    def toggle_mic_test(self):
        if self.mic_test_running:
            self.stop_mic_test()
        else:
            self.start_mic_test()

    def start_mic_test(self):
        if (
            self.controller is not None
            or self.loading
        ):
            return

        device = (
            self.device_combo.currentData()
        )

        if not device:
            self.mic_test_status.setText(
                "Микрофон не выбран."
            )
            return

        try:
            self.mic_monitor.start(
                device["index"]
            )

            self.mic_test_running = True

            self.mic_test_button.setText(
                "Остановить тест"
            )

            self.mic_test_status.setText(
                "Говори — полоска должна двигаться."
            )

        except Exception as exc:
            self.mic_test_running = False

            self.mic_test_button.setText(
                "Тест микрофона"
            )

            self.mic_test_status.setText(
                f"Ошибка микрофона: {exc}"
            )

    def stop_mic_test(self):
        self.mic_monitor.stop()
        self.mic_test_running = False

        if hasattr(
            self,
            "mic_level_bar",
        ):
            self.mic_level_bar.setValue(0)

        if hasattr(
            self,
            "mic_test_button",
        ):
            self.mic_test_button.setText(
                "Тест микрофона"
            )

    def _set_mic_level(
        self,
        value,
    ):
        if not self.mic_test_running:
            return

        self.mic_level_bar.setValue(
            value
        )

        if value >= 65:
            text = (
                "Громко — микрофон работает отлично."
            )
        elif value >= 25:
            text = (
                "Микрофон слышит голос."
            )
        elif value >= 7:
            text = (
                "Сигнал есть, говори чуть громче."
            )
        else:
            text = (
                "Ожидаю голос..."
            )

        self.mic_test_status.setText(
            text
        )

    def _mic_test_error(
        self,
        error,
    ):
        if not self.mic_test_running:
            return

        self.mic_test_status.setText(
            f"Ошибка микрофона: {error}"
        )

    def show_onboarding(self):
        if (
            self.controller is not None
            or self.loading
        ):
            QMessageBox.information(
                self,
                "Первичная настройка",
                "Сначала останови распознавание.",
            )
            return

        self.stop_mic_test()

        current = (
            self.device_combo.currentData()
        )

        current_key = (
            current.get("key", "")
            if current
            else self.settings.get(
                "device_key",
                "",
            )
        )

        dialog = OnboardingDialog(
            devices=get_input_devices(),
            selected_device_key=current_key,
            team_bind=self.team_bind,
            all_bind=self.all_bind,
            parent=self,
        )

        if not dialog.exec():
            return

        self._select_device_by_key(
            dialog.selected_device_key()
        )

        self.settings[
            "onboarding_completed"
        ] = True

        self.save_current_settings()

        self.mic_test_status.setText(
            "Настройка завершена. Микрофон готов."
        )

        self.refresh_health_status()

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

        self.refresh_bind_conflict_ui()
        self.refresh_health_status()

        self.capture_target = None

    # ========================================================
    # Dota / binds health
    # ========================================================

    def refresh_dota_status(self):
        try:
            state = get_dota_state()

            if state.foreground:
                text = "● Dota 2: активна"
                color = "#57F287"
                border = "#2E7D4F"
            elif state.running:
                text = (
                    "● Dota 2: запущена, "
                    "но окно не активно"
                )
                color = "#FFB74D"
                border = "#6E552A"
            else:
                text = "○ Dota 2: не запущена"
                color = "#9299A6"
                border = "#2A2F39"

            self.dota_status_label.setText(
                text
            )
            self.dota_status_label.setStyleSheet(
                f"color: {color};"
                f"border-color: {border};"
            )

        except Exception:
            self.dota_status_label.setText(
                "○ Dota 2: статус недоступен"
            )
            self.dota_status_label.setStyleSheet(
                "color: #9299A6;"
            )

        self.refresh_health_status()

    def refresh_health_status(self):
        if not hasattr(
            self,
            "health_status_label",
        ):
            return

        device = (
            self.device_combo.currentData()
            if hasattr(
                self,
                "device_combo",
            )
            else None
        )

        translate_enabled = bool(
            hasattr(
                self,
                "translate_to_english",
            )
            and self.translate_to_english.isChecked()
        )

        report = evaluate_app_health(
            device=device,
            team_bind=self.team_bind,
            all_bind=self.all_bind,
            translate_enabled=translate_enabled,
        )

        self.current_health_report = report

        if report.blockers:
            color = "#FF5252"
            border = "#71363A"
            prefix = "●"
        elif report.warnings:
            color = "#FFB74D"
            border = "#6E552A"
            prefix = "●"
        else:
            color = "#57F287"
            border = "#2E7D4F"
            prefix = "●"

        self.health_status_label.setText(
            f"{prefix} Готовность: {report.summary}"
        )

        self.health_status_label.setStyleSheet(
            f"color: {color};"
            f"border-color: {border};"
        )

        if (
            self.controller is None
            and not self.loading
            and not self.model_downloading
        ):
            self.start_button.setEnabled(
                report.ready
            )

    def show_health_check(self):
        if self.loading:
            QMessageBox.information(
                self,
                "Самотест",
                "Дождись завершения загрузки моделей.",
            )
            return

        if self.model_downloading:
            QMessageBox.information(
                self,
                "Самотест",
                "Дождись завершения загрузки модели перевода.",
            )
            return

        self.stop_mic_test()
        self.refresh_health_status()

        device = self.device_combo.currentData()
        device_index = (
            device.get("index")
            if device
            else None
        )

        dialog = SelfTestDialog(
            self,
            device_index=device_index,
            team_bind=self.team_bind,
            all_bind=self.all_bind,
            translate_enabled=(
                self.translate_to_english.isChecked()
            ),
            controller=self.controller,
        )
        dialog.exec()

        self.refresh_health_status()

    def refresh_bind_conflict_ui(self):
        conflict = bool(
            self.team_bind
            and self.all_bind
            and self.team_bind == self.all_bind
        )

        for button in (
            self.team_button,
            self.all_button,
        ):
            button.setProperty(
                "bindConflict",
                conflict,
            )

            button.style().unpolish(
                button
            )
            button.style().polish(
                button
            )

        if conflict:
            self.bind_warning.setText(
                "⚠ Командный и общий чат "
                "назначены на одну кнопку."
            )
            self.bind_warning.show()
        else:
            self.bind_warning.clear()
            self.bind_warning.hide()

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
        self.refresh_health_status()

        report = getattr(
            self,
            "current_health_report",
            None,
        )

        if (
            report is not None
            and not report.ready
        ):
            QMessageBox.warning(
                self,
                "Приложение не готово",
                format_health_report(
                    report
                ),
            )
            return

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

        self.stop_mic_test()

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

        self.mic_test_button.setEnabled(
            enabled
        )

        self.setup_button.setEnabled(
            enabled
        )

        if not enabled:
            self.stop_mic_test()

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
        self.pending_history_text = text

    def set_timing(self, seconds):
        self.timing_label.setText(
            f"Обработка: {seconds:.3f} сек."
        )

        if self.pending_history_text:
            add_history_entry(
                self.pending_history_text,
                seconds,
            )
            self.pending_history_text = ""

        self.dota_status_timer = QTimer(
            self
        )
        self.dota_status_timer.setInterval(
            1500
        )
        self.dota_status_timer.timeout.connect(
            self.refresh_dota_status
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

            "onboarding_completed":
                bool(
                    self.settings.get(
                        "onboarding_completed",
                        False,
                    )
                ),
        }

        self.settings = settings

        save_settings(settings)

        set_autostart(
            settings["autostart"]
        )

    # ========================================================
    # History / custom dictionary
    # ========================================================

    def show_history_dialog(self):
        HistoryDialog(self).exec()

    def show_custom_dictionary(self):
        if self.controller is not None or self.loading:
            QMessageBox.information(
                self,
                "Пользовательский словарь",
                "Сначала останови распознавание, чтобы обновить словарь.",
            )
            return

        dialog = CustomDictionaryDialog(self)
        if dialog.exec():
            self.set_status("Пользовательский словарь сохранён")

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

    def showEvent(self, event):
        super().showEvent(event)

        if self._initial_positioned:
            return

        self._initial_positioned = True

        QTimer.singleShot(
            0,
            self.center_on_screen,
        )

    def center_on_screen(self):
        screen = self.screen()

        if screen is None:
            screen = QApplication.primaryScreen()

        if screen is None:
            return

        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(
            available.center()
        )
        self.move(
            frame.topLeft()
        )

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
        self.stop_mic_test()
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
        self.stop_mic_test()

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
