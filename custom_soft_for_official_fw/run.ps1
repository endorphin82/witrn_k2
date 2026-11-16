# WITRN K2 Web Server Launcher
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[INFO] Віртуальне середовище не знайдено. Запуск інсталятора..." -ForegroundColor Cyan
    & "$PSScriptRoot\install.ps1" -NoPause
}

Write-Host "🚀 Запуск веб-сервера WITRN K2 на http://127.0.0.1:8000 ..." -ForegroundColor Green
& .venv\Scripts\python.exe -m witrn_k2.cli serve --host 127.0.0.1 --port 8000 --open-browser $args
