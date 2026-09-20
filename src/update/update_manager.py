import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


REPO = "wangocktech/Dota2voice2text"
RELEASES_API = (
    f"https://api.github.com/repos/"
    f"{REPO}/releases?per_page=30"
)
RELEASES_URL = (
    f"https://github.com/{REPO}/releases"
)

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

UPDATES_DIR = APP_DATA_DIR / "updates"

_VERSION_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)$"
)


class UpdateError(RuntimeError):
    pass


class UpdateCancelled(UpdateError):
    pass


def _version_tuple(value: str):
    match = _VERSION_RE.fullmatch(
        str(value).strip()
    )

    if not match:
        return None

    return tuple(
        int(part)
        for part in match.groups()
    )


def _request(url: str):
    return urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Dota2voice2text-Updater",
            "Accept":
                "application/vnd.github+json",
            "X-GitHub-Api-Version":
                "2022-11-28",
        },
    )


def _load_json_url(
    url: str,
    timeout=10,
):
    try:
        with urllib.request.urlopen(
            _request(url),
            timeout=timeout,
        ) as response:
            return json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except urllib.error.URLError as exc:
        raise UpdateError(
            "Не удалось проверить обновления. "
            "Проверь подключение к интернету."
        ) from exc

    except json.JSONDecodeError as exc:
        raise UpdateError(
            "GitHub вернул некорректный ответ."
        ) from exc


def _read_text_url(
    url: str,
    timeout=10,
) -> str:
    try:
        with urllib.request.urlopen(
            _request(url),
            timeout=timeout,
        ) as response:
            return response.read().decode(
                "utf-8-sig"
            )

    except urllib.error.URLError as exc:
        raise UpdateError(
            "Не удалось получить SHA-256 обновления."
        ) from exc


def check_for_update(
    current_version: str,
):
    current = _version_tuple(
        current_version
    )

    if current is None:
        raise UpdateError(
            "Некорректная версия приложения."
        )

    releases = _load_json_url(
        RELEASES_API
    )

    candidates = []

    for release in releases:
        if release.get("draft"):
            continue

        if release.get("prerelease"):
            continue

        tag = str(
            release.get(
                "tag_name",
                "",
            )
        ).strip()

        version = _version_tuple(tag)

        # Ignore utility releases such as translation-model-v1.
        if version is None:
            continue

        candidates.append(
            (
                version,
                release,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    latest_version, release = (
        candidates[0]
    )

    if latest_version <= current:
        return None

    version_text = ".".join(
        str(part)
        for part in latest_version
    )

    expected_zip = (
        f"Dota2voice2text-v"
        f"{version_text}-windows-x64.zip"
    )

    assets = release.get(
        "assets",
        [],
    )

    zip_asset = next(
        (
            asset
            for asset in assets
            if asset.get("name")
            == expected_zip
        ),
        None,
    )

    if zip_asset is None:
        zip_asset = next(
            (
                asset
                for asset in assets
                if str(
                    asset.get(
                        "name",
                        "",
                    )
                ).lower().endswith(
                    "-windows-x64.zip"
                )
            ),
            None,
        )

    sha256 = None

    if zip_asset:
        digest = str(
            zip_asset.get(
                "digest",
                "",
            )
            or ""
        ).strip().lower()

        if digest.startswith(
            "sha256:"
        ):
            candidate = digest.split(
                ":",
                1,
            )[1]

            if re.fullmatch(
                r"[0-9a-f]{64}",
                candidate,
            ):
                sha256 = candidate

    sha_asset = None

    if zip_asset:
        zip_name = str(
            zip_asset.get("name")
        )

        acceptable_names = {
            f"{zip_name}.sha256",
            f"{zip_name}.sha256.txt",
        }

        sha_asset = next(
            (
                asset
                for asset in assets
                if asset.get("name")
                in acceptable_names
            ),
            None,
        )

    if (
        sha256 is None
        and sha_asset is not None
    ):
        sha_text = _read_text_url(
            sha_asset[
                "browser_download_url"
            ]
        )

        match = re.search(
            r"\b([0-9a-fA-F]{64})\b",
            sha_text,
        )

        if match:
            sha256 = (
                match.group(1).lower()
            )

    return {
        "version": version_text,
        "tag": release.get(
            "tag_name",
            f"v{version_text}",
        ),
        "name": release.get(
            "name",
            f"v{version_text}",
        ),
        "notes": release.get(
            "body",
            "",
        )
        or "",
        "html_url": release.get(
            "html_url",
            RELEASES_URL,
        ),
        "zip_name":
            zip_asset.get("name")
            if zip_asset
            else None,
        "zip_url":
            zip_asset.get(
                "browser_download_url"
            )
            if zip_asset
            else None,
        "zip_size":
            int(
                zip_asset.get(
                    "size",
                    0,
                )
                or 0
            )
            if zip_asset
            else 0,
        "sha256": sha256,
    }


def is_frozen_build() -> bool:
    return bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    )


def download_update(
    info: dict,
    progress_callback=None,
    cancel_event:
        threading.Event | None = None,
) -> Path:
    url = info.get(
        "zip_url"
    )

    expected_hash = str(
        info.get(
            "sha256",
            "",
        )
        or ""
    ).lower()

    if not url:
        raise UpdateError(
            "В GitHub Release отсутствует Windows ZIP."
        )

    if not re.fullmatch(
        r"[0-9a-f]{64}",
        expected_hash,
    ):
        raise UpdateError(
            "Для релиза не опубликован SHA-256. "
            "Автоустановка отключена из соображений безопасности."
        )

    version = str(
        info.get(
            "version",
            "unknown",
        )
    )

    target_dir = (
        UPDATES_DIR
        / f"v{version}"
    )

    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    target = (
        target_dir
        / "update.zip"
    )

    temp_target = (
        target_dir
        / "update.zip.part"
    )

    for path in (
        target,
        temp_target,
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Dota2voice2text-Updater",
            "Accept":
                "application/octet-stream",
        },
    )

    hasher = hashlib.sha256()
    received = 0
    expected_total = int(
        info.get(
            "zip_size",
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

            with temp_target.open(
                "wb"
            ) as output:
                while True:
                    if (
                        cancel_event
                        is not None
                        and cancel_event.is_set()
                    ):
                        raise UpdateCancelled(
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
                                99,
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

        actual_hash = (
            hasher.hexdigest().lower()
        )

        if actual_hash != expected_hash:
            raise UpdateError(
                "SHA-256 обновления не совпал. "
                "Установка отменена."
            )

        if not zipfile.is_zipfile(
            temp_target
        ):
            raise UpdateError(
                "Скачанный файл не является корректным ZIP-архивом."
            )

        temp_target.replace(
            target
        )

        if progress_callback:
            progress_callback(
                100,
                received,
                expected_total,
            )

        return target

    except urllib.error.URLError as exc:
        raise UpdateError(
            "Не удалось скачать обновление."
        ) from exc

    finally:
        if temp_target.exists():
            try:
                temp_target.unlink()
            except OSError:
                pass


def launch_installer(
    zip_path: Path,
):
    if not is_frozen_build():
        raise UpdateError(
            "Автоустановка доступна только в собранной Windows-версии."
        )

    exe_path = Path(
        sys.executable
    ).resolve()

    install_dir = (
        exe_path.parent
    )

    script_path = (
        Path(
            tempfile.gettempdir()
        )
        / "Dota2voice2text-apply-update.ps1"
    )

    script = """param(
    [int]$ProcessId,
    [string]$ZipPath,
    [string]$InstallDir,
    [string]$ExePath
)

$ErrorActionPreference = "Stop"

try {
    Wait-Process -Id $ProcessId -Timeout 90 -ErrorAction SilentlyContinue
}
catch {
}

Start-Sleep -Milliseconds 800

$stage = Join-Path $env:TEMP (
    "Dota2voice2text-update-" + [guid]::NewGuid().ToString("N")
)

try {
    New-Item -ItemType Directory -Force $stage | Out-Null

    Expand-Archive `
        -Path $ZipPath `
        -DestinationPath $stage `
        -Force

    $entries = Get-ChildItem $stage

    if ($entries.Count -eq 1 -and $entries[0].PSIsContainer) {
        $source = $entries[0].FullName
    }
    else {
        $source = $stage
    }

    Get-ChildItem $source -Force | ForEach-Object {
        Copy-Item `
            $_.FullName `
            (Join-Path $InstallDir $_.Name) `
            -Recurse `
            -Force
    }

    Start-Process -FilePath $ExePath
}
finally {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
    Remove-Item $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
}
"""

    script_path.write_text(
        script,
        encoding="utf-8-sig",
    )

    creationflags = 0

    if os.name == "nt":
        creationflags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-ProcessId",
            str(os.getpid()),
            "-ZipPath",
            str(
                Path(zip_path).resolve()
            ),
            "-InstallDir",
            str(install_dir),
            "-ExePath",
            str(exe_path),
        ],
        close_fds=True,
        creationflags=creationflags,
    )


def cleanup_old_updates():
    if not UPDATES_DIR.exists():
        return

    for path in UPDATES_DIR.iterdir():
        try:
            if path.is_dir():
                shutil.rmtree(
                    path,
                    ignore_errors=True,
                )
            else:
                path.unlink()
        except OSError:
            pass
