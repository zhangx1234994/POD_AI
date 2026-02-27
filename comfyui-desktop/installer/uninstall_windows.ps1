param(
  [string]$InstallRoot = "$env:ProgramData\\PodiComfyuiAgent",
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Continue"

Write-Host "==> Stop and remove service"
$serviceHelper = Join-Path $InstallRoot "service_host\\windows_service.py"
if (Test-Path $serviceHelper) {
  & $PythonExe $serviceHelper stop
  & $PythonExe $serviceHelper remove
} else {
  sc.exe stop PodiComfyuiAgent | Out-Null
  sc.exe delete PodiComfyuiAgent | Out-Null
}

Write-Host "==> Remove install root"
Remove-Item -Recurse -Force -Path $InstallRoot

Write-Host "Uninstall completed."
