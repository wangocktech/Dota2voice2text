param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$Project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) ".git")) {
    $Project = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $Project ".git"))) {
    throw "Не найден Git-репозиторий Dota2voice2text."
}

Push-Location $Project

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "git не найден."
    }

    $trackedDirty = git status --porcelain --untracked-files=no

    if ($trackedDirty) {
        Write-Host "Есть незакоммиченные изменения:" -ForegroundColor Yellow
        git status --short --untracked-files=no
        throw "Сначала закоммить текущие изменения."
    }

    $tag = "v$Version"

    & git rev-parse $tag *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "Тег $tag уже существует."
    }

    $versionFile = "src\version.py"

    if (-not (Test-Path $versionFile)) {
        throw "Не найден src\version.py."
    }

    $content = Get-Content $versionFile -Raw

    if ($content -notmatch 'APP_VERSION\s*=') {
        throw "В src\version.py не найден APP_VERSION."
    }

    $content = [regex]::Replace(
        $content,
        'APP_VERSION\s*=\s*["''][^"'']+["'']',
        "APP_VERSION = `"$Version`"",
        1
    )

    Set-Content $versionFile $content -Encoding UTF8

    git add src/version.py
    git commit -m "Release $tag"

    if ($LASTEXITCODE -ne 0) {
        throw "git commit завершился с ошибкой."
    }

    git push

    if ($LASTEXITCODE -ne 0) {
        throw "git push завершился с ошибкой."
    }

    git tag $tag
    git push origin $tag

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось отправить тег $tag."
    }

    Write-Host ""
    Write-Host "ГОТОВО." -ForegroundColor Green
    Write-Host "GitHub Actions теперь автоматически:" -ForegroundColor Cyan
    Write-Host "  - скачает GigaAM и RUPunct;"
    Write-Host "  - соберёт portable ZIP;"
    Write-Host "  - соберёт Setup.exe;"
    Write-Host "  - посчитает SHA-256;"
    Write-Host "  - создаст GitHub Release $tag."
    Write-Host ""

    if (Get-Command gh -ErrorAction SilentlyContinue) {
        gh run list --limit 5
        gh repo view --web
    }
}
finally {
    Pop-Location
}
