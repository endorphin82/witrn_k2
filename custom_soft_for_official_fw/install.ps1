# WITRN K2 - Windows PowerShell Dependency Installer
[CmdletBinding()]
param(
    [switch]$NoPause
)

# ВИПРАВЛЕННЯ: Змінено "Stop" на "Continue", щоб попередження від Python не ламали скрипт
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location -Path $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ⚡ Встановлення залежностей WITRN K2 для Windows (PowerShell)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Пошук сумісної версії Python (рекомендовано 3.10 - 3.13)
$pythonCmd = $null
$pythonArgs = @()

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pyLauncher) {
    foreach ($ver in @("3.12", "3.11", "3.10", "3.13", "3")) {
        try {
            $testOutput = & py "-$ver" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>&1
        } catch {}
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = "py"
            $pythonArgs = @("-$ver")
            break
        }
    }
}

if (-not $pythonCmd) {
    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonExe) {
        try {
            $testOutput = & python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>&1
        } catch {}
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = "python"
            $pythonArgs = @()
        }
    }
}

# АВТОМАТИЧНЕ ВСТАНОВЛЕННЯ PYTHON
if (-not $pythonCmd) {
    Write-Host "[ПОПЕРЕДЖЕННЯ] Сумісний Python (версії 3.10+) не знайдено, або він пошкоджений!" -ForegroundColor Yellow
    Write-Host "Починаю автоматичне завантаження та встановлення Python 3.12..." -ForegroundColor Cyan

    $pythonInstallerUrl = "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe"
    $installerPath = Join-Path $env:TEMP "python-3.12.3-amd64.exe"

    Write-Host "Завантаження інсталятора в $installerPath..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $pythonInstallerUrl -OutFile $installerPath

    Write-Host "Встановлення Python (це може зайняти кілька хвилин)..." -ForegroundColor Gray
    # Тихе встановлення лише для поточного користувача, додавання до PATH
    $installArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0"
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "Python успішно встановлено!" -ForegroundColor Green
        
        # Оновлення змінної середовища PATH у поточному вікні
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        $pythonCmd = "python"
        $pythonArgs = @()
    } else {
        Write-Host "[ПОМИЛКА] Помилка під час встановлення Python (Код завершення: $($process.ExitCode))." -ForegroundColor Red
        if (-not $NoPause) { Read-Host "Натисніть Enter для виходу" }
        exit 1
    }
}

Write-Host "[1/4] Знайдено інтерпретатор: $pythonCmd $($pythonArgs -join ' ')" -ForegroundColor Green
& $pythonCmd @pythonArgs -c "import sys; print('      Версія Python:', sys.version.split()[0])"
Write-Host ""

# 2. Створення віртуального середовища
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[2/4] Створення віртуального середовища (.venv)..." -ForegroundColor Cyan
    & $pythonCmd @pythonArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ПОМИЛКА] Не вдалося створити віртуальне середовище!" -ForegroundColor Red
        if (-not $NoPause) { Read-Host "Натисніть Enter для виходу" }
        exit 1
    }
    Write-Host "      Віртуальне середовище успішно створено." -ForegroundColor Green
} else {
    Write-Host "[2/4] Віртуальне середовище .venv вже існує." -ForegroundColor Gray
}
Write-Host ""

# 3. Оновлення pip та встановлення залежностей
Write-Host "[3/4] Оновлення pip та встановлення залежностей з requirements.txt..." -ForegroundColor Cyan
& .venv\Scripts\python.exe -m pip install --upgrade pip 2>&1 | Out-Null
& .venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ПОМИЛКА] Не вдалося встановити всі залежності!" -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Натисніть Enter для виходу" }
    exit 1
}
Write-Host ""

# 4. Перевірка цілісності інсталяції
Write-Host "[4/4] Верифікація встановлених модулів..." -ForegroundColor Cyan
& .venv\Scripts\python.exe -c "import PyQt6, pyqtgraph, hid, fastapi, uvicorn, websockets, rich; print('      ✓ Всі ключові модулі успішно перевірено!')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ПОМИЛКА] Деякі модулі не вдалося імпортувати." -ForegroundColor Red
    if (-not $NoPause) { Read-Host "Натисніть Enter для виходу" }
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  🎉 Інсталяцію успішно завершено!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Тепер ви можете запускати програму:"
Write-Host "  • .\run_gui.ps1   - Десктопний GUI (PyQt6)" -ForegroundColor White
Write-Host "  • .\run.ps1       - Веб-панель (http://127.0.0.1:8000)" -ForegroundColor White
Write-Host "  • .\menu.ps1      - Головне інтерактивне меню" -ForegroundColor White
Write-Host ""

if (-not $NoPause) {
    Read-Host "Натисніть Enter для завершення"
}