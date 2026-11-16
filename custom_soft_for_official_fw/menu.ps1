# WITRN K2 Interactive Menu
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[INFO] Віртуальне середовище не знайдено. Запуск інсталятора..." -ForegroundColor Cyan
    & "$PSScriptRoot\install.ps1" -NoPause
}

& .venv\Scripts\python.exe -m witrn_k2.cli menu $args
