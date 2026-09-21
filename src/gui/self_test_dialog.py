from __future__ import annotations

import threading

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.utils.self_test import (
    SelfTestItem,
    SelfTestReport,
    format_self_test_report,
    run_self_test,
)


class SelfTestDialog(QDialog):
    item_ready = Signal(object)
    test_finished = Signal(object, str)

    STATUS_TEXT = {
        "pass": "OK",
        "warning": "Предупреждение",
        "error": "Ошибка",
        "skip": "Пропущено",
    }

    STATUS_COLOR = {
        "pass": "#57F287",
        "warning": "#FFB74D",
        "error": "#FF5252",
        "skip": "#9299A6",
    }

    TEST_COUNT = 8

    def __init__(
        self,
        parent=None,
        *,
        device_index=None,
        team_bind="",
        all_bind="",
        translate_enabled=False,
        controller=None,
    ):
        super().__init__(parent)

        self.device_index = device_index
        self.team_bind = team_bind
        self.all_bind = all_bind
        self.translate_enabled = translate_enabled
        self.controller = controller

        self.running = False
        self.report: SelfTestReport | None = None
        self.completed = 0

        self.setWindowTitle(
            "Самотест Dota2voice2text"
        )
        self.resize(760, 560)
        self.setMinimumSize(680, 500)
        self.setModal(True)

        self._build_ui()

        self.item_ready.connect(
            self._on_item
        )
        self.test_finished.connect(
            self._on_finished
        )

        self.start_test()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )
        layout.setSpacing(12)

        title = QLabel(
            "Самотест перед релизом"
        )
        title.setStyleSheet(
            "font-size: 20px; font-weight: 700;"
        )

        self.summary_label = QLabel(
            "Проверяю микрофон, модели, Dota 2, "
            "SendInput и latency..."
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "color: #9299A6;"
        )

        self.progress = QProgressBar()
        self.progress.setRange(
            0,
            self.TEST_COUNT,
        )
        self.progress.setValue(0)
        self.progress.setTextVisible(True)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels([
            "Проверка",
            "Статус",
            "Детали",
            "Время",
        ])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)

        header = self.tree.header()
        header.resizeSection(0, 175)
        header.resizeSection(1, 125)
        header.resizeSection(2, 330)
        header.resizeSection(3, 90)

        self.rerun_button = QPushButton(
            "Запустить снова"
        )
        self.rerun_button.clicked.connect(
            self.start_test
        )

        self.copy_button = QPushButton(
            "Копировать отчёт"
        )
        self.copy_button.clicked.connect(
            self.copy_report
        )
        self.copy_button.setEnabled(False)

        close_button = QPushButton(
            "Закрыть"
        )
        close_button.clicked.connect(
            self.accept
        )

        bottom = QHBoxLayout()
        bottom.addWidget(
            self.rerun_button
        )
        bottom.addWidget(
            self.copy_button
        )
        bottom.addStretch()
        bottom.addWidget(
            close_button
        )

        layout.addWidget(title)
        layout.addWidget(
            self.summary_label
        )
        layout.addWidget(
            self.progress
        )
        layout.addWidget(
            self.tree,
            1,
        )
        layout.addLayout(bottom)

    def start_test(self):
        if self.running:
            return

        self.running = True
        self.report = None
        self.completed = 0

        self.tree.clear()
        self.progress.setValue(0)
        self.rerun_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.summary_label.setText(
            "Проверка выполняется. Первичная загрузка моделей "
            "может занять несколько секунд..."
        )
        self.summary_label.setStyleSheet(
            "color: #9299A6;"
        )

        threading.Thread(
            target=self._worker,
            daemon=True,
        ).start()

    def _worker(self):
        try:
            report = run_self_test(
                device_index=self.device_index,
                team_bind=self.team_bind,
                all_bind=self.all_bind,
                translate_enabled=self.translate_enabled,
                controller=self.controller,
                on_item=self.item_ready.emit,
            )
            self.test_finished.emit(
                report,
                "",
            )
        except Exception as exc:
            self.test_finished.emit(
                None,
                str(exc),
            )

    def _on_item(
        self,
        item: SelfTestItem,
    ):
        self.completed += 1
        self.progress.setValue(
            min(
                self.completed,
                self.TEST_COUNT,
            )
        )

        elapsed = (
            f"{item.elapsed:.3f} s"
            if item.elapsed > 0
            else "—"
        )

        row = QTreeWidgetItem([
            item.title,
            self.STATUS_TEXT.get(
                item.status,
                item.status,
            ),
            item.detail,
            elapsed,
        ])

        color = self.STATUS_COLOR.get(
            item.status,
            "#F2F3F5",
        )
        row.setForeground(
            1,
            QBrush(QColor(color)),
        )

        self.tree.addTopLevelItem(row)

    def _on_finished(
        self,
        report,
        error: str,
    ):
        self.running = False
        self.rerun_button.setEnabled(True)

        if error:
            self.summary_label.setText(
                f"Самотест завершился ошибкой: {error}"
            )
            self.summary_label.setStyleSheet(
                "color: #FF5252;"
            )
            return

        self.report = report
        self.copy_button.setEnabled(True)
        self.progress.setValue(
            self.TEST_COUNT
        )

        if report.errors:
            color = "#FF5252"
        elif report.warnings:
            color = "#FFB74D"
        else:
            color = "#57F287"

        benchmark = ""
        if report.pipeline_seconds is not None:
            benchmark = (
                " • pipeline "
                f"{report.pipeline_seconds:.3f} сек."
            )

        self.summary_label.setText(
            f"Итог: {report.summary}{benchmark}"
        )
        self.summary_label.setStyleSheet(
            f"color: {color}; font-weight: 600;"
        )

    def copy_report(self):
        if self.report is None:
            return

        clipboard = (
            QGuiApplication.clipboard()
        )
        clipboard.setText(
            format_self_test_report(
                self.report
            )
        )

        QMessageBox.information(
            self,
            "Самотест",
            "Отчёт скопирован в буфер обмена.",
        )
