@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Python virtual environment not found. Running installer...
    call "%~dp0install.bat" --no-pause
    if errorlevel 1 (
        echo [ERROR] Installation failed.
        pause
        exit /b 1
    )
)

if not exist "recordings" mkdir recordings

echo Running Charge Recording with Auto-Stop (<50mA) (Ctrl+C to stop)...
.venv\Scripts\python.exe -c "import witrn_k2.cli, argparse, datetime, pathlib; ts = datetime.datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'); f = f'recordings/charge_test_{ts}.sqlite'; witrn_k2.cli.cmd_record(argparse.Namespace(out=f, duration=None, rate=10, format='witrn_csv', auto_stop=True, auto_kind='current', threshold=0.05, trigger_duration=10.0, simulator=False))" %*
if errorlevel 1 pause
