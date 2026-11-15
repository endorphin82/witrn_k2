@echo off
chcp 65001 >nul
title WITRN K2 100Hz Fast Recording
setlocal enabledelayedexpansion

echo ======================================================
echo  ⚡ WITRN K2 - Швидкісний запис (100 Гц)
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

if not exist "recordings" mkdir recordings

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "dt=%%I"
set "TIMESTAMP=%dt:~0,8%_%dt:~8,6%"
if "%TIMESTAMP%"=="_" (
    set "TIMESTAMP=%RANDOM%"
)
set "OUT_FILE=recordings\highspeed_100hz_%TIMESTAMP%.sqlite"

echo Параметри:
echo  - Вихідний файл:  %OUT_FILE%
echo  - Частота:        100 Гц
echo  - Зупинити запис: натисніть Ctrl+C
echo.

.venv\Scripts\python.exe -m witrn_k2.cli record -o "%OUT_FILE%" -r 100 --format sqlite %*
echo.
pause
