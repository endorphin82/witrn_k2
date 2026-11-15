# WITRN K2 Interactive Menu
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) {
    $python = (Get-Command python -ErrorAction SilentlyContinue)
}

if (-not $python) {
    Write-Host "[ПОМИЛКА] Python не знайдено в PATH." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Створення віртуального середовища..." -ForegroundColor Cyan
    & $python.Source -m venv .venv
    & .venv\Scripts\python.exe -m pip install --upgrade pip
    & .venv\Scripts\pip.exe install -r requirements.txt
}

& .venv\Scripts\python.exe -m witrn_k2.cli menu $args
