@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Install Python 3.11+ and Node.js 22.12+ first. PostgreSQL must also be available locally.
    pause
    exit /b 1
)
python tools\start_ledger.py %*
set "LEDGER_EXIT=%ERRORLEVEL%"
if not "%LEDGER_EXIT%"=="0" pause
exit /b %LEDGER_EXIT%
