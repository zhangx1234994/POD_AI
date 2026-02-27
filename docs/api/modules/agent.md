# ComfyUI Agent 接口（中台侧）

## 用途

- 中台接收 Agent 回执、心跳与告警。
- 提供 Manifest 下载与 Token 验证。

## 鉴权

- **任务回执/manifest**：`Authorization: Bearer <task_token>`（scope=task）
- **心跳/告警**：`Authorization: Bearer <agent_token>`（scope=agent）
- **调试**：`AGENT_DEBUG_TOKENS`（仅开发环境）

> Token 由中台签发，Agent 收到任务后会调用 `/api/agent/auth/verify` 进行二次校验。

---

## 1) 协议文档

### GET /api/agent/docs/agent-protocol

**用途**：获取当前协议 Markdown（实时读取仓库文档）。

---

## 2) Token 校验

### POST /api/agent/auth/verify

**请求体**

```json
{
  "token": "<jwt>",
  "agent_id": "comfyui-158",
  "task_id": "agt_20260205_0001",
  "nonce": "<nonce>"
}
```

**响应体**

```json
{
  "ok": true,
  "agentId": "comfyui-158",
  "taskId": "agt_20260205_0001",
  "expiresAt": "2026-02-05T23:59:59Z",
  "scope": "task",
  "policy": { "allow": true }
}
```

**错误**

- `AGENT_TOKEN_REQUIRED` / `AGENT_TOKEN_INVALID` / `AGENT_TOKEN_EXPIRED`
- `AGENT_TOKEN_PAYLOAD_INVALID` / `AGENT_TOKEN_PAYLOAD_MISMATCH`
- `AGENT_TASK_NOT_FOUND` / `AGENT_TASK_FORBIDDEN` / `AGENT_TASK_EXPIRED`

---

## 2.1) 桌面端首次接入（新增）

### POST /api/agent/bootstrap/exchange

**用途**：桌面端使用一次性注册码换取长期配置（`agent_id/agent_token/jwt_keys`）。

**请求体**

```json
{
  "enrollCode": "enroll_xxx",
  "machineName": "comfyui-node-158",
  "host": "117.50.80.158",
  "baseUrl": "http://117.50.80.158:18079",
  "preferredAgentId": "desktop_full_158"
}
```

**响应体**

```json
{
  "agentId": "desktop_full_158",
  "role": "full",
  "centerUrl": "http://117.50.80.158:8099",
  "agentToken": "<jwt>",
  "agentTokenExpiresAt": "2026-02-26T23:10:00Z",
  "heartbeatIntervalSec": 60,
  "jwtKeys": [
    { "kid": "k1", "secret": "xxxx", "status": "active" }
  ]
}
```

**错误**

- `AGENT_ENROLL_CODE_REQUIRED`
- `AGENT_ENROLL_CODE_NOT_FOUND`
- `AGENT_ENROLL_CODE_EXPIRED`
- `AGENT_ENROLL_CODE_USED`
- `AGENT_ENROLL_CODE_INACTIVE`

### POST /api/agent/bootstrap/refresh-keys

**用途**：桌面端刷新本地 JWT 验签 keyset（用于密钥轮换）。

**鉴权**：`Authorization: Bearer <agent_token>`

### GET /api/agent/bootstrap/releases

**用途**：桌面端查询可用安装包版本（用于自动更新检查）。

**鉴权**：`Authorization: Bearer <agent_token>`

**查询参数**

- `channel`（默认 `stable`）
- `os_type`（默认 `windows`）
- `arch`（默认 `x64`）
- `status`（默认 `active`）
- `limit`（默认 `20`）

### GET /api/agent/bootstrap/releases/files/{file_name}

**用途**：下载中台托管的桌面端安装包文件（供安装命令与自动更新使用）。

**错误**

- `AGENT_DESKTOP_RELEASE_FILE_NOT_FOUND`

### POST /api/agent/bootstrap/auto-exchange

**用途**：零配置安装模式下，桌面端使用安装密钥自动接入（免人工录入注册码）。

**请求体**

```json
{
  "installKey": "<install_key>",
  "machineName": "comfyui-node-158",
  "host": "117.50.80.158",
  "baseUrl": "http://117.50.80.158:18079",
  "role": "full"
}
```

**错误**

- `AGENT_BOOTSTRAP_INSTALL_KEY_REQUIRED`
- `AGENT_BOOTSTRAP_INSTALL_KEY_INVALID`
- `AGENT_BOOTSTRAP_INSTALL_KEY_NOT_CONFIGURED`

---

---

## 3) Manifest 拉取

### GET /api/agent/manifests/{manifest_id}

**用途**：Agent 拉取清单（必须 task token）。

**响应体**（示例）

```json
{
  "id": 12,
  "role": "full",
  "version": "2026.02.05-001",
  "content": {
    "comfyui": { "commit": "<sha>" },
    "models": [],
    "plugins": [],
    "workflows": []
  }
}
```

**错误**

- `AGENT_TOKEN_SCOPE_INVALID`
- `AGENT_MANIFEST_NOT_FOUND` / `AGENT_MANIFEST_FORBIDDEN`
- `AGENT_TASK_EXPIRED`

---

## 4) 任务事件回执

### POST /api/agent/tasks/{task_id}/events

**请求体**

```json
{
  "level": "info",
  "step": "models",
  "message": "sync models started",
  "progress": 42,
  "payload": { "note": "optional extra payload" }
}
```

**响应体**

```json
{
  "id": 1,
  "taskId": "agt_20260205_0001",
  "level": "info",
  "message": "sync models started",
  "payload": { "step": "models" },
  "created_at": "2026-02-05T22:40:00Z"
}
```

**错误**

- `AGENT_TASK_NOT_FOUND` / `AGENT_TASK_FORBIDDEN` / `AGENT_TASK_EXPIRED`

---

## 5) 任务完成回执

### POST /api/agent/tasks/{task_id}/complete

**请求体**

```json
{ "summary": "ok", "synced": ["models", "plugins"] }
```

**响应体**

```json
{ "id": "agt_20260205_0001", "agentId": "comfyui-158", "status": "success" }
```

> 约定：Agent 协议使用 `success`，与 AbilityTask 的 `succeeded` 不同；前端展示层需做统一映射。

---

## 6) 任务失败回执

### POST /api/agent/tasks/{task_id}/failed

**请求体**

```json
{
  "error_code": "DOWNLOAD_FAILED",
  "message": "Download xxx.safetensors failed",
  "failed_items": { "models": ["xxx.safetensors"], "plugins": [], "workflows": [] }
}
```

**响应体**

```json
{ "id": "agt_20260205_0001", "agentId": "comfyui-158", "status": "failed" }
```

---

## 7) 心跳

### POST /api/agent/agents/{id}/heartbeat

**请求体**

```json
{
  "status": "active",
  "cpu": 35,
  "mem": 62,
  "disk_free_gb": 120,
  "gpu": { "available": true, "util": 42 },
  "metrics": { "cpu": 0.42, "memory": 0.78, "disk": 0.61, "gpu": 0.55 },
  "payload": {
    "updateState": {
      "status": "applied",
      "currentVersion": "0.2.0",
      "targetVersion": "0.2.0",
      "error": null
    }
  },
  "agent_version": "1.2.0",
  "comfyui_version": "<git_commit>"
}
```

**响应体**

```json
{ "status": "ok", "agentId": "comfyui-158", "receivedAt": "2026-02-05T22:40:00Z" }
```

---

## 8) 告警

### POST /api/agent/agents/{id}/alerts

**请求体**

```json
{
  "type": "disk_low",
  "message": "disk usage 92%",
  "payload": { "disk": 0.92 }
}
```

**响应体**

```json
{ "status": "ok" }
```

**错误**

- `AGENT_NOT_ALLOWED` / `AGENT_NOT_FOUND`

---

## 9) 统一状态字段（新增）

以下任务查询接口会返回统一阶段字段（便于前端区分“提交成功”和“回调成功”）：

- `GET /api/admin/comfyui/tasks`
- `GET /api/admin/comfyui/tasks/{task_id}`

新增字段：

- `submitStatus`：`pending/submitting/submit_failed/submitted`
- `callbackStatus`：`waiting/running/success/failed/not_configured`
- `finalStatus`：`pending/running/success/failed/canceled`
- `errorCode`：标准错误码（可为空）

---

## 11) 管理端桌面接入接口（新增）

### POST /api/admin/comfyui/agents/enroll-codes

用途：生成一次性注册码（短效、可限制最大使用次数）。

### GET /api/admin/comfyui/agents/enroll-codes

用途：查看注册码历史与状态（active/used/expired）。

### GET /api/admin/comfyui/desktop/releases

用途：查看桌面端发布包清单（channel/os/arch/version）。

### POST /api/admin/comfyui/desktop/releases/upload?filename=<file_name>

用途：上传桌面端安装包二进制并返回 `downloadUrl + sha256`，用于后续发布版本记录。

### POST /api/admin/comfyui/desktop/releases

用途：新增桌面端发布包版本。

### PUT /api/admin/comfyui/desktop/releases/{release_id}

用途：更新桌面端发布包状态或下载地址。

### GET /api/admin/comfyui/desktop/releases/{release_id}/download

用途：按发布包 ID 获取下载直链（302）。

### GET /api/admin/comfyui/desktop/releases/latest/download?os=windows&arch=x64&channel=stable

用途：按平台参数获取最新可用安装包直链（302）。

### POST /api/admin/comfyui/manifests/{manifest_id}/repair-plan
### POST /api/admin/comfyui/repair-jobs
### GET /api/admin/comfyui/repair-jobs
### GET /api/admin/comfyui/repair-jobs/{job_id}

用途：将“清单漂移”转成可执行修复任务，并聚合多节点回执状态。

---

## 10) 事件结构标准化（新增）

`POST /api/agent/tasks/{task_id}/events` 请求体支持新增上下文字段（可选）：

- `stage`：阶段（如 `sync_models` / `sync_plugins`）
- `provider`：厂商或业务域
- `nodeId`：执行节点 ID
- `retryCount`：当前重试次数
- `traceId`：链路追踪 ID

> 中台会将这些字段并入事件 payload，便于统一日志检索与问题归因。
