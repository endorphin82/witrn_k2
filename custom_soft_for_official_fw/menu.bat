@echo off
chcp 65001 >nul
title WITRN K2 All-in-One Launcher
setlocal enabledelayedexpansion

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

set "PY=.venv\Scripts\python.exe"

:menu_loop
cls
echo ==========================================================
echo ⚡ WITRN K2 USB Tester — Меню швидкого вибору
echo ==========================================================
echo  1) 🌐 Веб-інтерфейс (Web Dashboard, 127.0.0.1:8000)
echo  2) 🖥️  Графічний додаток (PyQt6 Desktop GUI)
echo  3) 📊 Термінальний дашборд (Rich TUI)
echo  4) 🎮 Термінальний дашборд у режимі СИМУЛЯТОРА
echo  5) ⚡ Компактний однорядковий монітор (Live)
echo  6) 🔋 Запис заряджання акумулятора (Автозупинка менше 50мА)
echo  7) 🚀 Швидкісний запис (100 Гц)
echo  8) 🔍 Діагностика підключення тестера (info)
echo  9) 📈 Аналіз останнього збереженого запису
echo  0) ❌ Вихід
echo ==========================================================
set /p "choice=Оберіть дію [0-9]: "

if "%choice%"=="1" (
    start "" http://127.0.0.1:8000
    %PY% -m witrn_k2.cli serve --host 127.0.0.1 --port 8000
    goto :menu_loop
)
if "%choice%"=="2" (
    %PY% -m witrn_k2.cli gui
    goto :menu_loop
)
if "%choice%"=="3" (
    %PY% -m witrn_k2.cli dash
    goto :menu_loop
)
if "%choice%"=="4" (
    %PY% -m witrn_k2.cli dash --simulator
    goto :menu_loop
)
if "%choice%"=="5" (
    %PY% -m witrn_k2.cli live
    goto :menu_loop
)
if "%choice%"=="6" (
    call record_charge.bat
    goto :menu_loop
)
if "%choice%"=="7" (
    call record_100hz.bat
    goto :menu_loop
)
if "%choice%"=="8" (
    echo.
    %PY% -m witrn_k2.cli info
    echo.
    pause
    goto :menu_loop
)
if "%choice%"=="9" (
    for /f "delims=" %%F in ('dir /b /o-d recordings\*.sqlite 2^>nul') do (
        set "LAST_FILE=recordings\%%F"
        goto :analyze_file
    )
    echo У папці recordings ще немає збережених сесій.
    pause
    goto :menu_loop

    :analyze_file
    echo Аналіз файлу: !LAST_FILE!
    %PY% -m witrn_k2.cli analyze "!LAST_FILE!"
    pause
    goto :menu_loop
)
if "%choice%"=="0" exit /b 0

echo Невірний вибір. Спробуйте ще раз.
timeout /t 1 >nul
goto :menu_loop
