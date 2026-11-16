@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Python virtual environment not found. Running installer...
    call "%~dp0install.bat" --no-pause
    if errorlevel 1 (
        echo [ERROR] Installation failed.
        pause
        exit /b 1
    )
)

echo Starting WITRN K2 Terminal Dashboard (TUI)...
.venv\Scripts\python.exe -m witrn_k2.cli dash %*
if errorlevel 1 pause
