# ComfyUI 管理接口

## 用途

- 管理 LoRA / 模型 / 插件 / 版本清单。
- 对齐多台 ComfyUI 服务器资源。
- 管理 Agent、Manifest、任务下发与告警。

## 鉴权

- 全部接口均需 **管理员 Bearer Token**。

---

## 1) LoRA 素材库

### GET /api/admin/comfyui/loras

**用途**：查询 LoRA 库（可选拉取服务器未入库文件）。

**参数**

- `executorId`：可选，传入时返回 `installedFiles/untrackedFiles`

**响应体**（摘要）

```json
{
  "executorId": "executor_comfyui_xxx",
  "items": [
    {
      "id": 1,
      "file_name": "杯子1124.safetensors",
      "display_name": "杯子印花 LoRA",
      "base_models": ["qwen_image_edit_2509"],
      "tags": ["cup"],
      "status": "active"
    }
  ],
  "untrackedFiles": ["unknown.safetensors"]
}
```

### POST /api/admin/comfyui/loras

**请求体**

```json
{
  "file_name": "杯子1124.safetensors",
  "display_name": "杯子印花 LoRA",
  "base_models": ["qwen_image_edit_2509"],
  "tags": ["cup"],
  "status": "active"
}
```

### PUT /api/admin/comfyui/loras/{id} / DELETE

---

## 2) 模型资源清单

### GET /api/admin/comfyui/model-catalog

**用途**：维护模型下载地址与来源。

**响应体**（摘要）

```json
{
  "items": [
    {
      "id": 11,
      "file_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
      "display_name": "Qwen Image Edit 2509",
      "model_type": "unet",
      "source_url": "https://...",
      "download_url": "https://...",
      "status": "active"
    }
  ]
}
```

### POST /api/admin/comfyui/model-catalog

**请求体**（摘要）

```json
{
  "file_name": "qwen_image_edit_2509_fp8_e4m3fn.safetensors",
  "display_name": "Qwen Image Edit 2509",
  "model_type": "unet",
  "source_url": "https://...",
  "download_url": "https://..."
}
```

### PUT /api/admin/comfyui/model-catalog/{id} / DELETE

---

## 3) 插件资源清单

### GET /api/admin/comfyui/plugin-catalog

**用途**：维护插件节点与仓库信息。

**请求/响应字段**（摘要）

- `node_key`：插件节点 key（来自 `/object_info`）
- `display_name`：显示名称
- `package_name`：仓库/包名（可选）
- `version`：版本或 commit（可选）
- `source_url` / `download_url`

### POST /api/admin/comfyui/plugin-catalog
### PUT /api/admin/comfyui/plugin-catalog/{id} / DELETE

---

## 4) ComfyUI 版本清单

### GET /api/admin/comfyui/version-catalog

**用途**：维护 ComfyUI 版本与下载信息。

### POST /api/admin/comfyui/version-catalog
### PUT /api/admin/comfyui/version-catalog/{id} / DELETE

### POST /api/admin/comfyui/version-catalog/sync

**用途**：从 GitHub tag 同步增量版本。

**错误**

- `COMFYUI_VERSION_SOURCE_INVALID`
- `COMFYUI_VERSION_SYNC_FAILED`

### GET /api/admin/comfyui/resources/options?type=lora|model|plugin|version&status=active

**用途**：为管理端/测评端提供统一下拉选项真源，避免静态枚举。

---

---

## 5) 服务器信息与对齐

### GET /api/admin/comfyui/models

- `executorId` 必填
- `includeNodes=true` 时返回节点列表（用于对齐差异）

### GET /api/admin/comfyui/system-stats

- 代理 ComfyUI `/system_stats`

### GET /api/admin/comfyui/queue-status
### GET /api/admin/comfyui/queue-summary

- 代理 ComfyUI `/queue/status`

### POST /api/admin/comfyui/server-diff
### GET /api/admin/comfyui/server-diff

**用途**：保存/查询服务器差异快照。

---

## 6) Agent 管理（管理端）

### GET /api/admin/comfyui/agents
### POST /api/admin/comfyui/agents
### PUT /api/admin/comfyui/agents/{agent_id}
### DELETE /api/admin/comfyui/agents/{agent_id}

**字段摘要**

- `id`：Agent ID
- `name` / `role`
- `baseUrl`：Agent 对外地址
- `allowed`：白名单控制
- `config`：自定义配置

### POST /api/admin/comfyui/agents/{agent_id}/token

**用途**：签发 agent token（scope=agent）。

### POST /api/admin/comfyui/agents/enroll-codes
### GET /api/admin/comfyui/agents/enroll-codes

**用途**：生成/查看桌面端接入注册码（短效、单次或限次）。

> 零配置安装模式可不走注册码：配置后端环境变量 `AGENT_BOOTSTRAP_INSTALL_KEY`，桌面端改用
> `/api/agent/bootstrap/auto-exchange` 自动建联。

---

## 7) Manifest 管理

### GET /api/admin/comfyui/manifests
### POST /api/admin/comfyui/manifests
### GET /api/admin/comfyui/manifests/{id}
### PUT /api/admin/comfyui/manifests/{id}
### POST /api/admin/comfyui/manifests/{id}/publish
### POST /api/admin/comfyui/manifests/{id}/rollback
### GET /api/admin/comfyui/manifests/{id}/drift?agent_id=...
### POST /api/admin/comfyui/manifests/{id}/repair-plan

`repair-plan` 用于把“漂移差异”转换为可执行动作（仅增量补齐，不自动删除）。

请求体（示例）：

```json
{
  "agentIds": ["comfyui-158"],
  "mode": "additive"
}
```

响应体包含：

- `items[].actions`：建议动作（如 `sync_models/sync_plugins/sync_workflows/sync_comfyui`）
- `items[].missingItems`：缺失资源明细
- `summary`：可执行节点数、跳过节点数、动作总数

**字段摘要**

- `role`：服务器角色（full/lite 等）
- `version`：清单版本
- `status`：`draft/published/rolled_back`
- `content`：模型/插件/工作流清单
- `downloadUrl`：可选外部下载地址

说明：

- 发布（publish）会将同角色当前 `published` 清单自动标记为 `rolled_back`。
- 回滚（rollback）可指定 `targetManifestId`，用于将历史版本重新置为 `published`。
- 漂移对比（drift）会返回“清单期望值 vs 节点上报快照”的差异。

---

## 8) 漂移修复任务（新增）

### POST /api/admin/comfyui/repair-jobs
### GET /api/admin/comfyui/repair-jobs
### GET /api/admin/comfyui/repair-jobs/{job_id}

用途：将 repair-plan 下发为多节点任务，并聚合执行状态。

聚合字段（与统一状态契约一致）：

- `items[].submitStatus`
- `items[].callbackStatus`
- `items[].finalStatus`
- `items[].failedItems`

---

## 9) 任务下发与回执（管理端侧）

### GET /api/admin/comfyui/tasks
### POST /api/admin/comfyui/tasks
### GET /api/admin/comfyui/tasks/{task_id}
### POST /api/admin/comfyui/tasks/{task_id}/push
### GET /api/admin/comfyui/tasks/{task_id}/events

新增统一状态字段（查询接口）：

- `submitStatus`：`pending/submitting/submit_failed/submitted`
- `callbackStatus`：`waiting/running/success/failed/not_configured`
- `finalStatus`：`pending/running/success/failed/canceled`
- `errorCode`：标准错误码（可为空）

**说明**

- `POST /tasks` 会生成 `task_id` 与 `token_nonce`，用于 Agent 回执。
- `POST /tasks/{task_id}/push` 会向 Agent 推送任务（失败返回 `AGENT_PUSH_FAILED`）。

---

## 10) 告警查询

### GET /api/admin/comfyui/alerts

**参数**：`agent_id` / `alert_type` / `limit`

**响应体**

```json
[
  {
    "id": 1,
    "agentId": "comfyui-158",
    "alertType": "disk_low",
    "message": "disk usage 92%",
    "created_at": "2026-02-05T22:40:00Z"
  }
]
```

---

## 11) 角色主节点与监控汇总（新增）

### GET /api/admin/comfyui/roles/{role}/primary-agent
### POST /api/admin/comfyui/roles/{role}/primary-agent

用途：将“主服务器”从固定 IP 改为可切换指针（按角色维护）。

### GET /api/admin/comfyui/monitoring/summary?window_hours=24
### GET /api/admin/comfyui/monitoring/queues?window_hours=24
### GET /api/admin/comfyui/monitoring/errors?window_hours=24&limit=100

用途：统一查询多队列运行概况（按 provider + agent lane）：

- `total/queued/running/succeeded/failed`
- `avgWaitSeconds/failureRate/retryCount`

---

## 12) 运行策略中心（新增）

### GET /api/admin/comfyui/policies/concurrency
### PUT /api/admin/comfyui/policies/concurrency
### GET /api/admin/comfyui/policies/retry
### PUT /api/admin/comfyui/policies/retry

用途：按平台/队列/节点维护并发与重试策略，策略持久化到中台数据库。

---

## 13) 桌面端版本发布（新增）

### GET /api/admin/comfyui/desktop/releases
### POST /api/admin/comfyui/desktop/releases/upload?filename=<file_name>
### POST /api/admin/comfyui/desktop/releases
### PUT /api/admin/comfyui/desktop/releases/{release_id}
### GET /api/admin/comfyui/desktop/releases/{release_id}/download
### GET /api/admin/comfyui/desktop/releases/latest/download?os=windows&arch=x64&channel=stable

用途：维护桌面端安装包发布清单（版本、下载地址、校验值、最小兼容版本）。

`/desktop/releases/upload` 说明：

- 请求体：二进制流（`application/octet-stream`）
- 查询参数：`filename`（可选，建议传 `PODI-ComfyUI-Agent-Setup.exe`）
- 响应：`fileName/fileSize/sha256/downloadUrl`
- 常见错误：
  - `AGENT_DESKTOP_RELEASE_FILE_EMPTY`
  - `AGENT_DESKTOP_RELEASE_FILE_TOO_LARGE`

管理端操作建议：

- 进入 `ComfyUI 管理 -> 桌面端部署`
- 先发布 `Windows/x64` 的启用版本
- 选择目标版本后复制“一键安装命令”给运维执行（命令内置 SHA256 校验）
