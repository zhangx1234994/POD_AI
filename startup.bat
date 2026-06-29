@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "IMAGE_OPS_DIR=%ROOT%image-ops-service"
set "VENDOR_API_DIR=%ROOT%vendor-api-ops"
set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "BACKEND_PORT=8310"
set "IMAGE_OPS_PORT=8301"
set "VENDOR_API_PORT=8311"
set "COMFY_3090_BASE_URL=http://192.168.2.114:8079"
set "LOCAL_EXECUTOR_CONFIG=%ROOT%.tmp-local\executors.local-startup.yaml"

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

if not exist "%VENDOR_API_DIR%\app\main.py" (
  echo [ERROR] Vendor API ops app not found: %VENDOR_API_DIR%\app\main.py
  pause
  exit /b 1
)

call :prepare_local_executor_config
if errorlevel 1 (
  pause
  exit /b 1
)

call :stop_port %VENDOR_API_PORT%
call :stop_port %BACKEND_PORT%
call :stop_port %IMAGE_OPS_PORT%

echo [POD_AI] Launch vendor-api-ops on http://127.0.0.1:%VENDOR_API_PORT%
start "POD_AI vendor-api-ops %VENDOR_API_PORT%" /D "%VENDOR_API_DIR%" "%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port %VENDOR_API_PORT%

rem 本地完整闭环需要 backend 走本机 vendor-api-ops；只在本脚本进程注入，不修改 backend/.env 或线上配置。
set "VENDOR_API_ENABLED=true"
set "VENDOR_API_BASE_URL=http://127.0.0.1:%VENDOR_API_PORT%"
set "EXECUTOR_CONFIG_PATH=%LOCAL_EXECUTOR_CONFIG%"

echo [POD_AI] Launch backend on http://0.0.0.0:%BACKEND_PORT%
start "POD_AI backend %BACKEND_PORT%" /D "%BACKEND_DIR%" "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT%

echo [POD_AI] Launch image-ops on http://127.0.0.1:%IMAGE_OPS_PORT%
start "POD_AI image-ops %IMAGE_OPS_PORT%" /D "%IMAGE_OPS_DIR%" "%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port %IMAGE_OPS_PORT%

echo.
echo [POD_AI] Started. Health checks:
echo   backend:   http://127.0.0.1:%BACKEND_PORT%/health
echo   backend LAN: http://^<this-machine-ip^>:%BACKEND_PORT%/health
echo   image-ops: http://127.0.0.1:%IMAGE_OPS_PORT%/health
echo   vendor-api-ops: http://127.0.0.1:%VENDOR_API_PORT%/health
echo   vendor providers: http://127.0.0.1:%VENDOR_API_PORT%/v1/providers
echo.
exit /b 0

:prepare_local_executor_config
echo [POD_AI] Prepare local executor config for vendor-api-ops and 3090 ComfyUI...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $root='%ROOT%'; $src=Join-Path $root 'config\executors.yaml'; $dst='%LOCAL_EXECUTOR_CONFIG%'; $dir=Split-Path -Parent $dst; New-Item -ItemType Directory -Force -Path $dir | Out-Null; $content=Get-Content -Raw -Encoding UTF8 $src; $content=$content -replace '\$\{VENDOR_API_BASE_URL:-http://117\.50\.80\.158:8310\}', 'http://127.0.0.1:%VENDOR_API_PORT%'; $content=$content -replace 'http://117\.50\.80\.158:8079', '%COMFY_3090_BASE_URL%'; $content=$content -replace '(?s)(id: executor_comfyui_seamless_117.*?status: )active', '${1}inactive'; Set-Content -Encoding UTF8 -Path $dst -Value $content"
if errorlevel 1 (
  echo [ERROR] Failed to prepare local executor config: %LOCAL_EXECUTOR_CONFIG%
  exit /b 1
)
exit /b 0

:stop_port
set "PORT=%~1"
echo [POD_AI] Stop existing listener on port %PORT% if any...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-NetTCPConnection -LocalPort %PORT% -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }"
exit /b 0
