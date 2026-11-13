@echo off
cd /d "%~dp0"
if exist "data\pgdata\postmaster.pid" "runtime\pgsql\bin\pg_ctl.exe" stop -D "data\pgdata" -m fast
echo KUVIS stopped.
timeout /t 3 >nul
