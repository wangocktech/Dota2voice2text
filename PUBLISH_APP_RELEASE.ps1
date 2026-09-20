$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $project "app.py"))) {
    throw "Не найден проект Dota2voice2text."
}

$python = Join-Path $project ".venv313\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Не найден .venv313."
}

Push-Location $project

try {
    & ".\BUILD_WITH_TRANSLATION.ps1"

    if ($LASTEXITCODE -ne 0) {
        throw "Сборка завершилась с ошибкой."
    }

    $version = (
        & $python -c "from src.version import APP_VERSION; print(APP_VERSION)"
    ).Trim()

    if (-not $version) {
        throw "Не удалось определить APP_VERSION."
    }

    $assetName = "Dota2voice2text-v$version-windows-x64.zip"
    $asset = Join-Path $project $assetName
    $shaFile = "$asset.sha256"

    Remove-Item $asset -Force -ErrorAction SilentlyContinue
    Remove-Item $shaFile -Force -ErrorAction SilentlyContinue

    Compress-Archive `
        -Path ".\dist\Dota2voice2text\*" `
        -DestinationPath $asset `
        -CompressionLevel Optimal `
        -Force

    $hash = (
        Get-FileHash `
            $asset `
            -Algorithm SHA256
    ).Hash.ToLower()

    "$hash  $assetName" |
        Set-Content `
            $shaFile `
            -Encoding ASCII

    Write-Host ""
    Write-Host "РЕЛИЗ ПОДГОТОВЛЕН:" -ForegroundColor Green
    Write-Host $asset
    Write-Host $shaFile
    Write-Host "SHA256: $hash" -ForegroundColor Cyan

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "gh не найден. Файлы релиза готовы локально." -ForegroundColor Yellow
        exit 0
    }

    & gh auth status *> $null

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "gh не авторизован. Выполни gh auth login." -ForegroundColor Yellow
        exit 0
    }

    $repo = (
        & gh repo view `
            --json nameWithOwner `
            --jq ".nameWithOwner"
    ).Trim()

    $tag = "v$version"

    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    & gh release view `
        $tag `
        --repo $repo *> $null

    $exists = (
        $LASTEXITCODE -eq 0
    )

    $ErrorActionPreference = $oldEap

    if ($exists) {
        & gh release upload `
            $tag `
            $asset `
            $shaFile `
            --repo $repo `
            --clobber
    }
    else {
        & gh release create `
            $tag `
            $asset `
            $shaFile `
            --repo $repo `
            --title "Dota2voice2text v$version" `
            --notes @"
## Dota2voice2text v$version

- Локальное распознавание русской речи
- Dota 2 словарь и коррекция терминов
- Автоматический RU → EN перевод
- Модель перевода скачивается по требованию
- Проверка обновлений
- Логи и диагностика
- Системный трей и автозапуск

Скачайте ZIP, полностью распакуйте его и запустите Dota2voice2text.exe.
"@
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось опубликовать GitHub Release."
    }

    Write-Host ""
    Write-Host "GITHUB RELEASE ГОТОВ:" -ForegroundColor Green
    Write-Host "https://github.com/$repo/releases/tag/$tag"
}
finally {
    Pop-Location
}
