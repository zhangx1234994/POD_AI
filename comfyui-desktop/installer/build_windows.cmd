@echo off
setlocal
set SCRIPT_DIR=%~dp0
chcp 65001 >nul

echo [PODI] 一键打包桌面端安装包
echo.
pushd "%SCRIPT_DIR%"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows.ps1" %*
set ERR=%ERRORLEVEL%
popd
if not "%ERR%"=="0" (
  echo.
  echo 打包失败，请检查上方日志。
  pause
  exit /b %ERR%
)
echo.
echo 打包成功。
pause
