@echo off
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && set "PY=py"
if "%PY%"=="" where python >nul 2>&1 && set "PY=python"

if "%PY%"=="" (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\pip.exe install -r requirements.txt
)

echo Starting WITRN K2 Terminal Dashboard (TUI)...
.venv\Scripts\python.exe -m witrn_k2.cli dash %*
if errorlevel 1 pause
