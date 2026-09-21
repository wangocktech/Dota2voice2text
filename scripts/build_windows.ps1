$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

$python = Join-Path $project ".venv313\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Missing .venv313"
}

$manifest = Join-Path $project "data\translation_model_manifest.json"

if (-not (Test-Path $manifest)) {
    throw "Missing data\translation_model_manifest.json"
}

$manifestData = Get-Content $manifest -Raw | ConvertFrom-Json

if (
    -not $manifestData.sha256 -or
    $manifestData.sha256 -eq ("0" * 64)
) {
    throw "Translation model manifest SHA-256 is not configured."
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
        --icon "assets\icons\app_icon.ico" `
        --collect-all sherpa_onnx `
        --collect-all ctranslate2 `
        --collect-all sentencepiece `
        --exclude-module faster_whisper `
        --exclude-module transformers `
        --exclude-module torch `
        --exclude-module huggingface_hub `
        --exclude-module av `
        --add-data "models\sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19;models\sherpa-onnx-nemo-ctc-giga-am-v2-russian-2025-04-19" `
        --add-data "models\rupunct-small-onnx;models\rupunct-small-onnx" `
        --add-data "data;data" `
        --add-data "assets;assets" `
        app.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    $dist = Join-Path $project "dist\Dota2voice2text"
    $exe = Join-Path $dist "Dota2voice2text.exe"

    if (-not (Test-Path $exe)) {
        throw "Built EXE not found: $exe"
    }

    $size = (
        Get-ChildItem $dist -Recurse -File |
        Measure-Object Length -Sum
    ).Sum

    Write-Host ""
    Write-Host "BUILD OK" -ForegroundColor Green
    Write-Host $exe -ForegroundColor Cyan
    Write-Host ("Folder size: {0:N1} MB" -f ($size / 1MB)) -ForegroundColor Cyan
}
finally {
    Pop-Location
}