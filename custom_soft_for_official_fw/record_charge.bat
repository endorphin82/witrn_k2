@echo off
chcp 65001 >nul
title WITRN K2 Battery Charge Recording
setlocal enabledelayedexpansion

echo ======================================================
echo  🔋 WITRN K2 - Тест заряджання з автозупинкою
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

:: Generate timestamp YYYYMMDD_HHMMSS
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "dt=%%I"
set "TIMESTAMP=%dt:~0,8%_%dt:~8,6%"
if "%TIMESTAMP%"=="_" (
    set "TIMESTAMP=%RANDOM%"
)
set "OUT_FILE=recordings\charge_%TIMESTAMP%.sqlite"

echo Параметри тесту:
echo  - Вихідний файл:  %OUT_FILE%
echo  - Поріг зупинки:  струм менше 0.05 A (50 мА) протягом 10 с
echo  - Частота:        10 Гц
echo  - Автоекспорт:    офіційний WITRN CSV
echo.

.venv\Scripts\python.exe -m witrn_k2.cli record -o "%OUT_FILE%" -r 10 --format witrn_csv --auto-stop --auto-kind current --threshold 0.05 --trigger-duration 10.0 %*
echo.
pause
