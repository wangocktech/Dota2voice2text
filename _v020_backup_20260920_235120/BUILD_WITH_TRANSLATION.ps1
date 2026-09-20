$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

$python = Join-Path $project ".venv313\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Не найден .venv313. Сначала запусти INSTALL_TRANSLATION.ps1"
}

Push-Location $project

try {
    Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
    Remove-Item -Force Dota2voice2text.spec -ErrorAction SilentlyContinue

    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name "Dota2voice2text" `
        --collect-all sherpa_onnx `
        --collect-all ctranslate2 `
        --collect-all sentencepiece `
        --add-data "models\sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19;models\sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19" `
        --add-data "models\rupunct-small-onnx;models\rupunct-small-onnx" `
        --add-data "models\opus-mt-ru-en-ct2-int8;models\opus-mt-ru-en-ct2-int8" `
        --add-data "data;data" `
        --add-data "assets;assets" `
        app.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller завершился с ошибкой."
    }

    Write-Host ""
    Write-Host "ГОТОВО:" -ForegroundColor Green
    Write-Host "$project\dist\Dota2voice2text\Dota2voice2text.exe"
}
finally {
    Pop-Location
}
