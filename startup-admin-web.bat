@echo off
setlocal

set "ROOT=%~dp0"
set "ADMIN_DIR=%ROOT%podi-admin-web"
set "API_BASE=http://127.0.0.1:8310"
set "PORT=8199"

echo [POD_AI] Starting admin web...
echo [POD_AI] Admin dir: %ADMIN_DIR%
echo [POD_AI] API base: %API_BASE%
echo.

if not exist "%ADMIN_DIR%\package.json" (
  echo [ERROR] Admin web package not found: %ADMIN_DIR%\package.json
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm is not available. Please install Node.js first.
  pause
  exit /b 1
)

if not exist "%ADMIN_DIR%\node_modules" (
  echo [POD_AI] node_modules not found. Running npm install...
  pushd "%ADMIN_DIR%"
  call npm install
  if errorlevel 1 (
    popd
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
  popd
)

call :stop_port %PORT%

echo [POD_AI] Launch admin web on http://127.0.0.1:%PORT%
echo [POD_AI] Open: http://127.0.0.1:%PORT%/#nav=ability-logs
echo.

pushd "%ADMIN_DIR%"
set "VITE_API_BASE_URL=%API_BASE%"
call npm run dev -- --host 0.0.0.0 --port %PORT% --strictPort
set "EXIT_CODE=%ERRORLEVEL%"
popd

echo.
echo [POD_AI] Admin web exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

:stop_port
set "TARGET_PORT=%~1"
echo [POD_AI] Stop existing listener on port %TARGET_PORT% if any...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-NetTCPConnection -LocalPort %TARGET_PORT% -State Listen | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }"
exit /b 0
