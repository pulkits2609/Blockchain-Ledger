@echo off
setlocal
cd /d "%~dp0"
echo Demo seeding uses the configured PostgreSQL database and requires the admin setup.
call "Start Ledger.bat" --seed-demo %*
exit /b %ERRORLEVEL%
