$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

$python = Join-Path $project ".venv313\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Не найден .venv313."
}

$modelDir = Join-Path $env:LOCALAPPDATA "Dota2voice2text\models\opus-mt-ru-en-ct2-int8"

if (Test-Path $modelDir) {
    Write-Host "Удаляю только runtime-копию модели из LOCALAPPDATA..." -ForegroundColor Yellow
    Remove-Item $modelDir -Recurse -Force
}

Write-Host ""
Write-Host "Запускаю приложение." -ForegroundColor Cyan
Write-Host "Включи перевод → должна появиться загрузка модели." -ForegroundColor Cyan

& $python (Join-Path $project "app.py")
