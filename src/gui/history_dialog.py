from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.history.history_store import clear_history, load_history


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История сообщений")
        self.setMinimumSize(720, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Последние сообщения")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")

        hint = QLabel("Хранятся последние 50 успешно обработанных сообщений.")
        hint.setStyleSheet("color: #9299A6;")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Время", "Сообщение", "Обработка"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        copy_button = QPushButton("Копировать")
        copy_button.clicked.connect(self.copy_selected)

        clear_button = QPushButton("Очистить историю")
        clear_button.clicked.connect(self.clear_all)

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(copy_button)
        buttons.addWidget(clear_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

        self.reload()

    def reload(self):
        history = list(reversed(load_history()))
        self.table.setRowCount(0)

        for item in history:
            row = self.table.rowCount()
            self.table.insertRow(row)

            raw_time = str(item.get("timestamp", ""))
            try:
                stamp = datetime.fromisoformat(raw_time).strftime("%d.%m %H:%M:%S")
            except Exception:
                stamp = raw_time

            self.table.setItem(row, 0, QTableWidgetItem(stamp))
            self.table.setItem(row, 1, QTableWidgetItem(str(item.get("text", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(f"{float(item.get('total_time', 0)):.3f} с"))

    def copy_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 1)
        if item:
            QApplication.clipboard().setText(item.text())

    def clear_all(self):
        answer = QMessageBox.question(
            self,
            "Очистить историю",
            "Удалить всю историю сообщений?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            clear_history()
            self.reload()
