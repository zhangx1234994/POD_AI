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

---

## 7) Manifest 管理

### GET /api/admin/comfyui/manifests
### POST /api/admin/comfyui/manifests
### GET /api/admin/comfyui/manifests/{id}
### PUT /api/admin/comfyui/manifests/{id}

**字段摘要**

- `role`：服务器角色（full/lite 等）
- `version`：清单版本
- `content`：模型/插件/工作流清单
- `downloadUrl`：可选外部下载地址

---

## 8) 任务下发与回执（管理端侧）

### GET /api/admin/comfyui/tasks
### POST /api/admin/comfyui/tasks
### GET /api/admin/comfyui/tasks/{task_id}
### POST /api/admin/comfyui/tasks/{task_id}/push
### GET /api/admin/comfyui/tasks/{task_id}/events

**说明**

- `POST /tasks` 会生成 `task_id` 与 `token_nonce`，用于 Agent 回执。
- `POST /tasks/{task_id}/push` 会向 Agent 推送任务（失败返回 `AGENT_PUSH_FAILED`）。

---

## 9) 告警查询

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
