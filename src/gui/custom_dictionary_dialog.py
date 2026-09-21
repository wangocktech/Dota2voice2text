from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from src.text.custom_dictionary import (
    load_custom_dictionary,
    save_custom_dictionary,
)


class CustomDictionaryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Пользовательский словарь")
        self.setMinimumSize(620, 470)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Пользовательский словарь")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")

        hint = QLabel(
            "Добавляй свои исправления речи. Например: «пуджик» → «Пудж». "
            "Они применяются до Dota-коррекции и пунктуации."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9299A6;")

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Распознано", "Заменять на"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self.add_row)

        delete_button = QPushButton("Удалить выбранное")
        delete_button.clicked.connect(self.delete_selected)

        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_and_close)

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        buttons.addWidget(save_button)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

        self.load_entries()

    def load_entries(self):
        self.table.setRowCount(0)
        for source, target in load_custom_dictionary().items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(source))
            self.table.setItem(row, 1, QTableWidgetItem(target))

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def save_and_close(self):
        entries = {}

        for row in range(self.table.rowCount()):
            source_item = self.table.item(row, 0)
            target_item = self.table.item(row, 1)
            source = source_item.text().strip() if source_item else ""
            target = target_item.text().strip() if target_item else ""

            if not source and not target:
                continue

            if not source or not target:
                QMessageBox.warning(
                    self,
                    "Словарь",
                    f"Строка {row + 1}: заполни оба поля.",
                )
                return

            entries[source] = target

        save_custom_dictionary(entries)
        self.accept()
