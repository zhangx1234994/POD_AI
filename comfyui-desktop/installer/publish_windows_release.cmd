@echo off
setlocal
set SCRIPT_DIR=%~dp0

echo [PODI] 一键打包并发布桌面端安装包
echo.
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%publish_windows_release.ps1" %*
if errorlevel 1 (
  echo.
  echo 发布失败，请检查上方日志。
  pause
  exit /b 1
)
echo.
echo 发布成功。
pause
