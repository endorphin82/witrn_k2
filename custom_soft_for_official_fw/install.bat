@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   WITRN K2 - Dependency Installer for Windows
echo ============================================================
echo.

set "NO_PAUSE="
if "%~1"=="--no-pause" set "NO_PAUSE=1"

rem 1. Check for compatible Python version (3.10 - 3.13 recommended)
set "PY_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.12 3.11 3.10 3.13 3) do (
        if "!PY_CMD!"=="" (
            py -%%V --version >nul 2>&1
            if not errorlevel 1 set "PY_CMD=py -%%V"
        )
    )
)

if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python --version >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo [ERROR] Python not found in PATH!
    echo.
    echo Please install Python 3.10, 3.11 or 3.12 from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check 'Add python.exe to PATH' during installation.
    echo.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo [1/4] Found Python interpreter: %PY_CMD%
%PY_CMD% --version
echo.

rem 2. Create virtual environment .venv
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Creating virtual environment .venv...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        if not defined NO_PAUSE pause
        exit /b 1
    )
    echo       Virtual environment successfully created.
) else (
    echo [2/4] Virtual environment .venv already exists.
)
echo.

rem 3. Upgrade pip and install dependencies
echo [3/4] Installing dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARNING] Failed to upgrade pip, proceeding with package installation...
)

.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies!
    echo Please check internet connection or Python version compatibility: 3.10 to 3.13.
    if not defined NO_PAUSE pause
    exit /b 1
)
echo.

rem 4. Verify installation
echo [4/4] Verifying installed packages...
.venv\Scripts\python.exe -c "import PyQt6, pyqtgraph, hid, fastapi, uvicorn, websockets, rich; print('[OK] All core modules successfully verified!')"
if errorlevel 1 (
    echo [ERROR] Verification failed. Some modules could not be imported.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo.
echo ============================================================
echo   Installation completed successfully!
echo ============================================================
echo.
echo You can now launch the application using:
echo   - run_gui.bat   - Native PyQt6 Desktop GUI
echo   - run.bat       - Web Dashboard on http://127.0.0.1:8000
echo   - menu.bat      - Interactive Main Menu
echo.

if not defined NO_PAUSE pause
