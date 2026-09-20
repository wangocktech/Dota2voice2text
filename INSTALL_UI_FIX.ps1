$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"
if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $scriptDir "PATCH_FILES\src\gui\main_window.py"
$target = Join-Path $project "src\gui\main_window.py"

if (-not (Test-Path (Join-Path $project "app.py"))) {
    throw "Не найден проект Dota2voice2text."
}

if (-not (Test-Path $source)) {
    throw "В патче отсутствует main_window.py."
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $project "_ui_backup_$stamp"
New-Item -ItemType Directory -Force (Join-Path $backupDir "src\gui") | Out-Null

Copy-Item $target (Join-Path $backupDir "src\gui\main_window.py") -Force
Copy-Item $source $target -Force

$python = Join-Path $project ".venv313\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Не найден .venv313."
}

Push-Location $project
try {
    & $python -m py_compile "src\gui\main_window.py"
    if ($LASTEXITCODE -ne 0) {
        throw "main_window.py не прошёл py_compile."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "UI FIX УСТАНОВЛЕН." -ForegroundColor Green
Write-Host "Backup: $backupDir" -ForegroundColor Gray
Write-Host ""
Write-Host "Запуск:" -ForegroundColor Cyan
Write-Host "& `"$python`" `"$project\app.py`""
