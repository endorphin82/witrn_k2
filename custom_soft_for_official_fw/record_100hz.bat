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

echo Running High-Speed 100 Hz Recording (Ctrl+C to stop)...
.venv\Scripts\python.exe -c "import witrn_k2.cli, argparse, datetime, pathlib; ts = datetime.datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'); f = f'recordings/highspeed_100hz_{ts}.sqlite'; witrn_k2.cli.cmd_record(argparse.Namespace(out=f, duration=None, rate=100, format='sqlite', auto_stop=False, auto_kind='current', threshold=0.05, trigger_duration=10.0, simulator=False))" %*
if errorlevel 1 pause
