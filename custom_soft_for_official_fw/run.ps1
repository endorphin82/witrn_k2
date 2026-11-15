# WITRN K2 Web Server Launcher
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) {
    $python = (Get-Command python -ErrorAction SilentlyContinue)
}

if (-not $python) {
    Write-Host "[ПОМИЛКА] Python не знайдено в PATH." -ForegroundColor Red
    Write-Host "Встановіть Python 3.10+ з https://www.python.org/ (позначте 'Add Python to PATH')"
    Read-Host "Натисніть Enter для виходу"
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/2] Створення віртуального середовища (.venv)..." -ForegroundColor Cyan
    & $python.Source -m venv .venv
    Write-Host "[2/2] Встановлення залежностей..." -ForegroundColor Cyan
    & .venv\Scripts\python.exe -m pip install --upgrade pip
    & .venv\Scripts\pip.exe install -r requirements.txt
}

Write-Host "🚀 Запуск веб-сервера WITRN K2 на http://127.0.0.1:8000 ..." -ForegroundColor Green
& .venv\Scripts\python.exe -m witrn_k2.cli serve --host 127.0.0.1 --port 8000 --open-browser $args
