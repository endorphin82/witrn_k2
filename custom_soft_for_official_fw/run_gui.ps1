# WITRN K2 GUI Launcher
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[INFO] Віртуальне середовище не знайдено. Запуск інсталятора..." -ForegroundColor Cyan
    & "$PSScriptRoot\install.ps1" -NoPause
}

Write-Host "🚀 Запуск графічного інтерфейсу PyQt6..." -ForegroundColor Green
& .venv\Scripts\python.exe -m witrn_k2.cli gui $args
