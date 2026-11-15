@echo off
chcp 65001 >nul
title WITRN K2 Live Monitor
setlocal enabledelayedexpansion

echo ======================================================
echo  WITRN K2 - Однорядковий живий монітор
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

echo ⚡ Запуск живого моніторингу (натисніть Ctrl+C для зупинки)...
.venv\Scripts\python.exe -m witrn_k2.cli live %*
if !ERRORLEVEL! NEQ 0 (
    pause
)
