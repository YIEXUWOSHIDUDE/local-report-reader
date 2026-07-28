@echo off
setlocal
set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "backend" --host 0.0.0.0 --port 8787
pause
