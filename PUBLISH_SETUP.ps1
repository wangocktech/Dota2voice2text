$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) ".git")) {
    $project = (Get-Location).Path
}

$setup = Join-Path $project "installer\output\Dota2voice2text-v0.2.0-Setup.exe"

if (-not (Test-Path $setup)) {
    throw "Сначала собери installer через BUILD_INSTALLER.ps1."
}

Push-Location $project

try {
    gh release view v0.2.0 *> $null

    if ($LASTEXITCODE -ne 0) {
        throw "GitHub Release v0.2.0 не найден."
    }

    gh release upload v0.2.0 $setup --clobber

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось загрузить Setup.exe в GitHub Release."
    }

    Write-Host ""
    Write-Host "Setup.exe загружен в GitHub Release v0.2.0." -ForegroundColor Green
    gh release view v0.2.0 --web
}
finally {
    Pop-Location
}
