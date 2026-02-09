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
