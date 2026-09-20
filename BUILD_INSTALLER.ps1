$ErrorActionPreference = "Stop"

$project = "C:\Users\wango\Desktop\dota2voice2text"

if (Test-Path (Join-Path (Get-Location) "app.py")) {
    $project = (Get-Location).Path
}

if (-not (Test-Path (Join-Path $project "app.py"))) {
    throw "Не найден проект Dota2voice2text."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installerDir = Join-Path $project "installer"
$payload = Join-Path $installerDir "payload"

New-Item -ItemType Directory -Force $installerDir | Out-Null
Remove-Item $payload -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $payload | Out-Null

$dist = Join-Path $project "dist\Dota2voice2text"

if (Test-Path (Join-Path $dist "Dota2voice2text.exe")) {
    Write-Host "Использую текущий dist\Dota2voice2text..." -ForegroundColor Cyan
    Copy-Item (Join-Path $dist "*") $payload -Recurse -Force
}
else {
    $archive = Join-Path $project "Dota2voice2text_final_dist.zip"

    if (-not (Test-Path $archive)) {
        throw "Не найден ни dist\Dota2voice2text, ни Dota2voice2text_final_dist.zip."
    }

    Write-Host "Распаковываю Dota2voice2text_final_dist.zip..." -ForegroundColor Cyan
    Expand-Archive $archive $payload -Force
}

Copy-Item (Join-Path $scriptDir "Dota2voice2text.iss") (Join-Path $installerDir "Dota2voice2text.iss") -Force

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)

$iscc = $isccCandidates |
    Where-Object { Test-Path $_ } |
    Select-Object -First 1

if (-not $iscc) {
    Write-Host "Inno Setup 6 не найден. Устанавливаю через winget..." -ForegroundColor Yellow

    winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements

    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось установить Inno Setup 6."
    }

    $iscc = $isccCandidates |
        Where-Object { Test-Path $_ } |
        Select-Object -First 1
}

if (-not $iscc) {
    throw "ISCC.exe не найден после установки Inno Setup."
}

Push-Location $installerDir

try {
    Remove-Item ".\output" -Recurse -Force -ErrorAction SilentlyContinue

    & $iscc ".\Dota2voice2text.iss"

    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup завершился с ошибкой."
    }

    $setup = Join-Path $installerDir "output\Dota2voice2text-v0.2.0-Setup.exe"

    if (-not (Test-Path $setup)) {
        throw "Setup.exe не создан."
    }

    $hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
    $size = (Get-Item $setup).Length

    Write-Host ""
    Write-Host "УСТАНОВЩИК ГОТОВ." -ForegroundColor Green
    Write-Host $setup
    Write-Host ("Размер: {0:N1} МБ" -f ($size / 1MB)) -ForegroundColor Cyan
    Write-Host "SHA256: $hash"
}
finally {
    Pop-Location
}
