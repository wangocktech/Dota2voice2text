$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Dota2voice2text: RU -> EN translation patch ===" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultProject = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}
elseif (Test-Path (Join-Path $defaultProject "app.py")) {
    $project = $defaultProject
}
else {
    throw "Не найден проект Dota2voice2text. Запусти этот файл из папки проекта или проверь путь: $defaultProject"
}

$patchFiles = Join-Path $scriptDir "PATCH_FILES"

if (-not (Test-Path $patchFiles)) {
    throw "Рядом с INSTALL_TRANSLATION.ps1 нет папки PATCH_FILES."
}

Write-Host "[1/7] Проект: $project" -ForegroundColor Gray

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $project "_translation_backup_$stamp"

New-Item -ItemType Directory -Path $backup -Force | Out-Null

$backupItems = @(
    "src\core\controller.py",
    "src\gui\main_window.py",
    "src\config\settings.py",
    "src\text\translator.py",
    "data\dota_translation_glossary.json",
    "requirements.txt"
)

foreach ($item in $backupItems) {
    $source = Join-Path $project $item

    if (Test-Path $source) {
        $dest = Join-Path $backup $item
        $destDir = Split-Path -Parent $dest
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Copy-Item $source $dest -Force
    }
}

Write-Host "[2/7] Backup: $backup" -ForegroundColor Gray

Copy-Item (Join-Path $patchFiles "src\core\controller.py") `
    (Join-Path $project "src\core\controller.py") -Force

Copy-Item (Join-Path $patchFiles "src\gui\main_window.py") `
    (Join-Path $project "src\gui\main_window.py") -Force

Copy-Item (Join-Path $patchFiles "src\config\settings.py") `
    (Join-Path $project "src\config\settings.py") -Force

Copy-Item (Join-Path $patchFiles "src\text\translator.py") `
    (Join-Path $project "src\text\translator.py") -Force

Copy-Item (Join-Path $patchFiles "data\dota_translation_glossary.json") `
    (Join-Path $project "data\dota_translation_glossary.json") -Force

Copy-Item (Join-Path $patchFiles "requirements.txt") `
    (Join-Path $project "requirements.txt") -Force

Write-Host "[3/7] Готовые файлы установлены." -ForegroundColor Green

# Prefer an existing Python 3.13 project venv.
$candidates = @(
    (Join-Path $project ".venv313\Scripts\python.exe"),
    (Join-Path $project ".venv\Scripts\python.exe")
)

$python = $null

foreach ($candidate in $candidates) {
    if (Test-Path $candidate) {
        $version = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"

        if ($version.Trim() -eq "3.13") {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    Write-Host "[4/7] Python 3.13 venv не найден. Создаю .venv313..." -ForegroundColor Yellow

    $py313 = Get-Command py -ErrorAction SilentlyContinue

    if (-not $py313) {
        throw "Не найден Python Launcher (py). Установи Python 3.13 и запусти скрипт ещё раз."
    }

    Push-Location $project

    try {
        & py -3.13 -m venv .venv313

        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось создать .venv313. Проверь, что Python 3.13 установлен."
        }
    }
    finally {
        Pop-Location
    }

    $python = Join-Path $project ".venv313\Scripts\python.exe"

    Write-Host "Устанавливаю зависимости проекта в новый venv..." -ForegroundColor Yellow
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $project "requirements.txt")

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось установить requirements.txt"
    }
}
else {
    Write-Host "[4/7] Использую Python 3.13: $python" -ForegroundColor Green
}

Write-Host "[5/7] Ставлю runtime перевода..." -ForegroundColor Gray

& $python -m pip install "ctranslate2==4.8.2" "sentencepiece>=0.2.0"

if ($LASTEXITCODE -ne 0) {
    throw "Не удалось установить ctranslate2/sentencepiece."
}

$modelDir = Join-Path $project "models\opus-mt-ru-en-ct2-int8"
$modelFile = Join-Path $modelDir "model.bin"
$sourceSpm = Join-Path $modelDir "source.spm"
$targetSpm = Join-Path $modelDir "target.spm"

if (
    -not (Test-Path $modelFile) -or
    -not (Test-Path $sourceSpm) -or
    -not (Test-Path $targetSpm)
) {
    Write-Host ""
    Write-Host "[6/7] Модель перевода не найдена. Скачиваю и конвертирую OPUS-MT RU->EN..." -ForegroundColor Yellow
    Write-Host "Это делается один раз и может занять несколько минут." -ForegroundColor Yellow

    & $python -m pip install "transformers>=4.40,<5" torch

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось установить временные зависимости для конвертации модели."
    }

    if (Test-Path $modelDir) {
        Remove-Item $modelDir -Recurse -Force
    }

    $converter = Join-Path (Split-Path $python -Parent) "ct2-transformers-converter.exe"

    if (-not (Test-Path $converter)) {
        throw "Не найден ct2-transformers-converter.exe"
    }

    Push-Location $project

    try {
        & $converter `
            --model "Helsinki-NLP/opus-mt-ru-en" `
            --output_dir "models\opus-mt-ru-en-ct2-int8" `
            --quantization int8 `
            --copy_files source.spm target.spm

        if ($LASTEXITCODE -ne 0) {
            throw "Конвертация модели завершилась с ошибкой."
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[6/7] Модель перевода уже установлена — пропускаю скачивание." -ForegroundColor Green
}

Write-Host "[7/7] Проверяю файлы и перевод..." -ForegroundColor Gray

Push-Location $project

try {
    & $python -m py_compile `
        "src\core\controller.py" `
        "src\gui\main_window.py" `
        "src\config\settings.py" `
        "src\text\translator.py"

    if ($LASTEXITCODE -ne 0) {
        throw "Python-файлы не прошли проверку синтаксиса."
    }

    & $python -c "from src.text.translator import EnglishTranslator; t=EnglishTranslator(); text,sec=t.translate('Поставьте варды на миду, у них нет байбека.'); print(); print('TEST:', text); print(f'TIME: {sec:.3f} sec')"

    if ($LASTEXITCODE -ne 0) {
        throw "Тест переводчика завершился с ошибкой."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "ГОТОВО. Перевод RU -> EN установлен." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Запуск приложения:" -ForegroundColor Cyan
Write-Host "& `"$python`" `"$project\app.py`""
Write-Host ""
Write-Host "В окне появится галочка:" -ForegroundColor Cyan
Write-Host "  Автоматически переводить на английский"
Write-Host ""
Write-Host "Backup исходных файлов:" -ForegroundColor Gray
Write-Host "  $backup"
Write-Host ""
