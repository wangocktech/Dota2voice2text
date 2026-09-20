import os
import threading
import webbrowser

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.text.translation_model_manager import (
    is_translation_model_installed,
    translation_model_size_bytes,
)
from src.update.update_manager import (
    RELEASES_URL,
    UpdateCancelled,
    UpdateError,
    check_for_update,
    download_update,
    is_frozen_build,
    launch_installer,
)
from src.utils.logging_setup import (
    get_log_dir,
)
from src.version import (
    APP_NAME,
    APP_VERSION,
)


class AboutDialog(QDialog):
    update_checked = Signal(
        object,
        str,
    )

    update_progress = Signal(
        int,
        str,
    )

    update_downloaded = Signal(
        bool,
        object,
        str,
    )

    def __init__(
        self,
        parent=None,
        update_info=None,
    ):
        super().__init__(parent)

        self.update_info = update_info
        self.checking = False
        self.downloading = False
        self.cancel_event = None

        self.setWindowTitle(
            f"О программе — {APP_NAME}"
        )
        self.setModal(True)
        self.setMinimumWidth(500)

        self.update_checked.connect(
            self._on_update_checked
        )
        self.update_progress.connect(
            self._on_update_progress
        )
        self.update_downloaded.connect(
            self._on_update_downloaded
        )

        self._build_ui()
        self._refresh_model_text()
        self._refresh_update_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )
        layout.setSpacing(12)

        title = QLabel(
            APP_NAME
        )
        title.setStyleSheet(
            "font-size: 22px;"
            "font-weight: 700;"
        )

        subtitle = QLabel(
            f"Версия {APP_VERSION}\n"
            "Локальный голосовой ввод для Dota 2."
        )
        subtitle.setWordWrap(True)

        self.model_label = QLabel()
        self.model_label.setWordWrap(True)

        self.update_label = QLabel()
        self.update_label.setWordWrap(True)

        self.update_progress_bar = (
            QProgressBar()
        )
        self.update_progress_bar.setRange(
            0,
            100,
        )
        self.update_progress_bar.setTextVisible(
            False
        )
        self.update_progress_bar.hide()

        self.check_button = QPushButton(
            "Проверить обновления"
        )
        self.check_button.clicked.connect(
            self.check_updates
        )

        self.install_button = QPushButton(
            "Скачать и установить"
        )
        self.install_button.clicked.connect(
            self.install_update
        )
        self.install_button.hide()

        github_button = QPushButton(
            "GitHub Releases"
        )
        github_button.clicked.connect(
            lambda:
                webbrowser.open(
                    RELEASES_URL
                )
        )

        logs_button = QPushButton(
            "Открыть папку логов"
        )
        logs_button.clicked.connect(
            self.open_logs
        )

        close_button = QPushButton(
            "Закрыть"
        )
        close_button.clicked.connect(
            self.reject
        )

        actions = QHBoxLayout()
        actions.setSpacing(8)

        actions.addWidget(
            self.check_button
        )
        actions.addWidget(
            self.install_button
        )

        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        bottom.addWidget(
            github_button
        )
        bottom.addWidget(
            logs_button
        )
        bottom.addStretch()
        bottom.addWidget(
            close_button
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)
        layout.addWidget(
            self.model_label
        )
        layout.addWidget(
            self.update_label
        )
        layout.addWidget(
            self.update_progress_bar
        )
        layout.addLayout(actions)
        layout.addSpacing(4)
        layout.addLayout(bottom)

    def _refresh_model_text(self):
        if is_translation_model_installed():
            size_mb = (
                translation_model_size_bytes()
                / 1024
                / 1024
            )

            self.model_label.setText(
                "Перевод RU → EN: "
                f"модель установлена "
                f"({size_mb:.0f} МБ)"
            )
        else:
            self.model_label.setText(
                "Перевод RU → EN: "
                "модель не установлена"
            )

    def _refresh_update_ui(self):
        if self.update_info:
            version = self.update_info[
                "version"
            ]

            self.update_label.setText(
                f"Доступно обновление v{version}."
            )

            self.install_button.show()
        else:
            self.update_label.setText(
                "Обновления ещё не проверялись."
            )

            self.install_button.hide()

    def check_updates(self):
        if (
            self.checking
            or self.downloading
        ):
            return

        self.checking = True
        self.check_button.setEnabled(
            False
        )
        self.update_label.setText(
            "Проверяю обновления..."
        )

        threading.Thread(
            target=self._check_worker,
            daemon=True,
        ).start()

    def _check_worker(self):
        try:
            info = check_for_update(
                APP_VERSION
            )

            self.update_checked.emit(
                info,
                "",
            )

        except Exception as exc:
            self.update_checked.emit(
                None,
                str(exc),
            )

    def _on_update_checked(
        self,
        info,
        error,
    ):
        self.checking = False
        self.check_button.setEnabled(
            True
        )

        if error:
            self.update_label.setText(
                f"Ошибка: {error}"
            )
            return

        self.update_info = info

        if info is None:
            self.update_label.setText(
                "Установлена актуальная версия."
            )
            self.install_button.hide()
            return

        self._refresh_update_ui()

    def install_update(self):
        if (
            self.downloading
            or not self.update_info
        ):
            return

        if not is_frozen_build():
            QMessageBox.information(
                self,
                "Обновление",
                "Автоустановка проверяется только "
                "в готовом EXE.\n\n"
                "Из исходного кода можно открыть "
                "GitHub Releases.",
            )
            return

        if not self.update_info.get(
            "zip_url"
        ):
            QMessageBox.warning(
                self,
                "Обновление",
                "В релизе нет Windows ZIP.",
            )
            return

        if not self.update_info.get(
            "sha256"
        ):
            QMessageBox.warning(
                self,
                "Обновление",
                "У релиза отсутствует SHA-256. "
                "Автоустановка заблокирована.",
            )
            return

        version = self.update_info[
            "version"
        ]

        answer = QMessageBox.question(
            self,
            "Установить обновление",
            f"Скачать и установить "
            f"Dota2voice2text v{version}?\n\n"
            "После загрузки программа "
            "перезапустится.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if (
            answer
            != QMessageBox
            .StandardButton
            .Yes
        ):
            return

        self.downloading = True
        self.cancel_event = (
            threading.Event()
        )

        self.install_button.setEnabled(
            False
        )
        self.check_button.setEnabled(
            False
        )

        self.update_progress_bar.setValue(
            0
        )
        self.update_progress_bar.show()

        self.update_label.setText(
            "Скачивание обновления..."
        )

        threading.Thread(
            target=self._download_worker,
            daemon=True,
        ).start()

    def _download_worker(self):
        try:
            path = download_update(
                self.update_info,
                progress_callback=
                    self._progress_worker,
                cancel_event=
                    self.cancel_event,
            )

            self.update_downloaded.emit(
                True,
                path,
                "",
            )

        except UpdateCancelled as exc:
            self.update_downloaded.emit(
                False,
                None,
                str(exc),
            )

        except Exception as exc:
            self.update_downloaded.emit(
                False,
                None,
                str(exc),
            )

    def _progress_worker(
        self,
        percent,
        received,
        total,
    ):
        if total > 0:
            detail = (
                f"{received / 1024 / 1024:.0f}"
                f" / "
                f"{total / 1024 / 1024:.0f}"
                f" МБ"
            )
        else:
            detail = (
                f"{received / 1024 / 1024:.0f}"
                f" МБ"
            )

        self.update_progress.emit(
            percent,
            detail,
        )

    def _on_update_progress(
        self,
        percent,
        detail,
    ):
        if percent >= 0:
            self.update_progress_bar.setRange(
                0,
                100,
            )
            self.update_progress_bar.setValue(
                percent
            )
            self.update_label.setText(
                f"Скачивание: {percent}% • {detail}"
            )
        else:
            self.update_progress_bar.setRange(
                0,
                0,
            )
            self.update_label.setText(
                f"Скачивание • {detail}"
            )

    def _on_update_downloaded(
        self,
        success,
        path,
        message,
    ):
        self.downloading = False
        self.check_button.setEnabled(
            True
        )
        self.install_button.setEnabled(
            True
        )
        self.update_progress_bar.hide()

        if not success:
            self.update_label.setText(
                message
                or "Загрузка отменена."
            )
            return

        try:
            launch_installer(path)

        except UpdateError as exc:
            self.update_label.setText(
                f"Ошибка: {exc}"
            )
            return

        self.update_label.setText(
            "Обновление скачано. "
            "Перезапускаю приложение..."
        )

        parent = self.parent()

        if (
            parent is not None
            and hasattr(
                parent,
                "quit_application",
            )
        ):
            parent.quit_application()
        else:
            self.accept()

    def open_logs(self):
        path = get_log_dir()
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            os.startfile(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Логи",
                f"Не удалось открыть папку:\n{exc}",
            )
