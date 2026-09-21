import logging
import sys

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow
from src.utils.logging_setup import setup_logging
from src.version import (
    APP_NAME,
    APP_VERSION,
)
from src.utils.app_icon import get_app_icon



def main():
    setup_logging()

    logging.info(
        "Запуск Dota2voice2text"
    )

    app = QApplication(sys.argv)
    app.setWindowIcon(get_app_icon())

    app.setApplicationName(
        APP_NAME
    )

    app.setApplicationVersion(
        APP_VERSION
    )

    app.setQuitOnLastWindowClosed(
        False
    )

    start_hidden = (
        "--minimized"
        in sys.argv
    )

    window = MainWindow(
        start_hidden=start_hidden
    )
    window.setWindowIcon(get_app_icon())

    if window.start_hidden:
        window.hide()

        window.show_tray_notification(
            "Dota2voice2text запущен "
            "в системном трее."
        )
    else:
        window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
