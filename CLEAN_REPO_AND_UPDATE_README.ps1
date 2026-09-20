$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) ".git")) {
    $project = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $project ".git"))) {
    throw "Не найден Git-репозиторий Dota2voice2text."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location $project

try {
    $dirty = git status --porcelain

    if ($dirty) {
        Write-Host ""
        Write-Host "В репозитории есть незакоммиченные изменения." -ForegroundColor Yellow
        Write-Host "Сначала закоммить/сохрани их, затем запусти скрипт ещё раз." -ForegroundColor Yellow
        Write-Host ""
        git status --short
        exit 2
    }

    Write-Host ""
    Write-Host "=== CLEAN Dota2voice2text REPOSITORY ===" -ForegroundColor Cyan
    Write-Host ""

    # Replace README and gitignore with clean current versions.
    Copy-Item (Join-Path $scriptDir "README.md") (Join-Path $project "README.md") -Force
    Copy-Item (Join-Path $scriptDir ".gitignore") (Join-Path $project ".gitignore") -Force

    # Root patch/install scripts that were only needed during development.
    Get-ChildItem $project -File -Filter "INSTALL_*.ps1" -ErrorAction SilentlyContinue |
        Remove-Item -Force

    $rootJunk = @(
        "FIX_AND_PUBLISH_MODEL.ps1",
        "TEST_FRESH_MODEL_DOWNLOAD.ps1",
        "README.txt",
        "README_PATCH.txt",
        "requirements-translation.txt",
        "translation_source.zip",
        "v020_current_source.zip",
        "v020_final_source.zip",
        "Dota2voice2text_final_dist.zip"
    )

    foreach ($name in $rootJunk) {
        Remove-Item (Join-Path $project $name) -Force -ErrorAction SilentlyContinue
    }

    # Old generated patch folder.
    Remove-Item (Join-Path $project "PATCH_FILES") -Recurse -Force -ErrorAction SilentlyContinue

    # Temporary backup folders accumulated while we were developing.
    Get-ChildItem $project -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^_.*backup' -or
            $_.Name -match '^_quality_backup' -or
            $_.Name -match '^_translation_backup' -or
            $_.Name -match '^_ui_.*backup' -or
            $_.Name -match '^_v020_backup'
        } |
        Remove-Item -Recurse -Force

    # Root ZIP artifacts are release/source snapshots, not source code.
    Get-ChildItem $project -File -Filter "*.zip" -ErrorAction SilentlyContinue |
        Remove-Item -Force

    # Python cache.
    Get-ChildItem $project -Directory -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "__pycache__" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    Get-ChildItem $project -File -Recurse -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue

    # Obsolete experimental code that is not used by the current pipeline.
    $obsolete = @(
        "src\gui\main_window_backup.py",
        "src\audio\recorder.py",
        "src\speech\whisper_engine.py",
        "src\speech\gigaam_test.py",
        "src\speech\sherpa_test.py",
        "src\speech\sherpa_mic_test.py"
    )

    foreach ($rel in $obsolete) {
        Remove-Item (Join-Path $project $rel) -Force -ErrorAction SilentlyContinue
    }

    # Make sure the files that should remain really exist.
    $required = @(
        "app.py",
        "README.md",
        "LICENSE",
        "requirements.txt",
        "src\core\controller.py",
        "src\speech\gigaam_engine.py",
        "src\text\postprocessor.py",
        "src\text\translator.py",
        "src\text\translation_model_manager.py",
        "BUILD_WITH_TRANSLATION.ps1",
        "PUBLISH_APP_RELEASE.ps1",
        "PUBLISH_TRANSLATION_MODEL.ps1"
    )

    foreach ($rel in $required) {
        if (-not (Test-Path (Join-Path $project $rel))) {
            throw "После очистки не найден обязательный файл: $rel"
        }
    }

    git add -A

    Write-Host ""
    Write-Host "Что будет закоммичено:" -ForegroundColor Cyan
    git status --short

    git commit -m "Clean repository and update README for v0.2.0"

    if ($LASTEXITCODE -ne 0) {
        throw "git commit завершился с ошибкой."
    }

    git push

    if ($LASTEXITCODE -ne 0) {
        throw "git push завершился с ошибкой."
    }

    # Cosmetic GitHub repo metadata.
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        gh repo edit `
            --description "Local voice-to-text and optional RU→EN translation for Dota 2 chat." `
            --add-topic dota2 `
            --add-topic speech-to-text `
            --add-topic voice-to-text `
            --add-topic python `
            --add-topic windows `
            --add-topic offline `
            --add-topic translation *> $null
    }

    Write-Host ""
    Write-Host "ГОТОВО." -ForegroundColor Green
    Write-Host "Репозиторий очищен, README обновлён и изменения отправлены на GitHub." -ForegroundColor Green
}
finally {
    Pop-Location
}
