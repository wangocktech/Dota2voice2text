import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path


APP_DATA_DIR = (
    Path(
        os.getenv(
            "LOCALAPPDATA",
            os.getenv(
                "APPDATA",
                Path.home(),
            ),
        )
    )
    / "Dota2voice2text"
)

LOG_DIR = APP_DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"


class _TeeLogStream:
    def __init__(self, logger, level, original=None):
        self.logger = logger
        self.level = level
        self.original = original
        self._buffer = ""

    def write(self, text):
        if text is None:
            return 0

        text = str(text)

        if self.original is not None:
            try:
                self.original.write(text)
            except Exception:
                pass

        self._buffer += text

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split(
                "\n",
                1,
            )

            line = line.rstrip("\r")

            if line.strip():
                self.logger.log(
                    self.level,
                    line,
                )

        return len(text)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except Exception:
                pass

        if self._buffer.strip():
            self.logger.log(
                self.level,
                self._buffer.rstrip(),
            )
            self._buffer = ""

    def isatty(self):
        if self.original is None:
            return False

        try:
            return bool(
                self.original.isatty()
            )
        except Exception:
            return False

    @property
    def encoding(self):
        if self.original is not None:
            return getattr(
                self.original,
                "encoding",
                "utf-8",
            )

        return "utf-8"


def get_log_dir() -> Path:
    return LOG_DIR


def get_log_file() -> Path:
    return LOG_FILE


def setup_logging():
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in list(root.handlers):
        if getattr(
            handler,
            "_dota2voice2text_handler",
            False,
        ):
            root.removeHandler(handler)

    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    handler._dota2voice2text_handler = True

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | "
            "%(threadName)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root.addHandler(handler)

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    sys.stdout = _TeeLogStream(
        logging.getLogger("stdout"),
        logging.INFO,
        old_stdout,
    )

    sys.stderr = _TeeLogStream(
        logging.getLogger("stderr"),
        logging.ERROR,
        old_stderr,
    )

    def _exception_hook(
        exc_type,
        exc_value,
        exc_traceback,
    ):
        if issubclass(
            exc_type,
            KeyboardInterrupt,
        ):
            return

        logging.getLogger(
            "crash"
        ).critical(
            "Необработанное исключение",
            exc_info=(
                exc_type,
                exc_value,
                exc_traceback,
            ),
        )

    sys.excepthook = _exception_hook

    if hasattr(
        threading,
        "excepthook",
    ):
        def _thread_exception_hook(args):
            logging.getLogger(
                "crash"
            ).critical(
                "Необработанное исключение в потоке %s",
                getattr(
                    args.thread,
                    "name",
                    "unknown",
                ),
                exc_info=(
                    args.exc_type,
                    args.exc_value,
                    args.exc_traceback,
                ),
            )

        threading.excepthook = (
            _thread_exception_hook
        )

    logging.info(
        "Логирование запущено: %s",
        LOG_FILE,
    )

    return LOG_FILE
