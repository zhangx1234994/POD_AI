@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "IMAGE_OPS_DIR=%ROOT%image-ops-service"
set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"

echo [POD_AI] Starting local services...
echo [POD_AI] Root: %ROOT%
echo.

if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python venv not found: %PYTHON_EXE%
  echo [ERROR] Please initialize backend venv first.
  pause
  exit /b 1
)

if not exist "%BACKEND_DIR%\app\main.py" (
  echo [ERROR] Backend app not found: %BACKEND_DIR%\app\main.py
  pause
  exit /b 1
)

if not exist "%IMAGE_OPS_DIR%\app\main.py" (
  echo [ERROR] Image ops app not found: %IMAGE_OPS_DIR%\app\main.py
  pause
  exit /b 1
)

call :stop_port 8310
call :stop_port 8301

echo [POD_AI] Launch backend on http://0.0.0.0:8310
start "POD_AI backend 8310" /D "%BACKEND_DIR%" "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8310

echo [POD_AI] Launch image-ops on http://127.0.0.1:8301
start "POD_AI image-ops 8301" /D "%IMAGE_OPS_DIR%" "%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8301

echo.
echo [POD_AI] Started. Health checks:
echo   backend:   http://127.0.0.1:8310/health
echo   backend LAN: http://^<this-machine-ip^>:8310/health
echo   image-ops: http://127.0.0.1:8301/health
echo.
exit /b 0

:stop_port
set "PORT=%~1"
echo [POD_AI] Stop existing listener on port %PORT% if any...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-NetTCPConnection -LocalPort %PORT% -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }"
exit /b 0
