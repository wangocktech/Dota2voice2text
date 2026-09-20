$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"
if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$patch = Join-Path $scriptDir "PATCH_FILES"

if (-not (Test-Path (Join-Path $project "app.py"))) {
    throw "Не найден проект Dota2voice2text."
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $project "_quality_backup_$stamp"

New-Item -ItemType Directory -Path (Join-Path $backup "src\text") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $backup "data") -Force | Out-Null

$oldFiles = @(
    "src\text\translator.py",
    "data\dota_translation_glossary.json",
    "data\dota_translation_phrases.json"
)

foreach ($rel in $oldFiles) {
    $src = Join-Path $project $rel
    if (Test-Path $src) {
        $dst = Join-Path $backup $rel
        New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
        Copy-Item $src $dst -Force
    }
}

Copy-Item (Join-Path $patch "src\text\translator.py") `
    (Join-Path $project "src\text\translator.py") -Force

Copy-Item (Join-Path $patch "data\dota_translation_glossary.json") `
    (Join-Path $project "data\dota_translation_glossary.json") -Force

Copy-Item (Join-Path $patch "data\dota_translation_phrases.json") `
    (Join-Path $project "data\dota_translation_phrases.json") -Force

New-Item -ItemType Directory -Path (Join-Path $project "tools") -Force | Out-Null

Copy-Item (Join-Path $patch "tools\test_translation_quality.py") `
    (Join-Path $project "tools\test_translation_quality.py") -Force

$python = Join-Path $project ".venv313\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Не найден .venv313."
}

Push-Location $project
try {
    & $python -m py_compile `
        "src\text\translator.py" `
        "tools\test_translation_quality.py"

    if ($LASTEXITCODE -ne 0) {
        throw "Проверка синтаксиса не пройдена."
    }

    Write-Host ""
    Write-Host "=== QUALITY TEST ===" -ForegroundColor Cyan
    & $python -m tools.test_translation_quality

    if ($LASTEXITCODE -ne 0) {
        throw "Тест переводчика завершился с ошибкой."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "ГОТОВО. Quality patch установлен." -ForegroundColor Green
Write-Host "Backup: $backup" -ForegroundColor Gray
Write-Host ""
Write-Host "Запуск приложения:" -ForegroundColor Cyan
Write-Host "& `"$python`" `"$project\app.py`""

