param(
    [string]$ProjectPath = "C:\Users\wango\Desktop\dota2voice2text"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $ProjectPath = (Get-Location).Path
}

& (Join-Path $scriptDir "INSTALL_MODEL_MANAGER.ps1") `
    -ProjectPath $ProjectPath

if ($LASTEXITCODE -ne 0) {
    throw "Установка патча завершилась с ошибкой."
}

Write-Host ""
Write-Host "Сейчас будет создан/обновлён GitHub Release:" -ForegroundColor Yellow
Write-Host "translation-model-v1" -ForegroundColor Yellow
Write-Host "В него будет загружена твоя локальная INT8-модель RU→EN." -ForegroundColor Yellow
Write-Host ""

Push-Location $ProjectPath

try {
    & ".\PUBLISH_TRANSLATION_MODEL.ps1"

    if ($LASTEXITCODE -ne 0) {
        throw "Публикация модели завершилась с ошибкой."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "ВСЁ ГОТОВО." -ForegroundColor Green
Write-Host ""
Write-Host "Запусти приложение:" -ForegroundColor Cyan
Write-Host "& `"$ProjectPath\.venv313\Scripts\python.exe`" `"$ProjectPath\app.py`""
Write-Host ""
Write-Host "Включи «Автоматически переводить на английский»."
Write-Host "Приложение предложит скачать модель и покажет прогресс."
