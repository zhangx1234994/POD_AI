param(
  [string]$PythonExe = "python",
  [string]$CenterUrl = "http://117.50.80.158:8099",
  [string]$InstallKey = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $Root "build\windows"
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Write-Host "==> Build server exe"
& $PythonExe -m pip install pyinstaller
& $PythonExe -m PyInstaller --clean --noconfirm --onefile --name podi-agent-server "$Root\agent_server\main.py"

Write-Host "==> Build gui exe"
& $PythonExe -m PyInstaller --clean --noconfirm --windowed --onefile --name podi-agent-gui "$Root\app_gui\main.py"

Write-Host "==> Prepare installer payload"
Copy-Item "$Root\dist\podi-agent-server.exe" "$BuildDir\podi-agent-server.exe" -Force
Copy-Item "$Root\dist\podi-agent-gui.exe" "$BuildDir\podi-agent-gui.exe" -Force
Copy-Item "$PSScriptRoot\install_windows.ps1" "$BuildDir\install_windows.ps1" -Force
Copy-Item "$PSScriptRoot\uninstall_windows.ps1" "$BuildDir\uninstall_windows.ps1" -Force
Copy-Item "$PSScriptRoot\podi-agent.iss" "$BuildDir\podi-agent.iss" -Force

Write-Host "==> Optional: build setup.exe with Inno Setup (if ISCC exists)"
$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($iscc) {
  & $iscc.Source "/DCenterUrl=$CenterUrl" "/DInstallKey=$InstallKey" "$BuildDir\podi-agent.iss"
  Write-Host "Setup built under $BuildDir\Output"
} else {
  Write-Host "ISCC.exe not found. Install Inno Setup then run:"
  Write-Host "  ISCC.exe /DCenterUrl=$CenterUrl /DInstallKey=$InstallKey $BuildDir\podi-agent.iss"
}
