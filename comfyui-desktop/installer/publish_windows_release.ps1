param(
  [string]$CenterUrl = "http://117.50.80.158:8099",
  [string]$Username = "admin",
  [string]$Password = "admin123",
  [string]$Version = "",
  [string]$Channel = "stable",
  [string]$Status = "active",
  [string]$MinAgentVersion = "",
  [string]$Notes = "",
  [string]$InstallKey = "",
  [string]$ExePath = "",
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Join-Url([string]$Base, [string]$Path) {
  return ($Base.TrimEnd("/") + "/" + $Path.TrimStart("/"))
}

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

$InstallerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $InstallerDir

if ([string]::IsNullOrWhiteSpace($Version)) {
  $Version = (Get-Date -Format "yyyy.MM.dd.HHmm")
}

if (-not $SkipBuild) {
  Write-Host "==> 开始构建 Windows 安装包"
  $buildScript = Join-Path $InstallerDir "build_windows.ps1"
  Invoke-External -FilePath "powershell.exe" -Arguments @(
    "-NoLogo",
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $buildScript,
    "-CenterUrl",
    $CenterUrl,
    "-InstallKey",
    $InstallKey
  )
}

if ([string]::IsNullOrWhiteSpace($ExePath)) {
  $ExePath = Join-Path $ProjectRoot "installer\\build\\windows\\Output\\PODI-ComfyUI-Agent-Setup.exe"
}

if (-not (Test-Path $ExePath)) {
  throw "未找到安装包：$ExePath。请先安装 Inno Setup 6（ISCC.exe）并重新执行打包。"
}

Write-Host "==> 登录中台"
$loginUrl = Join-Url $CenterUrl "/api/auth/login"
$loginBody = @{
  username = $Username
  password = $Password
} | ConvertTo-Json
$loginResp = Invoke-RestMethod -Method Post -Uri $loginUrl -ContentType "application/json" -Body $loginBody
$token = $loginResp.accessToken
if ([string]::IsNullOrWhiteSpace($token)) {
  throw "登录失败：未拿到 accessToken"
}
$headers = @{ Authorization = "Bearer $token" }

Write-Host "==> 上传安装包到中台"
$fileName = [System.IO.Path]::GetFileName($ExePath)
$fileNameEncoded = [uri]::EscapeDataString($fileName)
$uploadUrl = Join-Url $CenterUrl "/api/admin/comfyui/desktop/releases/upload?filename=$fileNameEncoded"
$uploadRespRaw = Invoke-WebRequest -Method Post -Uri $uploadUrl -Headers $headers -ContentType "application/octet-stream" -InFile $ExePath
$uploadResp = $uploadRespRaw.Content | ConvertFrom-Json

if (-not $uploadResp.downloadUrl -or -not $uploadResp.sha256) {
  throw "上传失败：中台未返回 downloadUrl/sha256"
}

Write-Host "==> 写入安装包版本记录"
$createUrl = Join-Url $CenterUrl "/api/admin/comfyui/desktop/releases"
$releasePayload = @{
  channel = $Channel
  version = $Version
  osType = "windows"
  arch = "x64"
  status = $Status
  downloadUrl = $uploadResp.downloadUrl
  sha256 = $uploadResp.sha256
}
if (-not [string]::IsNullOrWhiteSpace($MinAgentVersion)) {
  $releasePayload.minAgentVersion = $MinAgentVersion
}
if (-not [string]::IsNullOrWhiteSpace($Notes)) {
  $releasePayload.notes = $Notes
}
$releaseJson = $releasePayload | ConvertTo-Json
$releaseResp = Invoke-RestMethod -Method Post -Uri $createUrl -Headers $headers -ContentType "application/json" -Body $releaseJson

Write-Host ""
Write-Host "发布完成："
Write-Host ("- release_id : {0}" -f $releaseResp.id)
Write-Host ("- version    : {0}" -f $releaseResp.version)
Write-Host ("- download   : {0}" -f $releaseResp.downloadUrl)
Write-Host ("- sha256     : {0}" -f $releaseResp.sha256)
$latestPath = '/api/admin/comfyui/desktop/releases/latest/download?os=windows`&arch=x64`&channel={0}' -f $Channel
$latestUrl = Join-Url $CenterUrl $latestPath
Write-Host ("- latest     : {0}" -f $latestUrl)
