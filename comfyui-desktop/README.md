# ComfyUI Desktop Agent (Windows First)

This folder provides a unified desktop package:

- local agent service (`agent_server`)
- runtime core (`agent_core`)
- Chinese GUI (`app_gui`)
- Windows service helper (`service_host`)
- installer scripts (`installer`)

## Quick start (dev)

```bash
cd comfyui-desktop
python -m venv .venv
source .venv/bin/activate
pip install -e .
comfyui-desktop-server
```

Open another terminal:

```bash
cd comfyui-desktop
source .venv/bin/activate
comfyui-desktop-gui
```

Default local endpoints:

- `GET http://127.0.0.1:18079/health`
- `GET http://127.0.0.1:18079/status`
- `POST http://127.0.0.1:18079/tasks`
- `POST http://127.0.0.1:18079/updates/check`
- `GET http://127.0.0.1:18079/updates/state`
- `POST http://127.0.0.1:18079/updates/apply`

## Runtime files

By default data is stored in:

- `~/.podi/comfyui-desktop/config.json`
- `~/.podi/comfyui-desktop/state.db`
- `~/.podi/comfyui-desktop/logs/`

Override by env:

- `COMFYUI_DESKTOP_HOME=/custom/path`

## Windows install

Run as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File installer\install_windows.ps1 `
  -CenterUrl "http://117.50.80.158:8099" `
  -InstallKey "<中台安装密钥>" `
  -ComfyuiPath "C:\ComfyUI"
```

Uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File installer\uninstall_windows.ps1
```

## Zero-config mode

When `center_url + install_key` are present in runtime config, service startup
will auto call:

- `POST /api/agent/bootstrap/auto-exchange`

Then it saves `agent_id/agent_token/jwt_keys` locally and starts heartbeat.

Update behavior:

- service checks updates periodically (via `/api/agent/bootstrap/releases`)
- manual apply endpoint: `POST /updates/apply`
- optional auto apply: set `PODI_DESKTOP_AUTO_APPLY=true`

## Build single setup EXE

Use:

```powershell
powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1 `
  -CenterUrl "http://117.50.80.158:8099" `
  -InstallKey "<中台安装密钥>"
```

If Inno Setup (`ISCC.exe`) is installed, it outputs:

- `installer\build\windows\Output\PODI-ComfyUI-Agent-Setup.exe`

## One-click publish to center

On Windows build server:

```powershell
powershell -ExecutionPolicy Bypass -File installer\publish_windows_release.ps1 `
  -CenterUrl "http://117.50.80.158:8099" `
  -Username "admin" `
  -Password "admin123" `
  -Version "0.1.0"
```

This script will:

1. run build script
2. upload installer to `/api/admin/comfyui/desktop/releases/upload`
3. create release record in `/api/admin/comfyui/desktop/releases`

Or double click:

- `installer\publish_windows_release.cmd`
