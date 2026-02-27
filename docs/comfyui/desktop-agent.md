# ComfyUI 桌面端代理服务（Windows 先行）

## 1. 定位

桌面端是 ComfyUI 服务器上的本地执行程序，职责是：

- 接收中台推送任务
- 本地验签 + 中台二次握手
- 按清单同步模型/插件/工作流/ComfyUI 版本
- 实时上报事件、完成、失败、心跳、告警

目标是让运维同学完成“安装 -> 配置 -> 体检 -> 接入 -> 自动执行”闭环。

## 2. 目录结构

代码位于仓库根目录 `comfyui-desktop/`：

- `agent_core/`：任务执行、配置、状态库、体检、中心端通信
- `agent_server/`：本地 FastAPI（`/health`、`/tasks`、`/status`）
- `app_gui/`：PySide6 中文界面
- `service_host/`：Windows 服务管理脚本
- `installer/`：安装/卸载脚本

## 3. 接入流程

1. 在中台生成一次性注册码（管理员接口）
2. 桌面端 GUI 填写中台地址、ComfyUI 路径和注册码
3. 桌面端调用 `/api/agent/bootstrap/exchange` 换取：
   - `agent_id`
   - `agent_token`
   - `jwt_keys`
4. 本地保存配置并启动常驻服务
5. 中台可直连推送任务到 `http://<host>:18079/tasks`

### 3.1 零配置安装模式（推荐）

运维仅安装 EXE，不做任何手工录入：

1. 安装包内预置固定 `center_url` 与 `install_key`
2. 服务首次启动自动调用 `/api/agent/bootstrap/auto-exchange`
3. 中台返回 `agent_id/agent_token/jwt_keys` 并落地本地配置
4. 自动开始心跳与任务接收

### 3.2 中台管理端操作路径（推荐）

管理端进入：`ComfyUI 管理 -> 桌面端部署`

1. 在“桌面端安装包版本”中发布 `Windows/x64` 启用版本（含下载地址、sha256）
2. 在“桌面端一键安装”选择目标版本并复制命令给运维执行（命令内含 SHA256 校验）
3. 若需手工接入，在“注册码（手动接入备用）”生成短效注册码

### 3.3 Windows 服务器一键打包并发布（推荐）

若代码仓库已在某台 Windows 服务器，可直接执行：

```powershell
powershell -ExecutionPolicy Bypass -File installer\publish_windows_release.ps1 `
  -CenterUrl "http://117.50.80.158:8099" `
  -Username "admin" `
  -Password "admin123" `
  -Version "0.1.0"
```

脚本会自动完成三步：构建 EXE、上传到中台、写入安装包版本记录。

也可直接双击：

- `installer\\build_windows.cmd`
- `installer\\publish_windows_release.cmd`

## 4. 本地配置

默认文件：

- `~/.podi/comfyui-desktop/config.json`
- `~/.podi/comfyui-desktop/state.db`

关键字段：

- `center_url`
- `agent_id`
- `agent_token`
- `jwt_keys[{kid,secret,status}]`
- `comfyui_path`
- `comfyui_port`（默认 8079）
- `agent_port`（默认 18079）
- `heartbeat_interval_sec`（默认 60）

## 5. 本地接口

- `GET /health`：体检 + 运行状态
- `GET /status`：当前配置和摘要
- `POST /tasks`：中台推送任务入口
- `POST /bootstrap/exchange`：本地转发接入（可选）
- `POST /bootstrap/refresh-keys`：刷新验签 key
- `GET /tasks/history`：任务历史
- `POST /updates/check`：手动检查新版本
- `GET /updates/state`：查看最近一次更新检查结果
- `POST /updates/apply`：执行安装包更新（Windows）
- `GET /api/agent/bootstrap/releases/files/{file_name}`：下载中台托管安装包文件

更新状态说明（`/updates/state`）：

- `up_to_date`：当前已是最新
- `update_available`：检测到新版本
- `apply_started`：已触发安装
- `applied`：版本回读确认升级完成
- `apply_failed`：安装失败（查看 payload.error）

心跳上报时会同步 `payload.updateState` 摘要（包含 `status/currentVersion/targetVersion/error`），管理端“桌面端部署”可直接查看每台机器升级状态与失败原因。

## 6. 安全策略

- 任务 token 先本地验签，再调用 `/api/agent/auth/verify`
- 支持多 `kid` 并存，便于密钥轮换
- 注册码短效单次，过期/用尽即失效
- 失败上报包含 `error_code + failed_items`

## 7. 运维建议

- 首次上线优先 1 台灰度机器验证
- 通过后再扩容到同角色机器
- 更新桌面端前先确认中台 release 列表可用
- 如需自动更新执行，可在服务环境变量开启 `PODI_DESKTOP_AUTO_APPLY=true`
- 任务执行失败优先查看：
  1) `state.db` 中 `task_history`
  2) 中台 `/api/agent/tasks/{task_id}/events`
