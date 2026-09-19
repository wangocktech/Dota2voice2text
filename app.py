import sys

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(
        "Dota2voice2text"
    )

    # Нужно для работы системного трея.
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
