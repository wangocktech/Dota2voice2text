$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

$modelDir = Join-Path $project "models\opus-mt-ru-en-ct2-int8"
$manifestPath = Join-Path $project "data\translation_model_manifest.json"

if (-not (Test-Path $modelDir)) {
    throw "Не найдена локальная модель: $modelDir"
}

$required = @(
    "model.bin",
    "config.json",
    "source.spm",
    "target.spm",
    "shared_vocabulary.json"
)

foreach ($file in $required) {
    if (-not (Test-Path (Join-Path $modelDir $file))) {
        throw "В модели отсутствует файл: $file"
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) не найден."
}

Push-Location $project

try {
    & gh auth status *> $null

    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI не авторизован. Выполни: gh auth login"
    }

    $repo = (
        & gh repo view --json nameWithOwner --jq ".nameWithOwner"
    ).Trim()

    if (-not $repo) {
        throw "Не удалось определить GitHub-репозиторий."
    }

    $releaseDir = Join-Path $project ".release"
    $stageDir = Join-Path $releaseDir "translation-model-v1-stage"

    Remove-Item $stageDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $stageDir | Out-Null

    foreach ($file in $required) {
        Copy-Item `
            (Join-Path $modelDir $file) `
            (Join-Path $stageDir $file) `
            -Force
    }

    @"
Dota2voice2text RU→EN Translation Model v1

Source model:
Helsinki-NLP/opus-mt-ru-en

Source:
https://huggingface.co/Helsinki-NLP/opus-mt-ru-en

License:
CC-BY-4.0

This archive contains a CTranslate2 INT8 conversion used by Dota2voice2text.
The conversion changes the runtime format/quantization, not the intended model task.
"@ | Set-Content `
        (Join-Path $stageDir "MODEL_INFO.txt") `
        -Encoding UTF8

    $assetName = "Dota2voice2text-translation-model-v1.zip"
    $archive = Join-Path $releaseDir $assetName

    Remove-Item $archive -Force -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "Упаковываю модель..." -ForegroundColor Cyan

    Compress-Archive `
        -Path (Join-Path $stageDir "*") `
        -DestinationPath $archive `
        -CompressionLevel Optimal `
        -Force

    $hash = (
        Get-FileHash $archive -Algorithm SHA256
    ).Hash.ToLower()

    $size = (Get-Item $archive).Length

    $tag = "translation-model-v1"
    $url = "https://github.com/$repo/releases/download/$tag/$assetName"

    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    $manifest.version = "1"
    $manifest.archive_name = $assetName
    $manifest.url = $url
    $manifest.sha256 = $hash
    $manifest.size_bytes = $size

    $manifest |
        ConvertTo-Json -Depth 10 |
        Set-Content $manifestPath -Encoding UTF8

    & gh release view $tag --repo $repo *> $null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Обновляю asset GitHub Release..." -ForegroundColor Cyan

        & gh release upload `
            $tag `
            $archive `
            --repo $repo `
            --clobber
    }
    else {
        Write-Host "Создаю GitHub Release для модели..." -ForegroundColor Cyan

        & gh release create `
            $tag `
            $archive `
            --repo $repo `
            --title "Dota2voice2text Translation Model v1" `
            --notes "Runtime RU→EN translation model for Dota2voice2text. Based on Helsinki-NLP/opus-mt-ru-en (CC-BY-4.0)."
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось опубликовать модель в GitHub Releases."
    }

    Write-Host ""
    Write-Host "МОДЕЛЬ ОПУБЛИКОВАНА." -ForegroundColor Green
    Write-Host "Repo:   $repo"
    Write-Host "Tag:    $tag"
    Write-Host "Asset:  $assetName"
    Write-Host ("Size:   {0:N1} МБ" -f ($size / 1MB))
    Write-Host "SHA256: $hash"
    Write-Host "URL:    $url"
    Write-Host ""
    Write-Host "Manifest обновлён:" -ForegroundColor Green
    Write-Host $manifestPath
}
finally {
    Remove-Item $stageDir -Recurse -Force -ErrorAction SilentlyContinue
    Pop-Location
}
