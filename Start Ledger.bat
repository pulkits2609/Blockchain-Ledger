@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer is required.
    pause
    exit /b 1
)

if not exist ".env" (
    echo Copy .env.example to .env and configure your local PostgreSQL connection first.
    echo See README.md for first-time admin setup and HTTPS certificate settings.
    pause
    exit /b 2
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r server\requirements.txt
if errorlevel 1 exit /b 1

if not exist "frontend\dist\index.html" (
    where npm.cmd >nul 2>nul
    if errorlevel 1 (
        echo Install Node.js 22.12 or newer to build the React viewer.
        pause
        exit /b 1
    )
    call npm.cmd --prefix frontend ci
    if errorlevel 1 exit /b 1
    call npm.cmd --prefix frontend run build
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" server\app.py --env-file .env --check-db
if errorlevel 1 exit /b 1
echo Open the public address printed by the server.
".venv\Scripts\python.exe" server\app.py --env-file .env %*
set "LEDGER_EXIT=%ERRORLEVEL%"
pause
exit /b %LEDGER_EXIT%
