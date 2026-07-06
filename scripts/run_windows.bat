@echo off
chcp 65001 >nul
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo 已创建 .env 配置文件。
  echo 请先用记事本打开 .env，填写 OPENAI_API_KEY 后再重新运行本脚本。
  echo.
  pause
  exit /b 1
)

where python >nul 2>nul
if %errorlevel% equ 0 (
  set "PYTHON_CMD=python"
) else (
  where py >nul 2>nul
  if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
  ) else (
    echo 未检测到 Python。请先安装 Python 3.11 或更高版本，并勾选 Add python.exe to PATH。
    pause
    exit /b 1
  )
)

where npm >nul 2>nul
if not %errorlevel% equ 0 (
  echo 未检测到 Node.js/npm。请先安装 Node.js LTS 版本。
  pause
  exit /b 1
)

if not exist "data" mkdir "data"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\output" mkdir "data\output"
if not exist "data\exports" mkdir "data\exports"

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建 Python 虚拟环境...
  %PYTHON_CMD% -m venv ".venv"
  if not %errorlevel% equ 0 (
    echo Python 虚拟环境创建失败。
    pause
    exit /b 1
  )
)

echo 正在安装 Python 依赖...
".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if not %errorlevel% equ 0 (
  echo Python 依赖安装失败，请检查网络或 Python 环境。
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo 正在安装前端依赖...
  pushd "frontend"
  npm install
  if not %errorlevel% equ 0 (
    popd
    echo 前端依赖安装失败，请检查网络或 Node.js 环境。
    pause
    exit /b 1
  )
  popd
)

echo.
echo 正在启动本地服务...
echo 浏览器地址：http://127.0.0.1:5173/
echo 手机访问：手机和电脑连接同一个 Wi-Fi 后，扫描页面上的二维码。
echo.

start "可研报告精读工具-后端" cmd /k """%ROOT_DIR%\.venv\Scripts\python.exe"" -m uvicorn app.main:app --app-dir ""%ROOT_DIR%\backend"" --host 0.0.0.0 --port 8787"
start "可研报告精读工具-前端" cmd /k "npm --prefix ""%ROOT_DIR%\frontend"" run dev"

timeout /t 3 >nul
start "" "http://127.0.0.1:5173/"

echo 已启动。请不要关闭弹出的后端和前端窗口。
pause
