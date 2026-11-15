@echo off
chcp 65001 >nul
title WITRN K2 GUI Analyzer
setlocal enabledelayedexpansion

echo ======================================================
echo  WITRN K2 - Нативний GUI інтерфейс (PyQt6)
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
    echo Будь ласка, встановіть Python 3.10+ з https://www.python.org/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Створення віртуального середовища...
    %PYTHON_EXE% -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\pip.exe install -r requirements.txt
)

echo 🚀 Запуск графічного інтерфейсу WITRN K2...
.venv\Scripts\python.exe -m witrn_k2.cli gui %*
if !ERRORLEVEL! NEQ 0 (
    pause
)
