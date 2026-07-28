@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from .env.example.
  echo Open .env with Notepad, fill OPENAI_API_KEY, then run this file again.
  pause
  exit /b 1
)

if exist "LocalReportReader.exe" (
  echo Starting LocalReportReader.exe...
  start "Local Report Reader" "%ROOT_DIR%\LocalReportReader.exe"
  echo Started. The browser should open automatically.
  pause
  exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python was not found.
    echo Install Python 3.11 or newer and enable "Add python.exe to PATH".
    pause
    exit /b 1
  )
  set "PYTHON_CMD=py"
) else (
  set "PYTHON_CMD=python"
)

set "FRONTEND_BUILT=0"
if exist "frontend\dist\index.html" set "FRONTEND_BUILT=1"

if "%FRONTEND_BUILT%"=="0" (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo Node.js/npm was not found.
    echo This package does not contain frontend\dist.
    echo Install Node.js LTS, or ask for the customer package with built frontend files.
    pause
    exit /b 1
  )
)

if not exist "data" mkdir "data"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\output" mkdir "data\output"
if not exist "data\exports" mkdir "data\exports"

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  %PYTHON_CMD% -m venv ".venv"
  if errorlevel 1 (
    echo Failed to create Python virtual environment.
    pause
    exit /b 1
  )
)

echo Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 (
  echo Failed to install Python dependencies.
  echo Check network and Python installation.
  pause
  exit /b 1
)

if "%FRONTEND_BUILT%"=="0" if not exist "frontend\node_modules" (
  echo Installing frontend dependencies...
  pushd "frontend"
  npm install
  if errorlevel 1 (
    popd
    echo Failed to install frontend dependencies.
    echo Check network and Node.js installation.
    pause
    exit /b 1
  )
  popd
)

echo.
echo Starting local services...
if "%FRONTEND_BUILT%"=="1" (
  echo Browser URL: http://127.0.0.1:8787/
  echo Built frontend found. Node.js is not required for this customer package.
) else (
  echo Browser URL: http://127.0.0.1:5173/
  echo Built frontend not found. Starting Vite dev server with Node.js.
)
echo.

start "Local Report Reader Backend" "%ComSpec%" /k call "%ROOT_DIR%\scripts\start_backend.bat"
if "%FRONTEND_BUILT%"=="0" start "Local Report Reader Frontend" "%ComSpec%" /k call "%ROOT_DIR%\scripts\start_frontend.bat"

timeout /t 3 >nul
if "%FRONTEND_BUILT%"=="1" (
  start "" "http://127.0.0.1:8787/"
) else (
  start "" "http://127.0.0.1:5173/"
)

if "%FRONTEND_BUILT%"=="1" (
  echo Started. Do not close the backend command window.
) else (
  echo Started. Do not close the backend and frontend command windows.
)
pause
