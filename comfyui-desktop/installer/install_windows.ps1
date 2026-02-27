param(
  [string]$InstallRoot = "$env:ProgramData\\PodiComfyuiAgent",
  [string]$PythonExe = "python",
  [string]$CenterUrl = "http://117.50.80.158:8099",
  [string]$InstallKey = "",
  [string]$ComfyuiPath = "C:\\ComfyUI",
  [int]$ComfyuiPort = 8079,
  [int]$AgentPort = 18079,
  [switch]$SkipCopy
)

$ErrorActionPreference = "Stop"

Write-Host "==> Prepare install root: $InstallRoot"
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$RuntimeHome = Join-Path $InstallRoot "runtime"
New-Item -ItemType Directory -Force -Path $RuntimeHome | Out-Null

if (-not $SkipCopy) {
  Write-Host "==> Copy files"
  Copy-Item -Path "$PSScriptRoot\\.." -Destination $InstallRoot -Recurse -Force
}

Write-Host "==> Write runtime config"
$configPath = Join-Path $RuntimeHome "config.json"
$config = @{
  center_url = $CenterUrl
  install_key = $InstallKey
  auto_bootstrap = $true
  agent_id = ""
  agent_token = ""
  jwt_keys = @()
  comfyui_path = $ComfyuiPath
  comfyui_port = $ComfyuiPort
  agent_port = $AgentPort
  heartbeat_interval_sec = 60
  auto_update = $true
  log_level = "INFO"
}
$config | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding UTF8

function Register-Service {
  param(
    [string]$BinPath
  )
  $serviceName = "PodiComfyuiAgent"
  sc.exe stop $serviceName | Out-Null
  sc.exe delete $serviceName | Out-Null
  sc.exe create $serviceName "binPath=$BinPath" start=auto DisplayName="PODI ComfyUI 代理服务" | Out-Null
  sc.exe description $serviceName "PODI ComfyUI desktop agent service" | Out-Null
  sc.exe start $serviceName | Out-Null
}

$ServerExe = Join-Path $InstallRoot "podi-agent-server.exe"
if (Test-Path $ServerExe) {
  Write-Host "==> Register windows service (binary mode)"
  $wrapper = Join-Path $InstallRoot "run_agent_service.cmd"
  @(
    "@echo off"
    "set COMFYUI_DESKTOP_HOME=$RuntimeHome"
    "`"$ServerExe`""
  ) | Set-Content -Path $wrapper -Encoding ASCII
  Register-Service -BinPath "`"$wrapper`""
} else {
  Write-Host "==> Install dependencies (python mode)"
  & $PythonExe -m pip install --upgrade pip
  & $PythonExe -m pip install "$InstallRoot\\pyproject.toml"

  Write-Host "==> Register windows service (python mode)"
  & $PythonExe "$InstallRoot\\service_host\\windows_service.py" install --python $PythonExe --workdir $InstallRoot --home $RuntimeHome
  & $PythonExe "$InstallRoot\\service_host\\windows_service.py" start
}

Write-Host "Install completed."
