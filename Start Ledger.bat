@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer is required.
    pause
    exit /b 1
)

python -c "from cryptography.fernet import Fernet" >nul 2>nul
if errorlevel 1 (
    python -m pip install -r server\requirements.txt
    if errorlevel 1 exit /b 1
)

if not exist "frontend\dist\index.html" (
    where npm.cmd >nul 2>nul
    if errorlevel 1 (
        echo Install Node.js 22.12 or newer to build the React viewer.
        pause
        exit /b 1
    )
    if not exist "frontend\node_modules" (
        call npm.cmd --prefix frontend ci
        if errorlevel 1 exit /b 1
    )
    call npm.cmd --prefix frontend run build
    if errorlevel 1 exit /b 1
)

echo Open the address printed by the server, normally http://127.0.0.1:8000.
python server\app.py %*
pause
