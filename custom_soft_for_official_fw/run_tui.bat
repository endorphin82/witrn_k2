@echo off
chcp 65001 >nul
title WITRN K2 Terminal Dashboard
setlocal enabledelayedexpansion

echo ======================================================
echo  WITRN K2 - Термінальний дашборд (TUI)
echo ======================================================
echo.

set "PYTHON_EXE="
where py >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON_EXE=py"
) else (
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_EXE=python"
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ПОМИЛКА] Python не знайдено в PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Створення віртуального середовища...
    %PYTHON_EXE% -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\pip.exe install -r requirements.txt
)

echo 📊 Запуск термінального дашборду...
.venv\Scripts\python.exe -m witrn_k2.cli dash %*
if !ERRORLEVEL! NEQ 0 (
    pause
)
