$ErrorActionPreference = "Stop"

$Tag = "v0.3.0"
$Project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) ".git")) {
    $Project = (Get-Location).Path
}

Push-Location $Project

try {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host " Dota2voice2text - fix existing v0.3.0 tag" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""

    gh auth status | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI не авторизован."
    }

    git fetch origin --tags --prune
    if ($LASTEXITCODE -ne 0) {
        throw "git fetch завершился с ошибкой."
    }

    $localExists = $false
    git rev-parse -q --verify "refs/tags/$Tag" *> $null
    if ($LASTEXITCODE -eq 0) {
        $localExists = $true
    }

    $remoteTag = git ls-remote --tags origin "refs/tags/$Tag"
    $remoteExists = -not [string]::IsNullOrWhiteSpace(($remoteTag -join ""))

    gh release view $Tag *> $null
    $releaseExists = ($LASTEXITCODE -eq 0)

    Write-Host "Локальный тег:  $localExists"
    Write-Host "Удалённый тег:  $remoteExists"
    Write-Host "GitHub Release:  $releaseExists"
    Write-Host ""

    if (-not $remoteExists -and -not $releaseExists) {
        if ($localExists) {
            Write-Host "На GitHub v0.3.0 ещё нет. Удаляю только старый локальный тег..." -ForegroundColor Yellow
            git tag -d $Tag
            if ($LASTEXITCODE -ne 0) {
                throw "Не удалось удалить локальный тег $Tag."
            }
        }

        Write-Host ""
        Write-Host "Локальный конфликт устранён." -ForegroundColor Green
        Write-Host "Перезапускаю релизный скрипт..." -ForegroundColor Cyan

        & ".\RELEASE_V030_WITH_OVERLAY.ps1"
        exit $LASTEXITCODE
    }

    Write-Host "На GitHub уже существует тег и/или Release $Tag." -ForegroundColor Yellow
    Write-Host "Чтобы переиздать именно v0.3.0, старый удалённый релиз/тег нужно удалить." -ForegroundColor Yellow
    Write-Host ""
    $answer = Read-Host "Удалить существующий GitHub v0.3.0 и опубликовать его заново? [Y/N]"

    if ($answer -notmatch '^(y|yes|д|да)$') {
        Write-Host "Ничего не удалено. Лучше выпустить v0.3.1." -ForegroundColor Cyan
        exit 0
    }

    if ($releaseExists) {
        Write-Host "Удаляю GitHub Release $Tag..." -ForegroundColor Cyan
        gh release delete $Tag --yes
        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось удалить GitHub Release $Tag."
        }
    }

    if ($remoteExists) {
        Write-Host "Удаляю удалённый тег $Tag..." -ForegroundColor Cyan
        git push origin ":refs/tags/$Tag"
        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось удалить удалённый тег $Tag."
        }
    }

    if ($localExists) {
        Write-Host "Удаляю локальный тег $Tag..." -ForegroundColor Cyan
        git tag -d $Tag
        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось удалить локальный тег $Tag."
        }
    }

    Write-Host ""
    Write-Host "Старый v0.3.0 удалён. Запускаю публикацию заново..." -ForegroundColor Green
    Write-Host ""

    & ".\RELEASE_V030_WITH_OVERLAY.ps1"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
