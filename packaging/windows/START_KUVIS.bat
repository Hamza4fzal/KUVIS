@echo off
title KUVIS
cd /d "%~dp0"
if not exist "runtime\python\python.exe" (
  echo The runtime folder is missing. Extract the whole zip file first, then run START_KUVIS.bat from the extracted folder.
  pause
  exit /b 1
)
"runtime\python\python.exe" -I "kuvis_launcher.py"
if errorlevel 1 pause
