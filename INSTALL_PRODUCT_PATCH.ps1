$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $project "app.py"))) {
    throw "Не найден проект Dota2voice2text."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$patchDir = Join-Path $scriptDir "PATCH_FILES"

if (-not (Test-Path $patchDir)) {
    throw "Не найдена папка PATCH_FILES."
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $project "_product_backup_$stamp"

Write-Host ""
Write-Host "=== Dota2voice2text Product Patch ===" -ForegroundColor Cyan
Write-Host "Проект: $project"
Write-Host "Backup: $backup"
Write-Host ""

$files = @(
    "app.py",
    "src\gui\main_window.py",
    "src\gui\about_dialog.py",
    "src\utils\logging_setup.py",
    "src\update\__init__.py",
    "src\update\update_manager.py",
    "PUBLISH_APP_RELEASE.ps1"
)

foreach ($rel in $files) {
    $source = Join-Path $patchDir $rel
    $target = Join-Path $project $rel

    if (-not (Test-Path $source)) {
        throw "В патче отсутствует: $rel"
    }

    if (Test-Path $target) {
        $backupTarget = Join-Path $backup $rel
        New-Item -ItemType Directory -Force (Split-Path -Parent $backupTarget) | Out-Null
        Copy-Item $target $backupTarget -Force
    }

    New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
    Copy-Item $source $target -Force
}

$python = Join-Path $project ".venv313\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Не найден .venv313."
}

Push-Location $project

try {
    Write-Host "Проверяю Python-файлы..." -ForegroundColor Cyan

    & $python -m py_compile `
        "app.py" `
        "src\gui\main_window.py" `
        "src\gui\about_dialog.py" `
        "src\utils\logging_setup.py" `
        "src\update\update_manager.py"

    if ($LASTEXITCODE -ne 0) {
        throw "Python-файлы не прошли py_compile."
    }

    Write-Host "Python: OK" -ForegroundColor Green

    & $python -c "from src.update.update_manager import check_for_update; from src.version import APP_VERSION; print('Update checker import: OK, current version:', APP_VERSION)"

    if ($LASTEXITCODE -ne 0) {
        throw "Update manager не импортируется."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "ПАТЧ УСТАНОВЛЕН." -ForegroundColor Green
Write-Host ""
Write-Host "Добавлено:" -ForegroundColor Cyan
Write-Host "  - логи в %LOCALAPPDATA%\Dota2voice2text\logs"
Write-Host "  - окно 'О программе'"
Write-Host "  - фоновая проверка GitHub Releases"
Write-Host "  - безопасная загрузка обновления с SHA-256"
Write-Host "  - автоустановка обновления для готового EXE"
Write-Host "  - PUBLISH_APP_RELEASE.ps1"
Write-Host ""
Write-Host "Backup: $backup" -ForegroundColor Gray
Write-Host ""
Write-Host "Сейчас запусти:" -ForegroundColor Yellow
Write-Host "& `"$python`" `"$project\app.py`""
