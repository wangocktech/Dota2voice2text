param(
    [string]$ProjectPath = "C:\Users\wango\Desktop\dota2voice2text"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $ProjectPath = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $ProjectPath "app.py"))) {
    throw "Не найден проект Dota2voice2text: $ProjectPath"
}

$source = Join-Path $scriptDir "PUBLISH_TRANSLATION_MODEL.ps1"
$target = Join-Path $ProjectPath "PUBLISH_TRANSLATION_MODEL.ps1"

Copy-Item $source $target -Force

Write-Host "Исправленный PUBLISH_TRANSLATION_MODEL.ps1 установлен." -ForegroundColor Green
Write-Host "Публикую модель..." -ForegroundColor Cyan
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
Write-Host "ГОТОВО." -ForegroundColor Green
Write-Host "Теперь можно запускать приложение и проверять скачивание модели." -ForegroundColor Cyan
