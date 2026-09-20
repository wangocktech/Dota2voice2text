import hashlib
import json
import os
import shutil
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from src.utils.paths import resource_path


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

MODELS_DIR = APP_DATA_DIR / "models"
MODEL_DIR = MODELS_DIR / "opus-mt-ru-en-ct2-int8"

MANIFEST_FILE = Path(
    resource_path(
        "data/translation_model_manifest.json"
    )
)

REQUIRED_FILES = (
    "model.bin",
    "config.json",
    "source.spm",
    "target.spm",
    "shared_vocabulary.json",
)


class TranslationModelError(RuntimeError):
    pass


class TranslationModelCancelled(TranslationModelError):
    pass


def get_translation_model_dir() -> Path:
    return MODEL_DIR


def _is_valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False

    if value == "0" * 64:
        return False

    return all(
        ch in "0123456789abcdef"
        for ch in value
    )


def load_manifest() -> dict:
    try:
        data = json.loads(
            MANIFEST_FILE.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception as exc:
        raise TranslationModelError(
            "Не удалось прочитать manifest модели перевода."
        ) from exc

    required = (
        "version",
        "url",
        "sha256",
        "archive_name",
    )

    missing = [
        key
        for key in required
        if not data.get(key)
    ]

    if missing:
        raise TranslationModelError(
            "Manifest модели перевода не настроен: "
            + ", ".join(missing)
        )

    sha256 = str(
        data["sha256"]
    ).strip().lower()

    if not _is_valid_sha256(sha256):
        raise TranslationModelError(
            "Модель перевода ещё не опубликована. "
            "Запусти PUBLISH_TRANSLATION_MODEL.ps1."
        )

    data["sha256"] = sha256
    return data


def is_translation_model_installed() -> bool:
    return all(
        (MODEL_DIR / name).is_file()
        for name in REQUIRED_FILES
    )


def translation_model_size_bytes() -> int:
    if not MODEL_DIR.exists():
        return 0

    total = 0

    for path in MODEL_DIR.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass

    return total


def manifest_download_size_bytes() -> int:
    try:
        data = json.loads(
            MANIFEST_FILE.read_text(
                encoding="utf-8-sig"
            )
        )

        return int(
            data.get(
                "size_bytes",
                0,
            )
            or 0
        )
    except Exception:
        return 0


def remove_translation_model():
    if MODEL_DIR.exists():
        shutil.rmtree(
            MODEL_DIR,
            ignore_errors=False,
        )


def cleanup_stale_downloads():
    MODELS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup_dir = (
        MODELS_DIR
        / ".translation-backup"
    )

    if (
        backup_dir.exists()
        and not MODEL_DIR.exists()
    ):
        try:
            shutil.move(
                str(backup_dir),
                str(MODEL_DIR),
            )
        except OSError:
            pass

    for path in MODELS_DIR.glob(
        ".translation-*"
    ):
        if path.is_dir():
            shutil.rmtree(
                path,
                ignore_errors=True,
            )
        else:
            try:
                path.unlink()
            except OSError:
                pass


def _safe_extract(
    archive: Path,
    destination: Path,
):
    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    root = destination.resolve()

    with zipfile.ZipFile(
        archive,
        "r",
    ) as zip_file:
        for member in zip_file.infolist():
            member_path = (
                destination
                / member.filename
            ).resolve()

            try:
                member_path.relative_to(root)
            except ValueError as exc:
                raise TranslationModelError(
                    "Архив модели содержит "
                    "небезопасный путь."
                ) from exc

        zip_file.extractall(
            destination
        )


def _locate_extracted_model(
    extracted_root: Path,
) -> Path:
    if all(
        (extracted_root / name).is_file()
        for name in REQUIRED_FILES
    ):
        return extracted_root

    children = [
        path
        for path in extracted_root.iterdir()
        if path.is_dir()
    ]

    for child in children:
        if all(
            (child / name).is_file()
            for name in REQUIRED_FILES
        ):
            return child

    raise TranslationModelError(
        "В архиве не найдены необходимые "
        "файлы модели."
    )


def download_and_install_translation_model(
    progress_callback=None,
    cancel_event: threading.Event | None = None,
):
    cleanup_stale_downloads()

    manifest = load_manifest()

    MODELS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    download_file = (
        MODELS_DIR
        / ".translation-download.part"
    )
    extract_dir = (
        MODELS_DIR
        / ".translation-extract"
    )
    install_dir = (
        MODELS_DIR
        / ".translation-install"
    )
    backup_dir = (
        MODELS_DIR
        / ".translation-backup"
    )

    request = urllib.request.Request(
        manifest["url"],
        headers={
            "User-Agent":
                "Dota2voice2text/0.2",
            "Accept":
                "application/octet-stream",
        },
    )

    hasher = hashlib.sha256()
    received = 0
    expected_total = int(
        manifest.get(
            "size_bytes",
            0,
        )
        or 0
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            content_length = (
                response.headers.get(
                    "Content-Length"
                )
            )

            if content_length:
                try:
                    expected_total = int(
                        content_length
                    )
                except ValueError:
                    pass

            with download_file.open(
                "wb"
            ) as output:
                while True:
                    if (
                        cancel_event is not None
                        and cancel_event.is_set()
                    ):
                        raise TranslationModelCancelled(
                            "Загрузка отменена."
                        )

                    chunk = response.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    output.write(chunk)
                    hasher.update(chunk)
                    received += len(chunk)

                    if progress_callback:
                        if expected_total > 0:
                            percent = min(
                                98,
                                int(
                                    received
                                    * 100
                                    / expected_total
                                ),
                            )
                        else:
                            percent = -1

                        progress_callback(
                            percent,
                            received,
                            expected_total,
                        )

        if (
            cancel_event is not None
            and cancel_event.is_set()
        ):
            raise TranslationModelCancelled(
                "Загрузка отменена."
            )

        actual_hash = (
            hasher.hexdigest().lower()
        )

        if (
            actual_hash
            != manifest["sha256"]
        ):
            raise TranslationModelError(
                "SHA-256 модели не совпал. "
                "Файл повреждён или был изменён."
            )

        if progress_callback:
            progress_callback(
                99,
                received,
                expected_total,
            )

        _safe_extract(
            download_file,
            extract_dir,
        )

        extracted_model = (
            _locate_extracted_model(
                extract_dir
            )
        )

        if extracted_model == extract_dir:
            install_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            for item in list(
                extract_dir.iterdir()
            ):
                shutil.move(
                    str(item),
                    str(
                        install_dir
                        / item.name
                    ),
                )
        else:
            shutil.move(
                str(extracted_model),
                str(install_dir),
            )

        if MODEL_DIR.exists():
            shutil.move(
                str(MODEL_DIR),
                str(backup_dir),
            )

        try:
            shutil.move(
                str(install_dir),
                str(MODEL_DIR),
            )

            if not is_translation_model_installed():
                raise TranslationModelError(
                    "Модель скачалась, но "
                    "проверка установки не пройдена."
                )

        except Exception:
            if MODEL_DIR.exists():
                shutil.rmtree(
                    MODEL_DIR,
                    ignore_errors=True,
                )

            if backup_dir.exists():
                shutil.move(
                    str(backup_dir),
                    str(MODEL_DIR),
                )

            raise

        if backup_dir.exists():
            shutil.rmtree(
                backup_dir,
                ignore_errors=True,
            )

        if progress_callback:
            progress_callback(
                100,
                received,
                expected_total,
            )

    except urllib.error.URLError as exc:
        raise TranslationModelError(
            "Не удалось скачать модель. "
            "Проверь подключение к интернету."
        ) from exc

    except zipfile.BadZipFile as exc:
        raise TranslationModelError(
            "Скачанный файл модели повреждён."
        ) from exc

    finally:
        if download_file.exists():
            try:
                download_file.unlink()
            except OSError:
                pass

        if extract_dir.exists():
            shutil.rmtree(
                extract_dir,
                ignore_errors=True,
            )

        if install_dir.exists():
            shutil.rmtree(
                install_dir,
                ignore_errors=True,
            )

        if (
            backup_dir.exists()
            and MODEL_DIR.exists()
        ):
            shutil.rmtree(
                backup_dir,
                ignore_errors=True,
            )
