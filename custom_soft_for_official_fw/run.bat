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

echo Starting WITRN K2 Web Server on http://127.0.0.1:8000 ...
.venv\Scripts\python.exe -m witrn_k2.cli serve --host 127.0.0.1 --port 8000 --open-browser %*
if errorlevel 1 pause
