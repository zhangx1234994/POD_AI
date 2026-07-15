@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo AI Chuangpin online update
echo ========================================
echo.
echo Please edit deploy_aichuangpin_generic.ps1 before running:
echo   - SERVER_HOST / SERVER_PORT / SERVER_USER
echo   - SERVER_PASSWORD, if using password login
echo   - COMMITS or COMMIT_IDS, for example @("9c32458") or "9c32458"
echo.
echo Starting deployment...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_aichuangpin_generic.ps1"
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo Deployment finished successfully.
) else (
  echo Deployment failed with exit code %EXIT_CODE%.
)
echo.
pause
exit /b %EXIT_CODE%
