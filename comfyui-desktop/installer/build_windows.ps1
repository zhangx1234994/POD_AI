param(
  [string]$PythonExe = "python",
  [string]$CenterUrl = "http://117.50.80.158:8099",
  [string]$InstallKey = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $Root "build\windows"
$DistDir = Join-Path $Root "dist"
$PyInstallerWorkDir = Join-Path $Root "build\pyinstaller"
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path $PyInstallerWorkDir | Out-Null

function Invoke-External {
  param(
    [string]$FilePath,
    [string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "外部命令执行失败: $FilePath $($Arguments -join ' ')"
  }
}

function Resolve-IsccPath {
  $cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }
  $candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      return $candidate
    }
  }
  return $null
}

Write-Host "==> 校验 Python 环境"
Invoke-External -FilePath $PythonExe -Arguments @("--version")

Push-Location $Root
try {
  Write-Host "==> 安装桌面端依赖（含 PySide6）"
  Invoke-External -FilePath $PythonExe -Arguments @("-m", "pip", "install", "-e", $Root)

  Write-Host "==> 安装/更新 PyInstaller"
  Invoke-External -FilePath $PythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pyinstaller")

  Write-Host "==> Build server exe"
  Invoke-External -FilePath $PythonExe -Arguments @(
    "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--onefile",
    "--name", "podi-agent-server",
    "--distpath", $DistDir,
    "--workpath", (Join-Path $PyInstallerWorkDir "server"),
    "--specpath", $PyInstallerWorkDir,
    (Join-Path $Root "agent_server\main.py")
  )

  Write-Host "==> Build gui exe"
  Invoke-External -FilePath $PythonExe -Arguments @(
    "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--windowed",
    "--onefile",
    "--name", "podi-agent-gui",
    "--collect-all", "PySide6",
    "--collect-all", "shiboken6",
    "--hidden-import", "PySide6.QtCore",
    "--hidden-import", "PySide6.QtGui",
    "--hidden-import", "PySide6.QtWidgets",
    "--distpath", $DistDir,
    "--workpath", (Join-Path $PyInstallerWorkDir "gui"),
    "--specpath", $PyInstallerWorkDir,
    (Join-Path $Root "app_gui\main.py")
  )
} finally {
  Pop-Location
}

if (-not (Test-Path (Join-Path $DistDir "podi-agent-server.exe"))) {
  throw "打包失败：未生成 podi-agent-server.exe"
}
if (-not (Test-Path (Join-Path $DistDir "podi-agent-gui.exe"))) {
  throw "打包失败：未生成 podi-agent-gui.exe"
}

Write-Host "==> Prepare installer payload"
Copy-Item (Join-Path $DistDir "podi-agent-server.exe") "$BuildDir\podi-agent-server.exe" -Force
Copy-Item (Join-Path $DistDir "podi-agent-gui.exe") "$BuildDir\podi-agent-gui.exe" -Force
Copy-Item "$PSScriptRoot\install_windows.ps1" "$BuildDir\install_windows.ps1" -Force
Copy-Item "$PSScriptRoot\uninstall_windows.ps1" "$BuildDir\uninstall_windows.ps1" -Force
Copy-Item "$PSScriptRoot\podi-agent.iss" "$BuildDir\podi-agent.iss" -Force

Write-Host "==> Optional: build setup.exe with Inno Setup (if ISCC exists)"
$iscc = Resolve-IsccPath
if ($iscc) {
  Invoke-External -FilePath $iscc -Arguments @(
    "/DCenterUrl=$CenterUrl",
    "/DInstallKey=$InstallKey",
    "$BuildDir\podi-agent.iss"
  )
  Write-Host "Setup built under $BuildDir\Output"
} else {
  Write-Host "ISCC.exe not found. Install Inno Setup then run:"
  Write-Host "  ISCC.exe /DCenterUrl=$CenterUrl /DInstallKey=$InstallKey $BuildDir\podi-agent.iss"
}
