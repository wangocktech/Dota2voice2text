param(
    [string]$ProjectPath = "C:\Users\wango\Desktop\dota2voice2text"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$patchRoot = Join-Path $scriptDir "PATCH_FILES"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $ProjectPath = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $ProjectPath "app.py"))) {
    throw "Не найден проект Dota2voice2text: $ProjectPath"
}

if (-not (Test-Path $patchRoot)) {
    throw "Не найдена папка PATCH_FILES рядом с установщиком."
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $ProjectPath "_v020_backup_$stamp"

Write-Host ""
Write-Host "=== Dota2voice2text v0.2.0 Model Manager ===" -ForegroundColor Cyan
Write-Host "Проект: $ProjectPath"
Write-Host "Backup: $backup"
Write-Host ""

$files = @(
    "src\gui\main_window.py",
    "src\core\controller.py",
    "src\text\translator.py",
    "src\text\translation_model_manager.py",
    "data\translation_model_manifest.json",
    "BUILD_WITH_TRANSLATION.ps1",
    "PUBLISH_TRANSLATION_MODEL.ps1",
    "requirements.txt"
)

foreach ($rel in $files) {
    $current = Join-Path $ProjectPath $rel

    if (Test-Path $current) {
        $backupFile = Join-Path $backup $rel
        New-Item -ItemType Directory -Force (Split-Path -Parent $backupFile) | Out-Null
        Copy-Item $current $backupFile -Force
    }
}

foreach ($rel in $files) {
    $source = Join-Path $patchRoot $rel

    if (-not (Test-Path $source)) {
        throw "В патче отсутствует: $rel"
    }

    $target = Join-Path $ProjectPath $rel
    New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
    Copy-Item $source $target -Force
}

$gitignore = Join-Path $ProjectPath ".gitignore"
$ignoreLines = @(
    ".release/",
    "models/opus-mt-ru-en-ct2-int8/"
)

if (-not (Test-Path $gitignore)) {
    New-Item -ItemType File -Path $gitignore -Force | Out-Null
}

$gitignoreText = Get-Content $gitignore -Raw -ErrorAction SilentlyContinue

foreach ($line in $ignoreLines) {
    if ($gitignoreText -notmatch [regex]::Escape($line)) {
        Add-Content $gitignore "`n$line"
        $gitignoreText += "`n$line"
    }
}

$python = Join-Path $ProjectPath ".venv313\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Не найден .venv313\Scripts\python.exe"
}

Push-Location $ProjectPath

try {
    Write-Host "Проверяю Python-файлы..." -ForegroundColor Cyan

    & $python -m py_compile `
        "src\gui\main_window.py" `
        "src\core\controller.py" `
        "src\text\translator.py" `
        "src\text\translation_model_manager.py"

    if ($LASTEXITCODE -ne 0) {
        throw "Python syntax check завершился с ошибкой."
    }

    & $python -c "import ctranslate2, sentencepiece, PySide6, sherpa_onnx, onnxruntime; print('Python dependencies: OK')"

    if ($LASTEXITCODE -ne 0) {
        throw "Не хватает Python-зависимостей."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "ПАТЧ УСТАНОВЛЕН." -ForegroundColor Green
Write-Host "Backup: $backup" -ForegroundColor Gray
Write-Host ""
Write-Host "Следующий шаг:" -ForegroundColor Yellow
Write-Host "  .\PUBLISH_TRANSLATION_MODEL.ps1"
Write-Host ""
