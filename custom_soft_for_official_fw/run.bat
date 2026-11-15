@echo off
chcp 65001 >nul
title WITRN K2 Web Analyzer
setlocal enabledelayedexpansion

echo ======================================================
echo  WITRN K2 - Лабораторне ПЗ для аналізу даних
echo ======================================================
echo.

:: Detect Python
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
    echo [ПОМИЛКА] Python не знайдено в системній змінній PATH.
    echo Будь ласка, встановіть Python 3.10+ з https://www.python.org/
    echo Обов'язково відмітьте галочку "Add Python to PATH" під час встановлення.
    echo.
    pause
    exit /b 1
)

:: Virtual environment management
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Створення віртуального середовища Python (.venv)...
    %PYTHON_EXE% -m venv .venv
    if !ERRORLEVEL! NEQ 0 (
        echo [ПОМИЛКА] Не вдалося створити .venv.
        pause
        exit /b 1
    )
    echo [2/3] Встановлення залежностей (це може зайняти хвилину)...
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\pip.exe install -r requirements.txt
    if !ERRORLEVEL! NEQ 0 (
        echo [ПОМИЛКА] Помилка встановлення бібліотек із requirements.txt.
        pause
        exit /b 1
    )
)

:: Device check
echo [3/3] Перевірка підключення USB-тестера WITRN K2...
.venv\Scripts\python.exe -m witrn_k2.cli info
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ⚠️ Попередження: Пристрій не знайдено або зайнятий іншою програмою.
    echo    Ви зможете працювати в режимі симулятора у веб-панелі.
    echo.
)

echo.
echo 🚀 Запуск веб-сервера на http://127.0.0.1:8000 ...
echo    (Для завершення роботи натисніть Ctrl+C у цьому вікні)
echo.

.venv\Scripts\python.exe -m witrn_k2.cli serve --host 127.0.0.1 --port 8000 --open-browser %*
pause
