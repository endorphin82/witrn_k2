@echo off
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && set "PY=py"
if "%PY%"=="" where python >nul 2>&1 && set "PY=python"

if "%PY%"=="" (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY% -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\pip.exe install -r requirements.txt
)

if not exist "recordings" mkdir recordings

echo Running Battery Charge Test with Auto-Stop (<50mA for 10s)...
.venv\Scripts\python.exe -c "import witrn_k2.cli, argparse, datetime, pathlib; ts = datetime.datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'); f = f'recordings/charge_{ts}.sqlite'; witrn_k2.cli.cmd_record(argparse.Namespace(out=f, duration=None, rate=10, format='witrn_csv', auto_stop=True, auto_kind='current', threshold=0.05, trigger_duration=10.0, simulator=False))" %*
if errorlevel 1 pause
