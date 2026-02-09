# ComfyUI 服务器管理（中台 ↔ Agent 协议与实现规范）

> 版本：2026-02-05
> 目标：用“可下发清单 + 主动推送任务 + 回执/心跳”统一多台 ComfyUI 服务器的模型/插件/工作流一致性。

## 实时接口文档（对外同步）

- Swagger UI：`http://<center_host>:8099/docs`
- OpenAPI JSON：`http://<center_host>:8099/openapi.json`
- 协议 Markdown：`http://<center_host>:8099/api/agent/docs/agent-protocol`（以本仓库文档实时渲染）
- 过滤说明：`/api/agent/*` 统一标记在 `agent` tag，`/api/admin/comfyui/*` 统一标记在 `admin-agent` tag。

## 1. 边界与职责

### 1.1 中台职责（控制面）
- 维护 **资源清单（Manifest）** 与版本历史。
- 生成任务并 **主动推送** 到 Agent（不轮询）。
- 维护 Agent 白名单、鉴权与任务状态机。
- 接收日志/回执/心跳/告警，并提供运维视图。

### 1.2 Agent 职责（执行面）
- 接收任务，校验鉴权并执行。
- 拉取 Manifest 并按动作执行（模型/插件/工作流同步）。
- 回传执行日志与成功/失败回执。
- 定期心跳与异常告警。

### 1.3 通信与端口约定
- Agent API **独立端口**（不与 ComfyUI 8079 冲突）。
- **默认端口：18079**（如需变更须在配置中显式声明）。
- 中台必须可直连 Agent（公网 IP / 端口映射 / 防火墙放行）。

> 原则：中台只管理“目标状态”，Agent 只负责“执行与回执”。

---

## 2. 资源与版本管理（核心）

### 2.1 资源清单（Manifest）
- **按服务器角色维护**：如 `full` / `lite`。
- **清单内容建议**：
  - ComfyUI 版本（Git commit 或 tag）
  - plugins 列表（即 ComfyUI `custom_nodes`，repo + commit）
  - workflows 列表（repo + commit）
  - models 列表（url + sha256 + size + dest）
- 插件依赖可写入 `plugins[].requirements` 或 `plugins[].dependencies`，**默认仅记录，不自动安装**。

### 2.2 URL 与下载地址维护
- 模型/插件 **不落中台存储**，只维护 URL 与校验信息。
- 资源字段建议：`url`、`sha256`、`size`、`name`、`dest_path`。
- URL 可替换，Agent 逻辑不需要改动。
- 若清单未填写 `download_url`，中台会提供 `/api/agent/manifests/{id}` 临时拉取地址，基准域名由 `AGENT_MANIFEST_BASE_URL` 控制。

### 2.3 清单生成与版本化
- 每次发布生成 **manifest_version**。
- 保存历史版本，支持回滚。
- 清单可导出 JSON 供 Agent 拉取。

---

## 3. 任务管理与下发（核心）

### 3.1 任务创建
- 基于“服务器角色”生成任务：
  - `task_id`、`agent_id`
  - `manifest_url`
  - `actions`（`sync_models` / `sync_plugins` / `sync_workflows` / `restart`）
  - `expires_at`（防重放）

### 3.2 任务推送
- 中台 **直接 POST /tasks** 到 Agent。
- 若 Agent 返回 `409 busy`：
  - 中台标记为“待重试”
  - 手动或策略性重试（可加退避）

### 3.3 状态机与回执
- 中台维护任务生命周期：
  - `pending → running → success / failed / rejected`
- 每个任务记录日志与结果摘要。
- **任务超时**：默认 **60 分钟**（超时后中台判定过期并返回 409；失败回执需由 Agent/人工补全）。

---

## 4. 安全与鉴权（必须）

### 4.1 Token 签发
- 中台生成短效 JWT（HS256）：包含 `agent_id/task_id/nonce/exp`。
- **建议携带 `kid`**，便于密钥轮换。
- 签名密钥由中台统一管理并分发给 Agent 用于验签（Agent 不生成 token）。
- token `scope` 用于区分任务/心跳/告警；Agent 需按 scope 调用对应接口。
- 心跳/告警 token 可由管理端接口签发：`POST /api/admin/comfyui/agents/{agent_id}/token`（默认 TTL=`AGENT_HEARTBEAT_TOKEN_TTL`）。
- **开发环境临时白名单**：设置 `AGENT_DEBUG_TOKENS`（逗号分隔）后，`/api/agent/*` 会接受这些 token 直接通过鉴权（`scope=debug`）。仅限联调用途，线上必须移除。

### 4.2 握手校验接口
- 中台提供 `POST /api/agent/auth/verify`。
- Agent 收到任务后必须二次确认合法性。

### 4.3 白名单管理
- 中台维护 Agent 白名单（`agent_id → allowed`）。
- 支持禁用某一台服务器。

### 4.4 HTTPS
- 推送、回执、心跳、告警 **必须 HTTPS**。
- **密钥轮换**：Agent 需支持多密钥并存（按 `kid` 选择）。

---

## 5. 日志与回执系统（必须）

### 5.1 日志收集
- Agent 调用 `POST /api/agent/tasks/{task_id}/events`。
- 日志分级：`info / warn / error`。
- 单条日志建议 **≤ 4KB**，超过会被截断。

### 5.2 任务回执
- `POST /api/agent/tasks/{task_id}/complete`
- `POST /api/agent/tasks/{task_id}/failed`
- 失败回执需包含失败阶段与失败项列表。

### 5.3 告警
- Agent 调用 `POST /api/agent/agents/{id}/alerts`。
- 支持短信/邮件/钉钉/企业微信（可选）。
- 建议枚举：`comfyui_down` / `disk_low` / `download_fail` / `checksum_mismatch` / `plugin_sync_fail`。

---

## 6. 节点健康管理（必须）

### 6.1 心跳
- Agent 每 60s 发送 `POST /api/agent/agents/{id}/heartbeat`。
- 指标建议：CPU / 内存 / 磁盘 / GPU。

### 6.2 离线判定
- 中台按心跳超时判定掉线。
- **中台不轮询 Agent**。

---

## 7. 控制面（面向运维）

### 7.1 Agent 管理
- 在线/离线状态
- 当前 ComfyUI 版本
- 最近一次同步结果

### 7.2 任务管理
- 发起任务 / 重试 / 终止（可选）

### 7.3 差异对比
- “主清单 vs 子服务器清单”差异展示（可选）

---

## 8. 扩展能力（后续）

- 资源分组 / 动态分发
- 灰度推送（先小部分服务器）
- 任务调度策略（避开高峰下载）
- 审计日志（谁触发、何时触发、变更了什么）

---

## 9. 中台端接口清单（现行实现）

### Agent 侧调用（/api/agent）

- 统一使用 `Authorization: Bearer <jwt>` 传递 token。
- `POST /api/agent/auth/verify`
- `GET /api/agent/manifests/{manifest_id}`
- `POST /api/agent/tasks/{task_id}/events`
- `POST /api/agent/tasks/{task_id}/complete`
- `POST /api/agent/tasks/{task_id}/failed`
- `POST /api/agent/agents/{id}/heartbeat`
- `POST /api/agent/agents/{id}/alerts`

### 管理端调用（/api/admin/comfyui）

- `GET /api/admin/comfyui/agents`
- `POST /api/admin/comfyui/agents`
- `PUT /api/admin/comfyui/agents/{agent_id}`
- `DELETE /api/admin/comfyui/agents/{agent_id}`
- `POST /api/admin/comfyui/agents/{agent_id}/token`
- `GET /api/admin/comfyui/manifests`
- `POST /api/admin/comfyui/manifests`
- `GET /api/admin/comfyui/manifests/{id}`
- `PUT /api/admin/comfyui/manifests/{id}`
- `GET /api/admin/comfyui/tasks`
- `POST /api/admin/comfyui/tasks`
- `GET /api/admin/comfyui/tasks/{task_id}`
- `POST /api/admin/comfyui/tasks/{task_id}/push`
- `GET /api/admin/comfyui/tasks/{task_id}/events`
- `GET /api/admin/comfyui/alerts`

---

## 10. 中台端数据表（已落库）

- `agents`（id、host、status、allowed、last_seen_at、metrics）
- `agent_manifests`（id、role、version、download_url、content）
- `agent_tasks`（task_id、agent_id、status、expires_at、result_payload）
- `agent_task_events`（task_id、level、message、payload）
- `agent_alerts`（agent_id、alert_type、message、payload）

> 注：表名已与业务侧 `tasks` 表避让。

---

## 11. Manifest JSON 示例（建议）

```json
{
  "manifest_version": "2026.02.05-001",
  "role": "full",
  "comfyui": {
    "repo": "https://github.com/comfyanonymous/ComfyUI",
    "commit": "abcd1234"
  },
  "plugins": [
    {
      "name": "comfyui-essentials",
      "repo": "https://github.com/cubiq/ComfyUI_essentials",
      "commit": "9c1a2f1",
      "requirements": ["sentencepiece==0.2.0"]
    }
  ],
  "workflows": [
    {
      "name": "sifang_lianxu",
      "repo": "https://git.example.com/podi/workflows",
      "commit": "21f4b88"
    }
  ],
  "models": [
    {
      "name": "qwen_image_edit_2511_fp8mixed.safetensors",
      "url": "https://mirror.example.com/models/qwen_image_edit_2511_fp8mixed.safetensors",
      "sha256": "<sha256>",
      "size": 123456789,
      "dest_path": "models/unet/qwen_image_edit_2511_fp8mixed.safetensors"
    }
  ]
}
```

---

## 12. 任务 JSON 示例（建议）

```json
{
  "task_id": "task_20260205_0001",
  "agent_id": "comfyui-158",
  "token": "<task_jwt>",
  "nonce": "<nonce>",
  "manifest_url": "https://podi.example.com/manifests/full/2026.02.05-001.json",
  "actions": {
    "sync_models": true,
    "sync_plugins": true,
    "sync_workflows": true
  },
  "expires_at": "2026-02-05T23:59:59Z"
}
```

---

## 13. 请求/响应/错误（必备）

### 13.1 /api/agent/auth/verify

**请求**
```json
{ "token": "<jwt>" }
```

> 说明：`agent_id/task_id/nonce` 可选（用于日志或排查），实际鉴权以 token 为准。
> 若请求体传入 `agent_id/task_id/nonce`，中台会与 token 内 claims 比对，不匹配将返回 `AGENT_TOKEN_PAYLOAD_MISMATCH`。

**响应**
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
- `AGENT_TOKEN_KID_REQUIRED` / `AGENT_TOKEN_KID_INVALID`
- `AGENT_TOKEN_SCOPE_INVALID`
- `AGENT_TOKEN_PAYLOAD_MISMATCH`
- `AGENT_NOT_ALLOWED` / `AGENT_NOT_FOUND`
- `AGENT_TASK_NOT_FOUND` / `AGENT_TASK_FORBIDDEN` / `AGENT_TASK_EXPIRED`

### 13.2 /api/agent/tasks/{task_id}/events

**请求**
```json
{
  "level": "info",
  "step": "models",
  "message": "sync models started",
  "progress": 42,
  "payload": { "note": "optional extra payload" }
}
```

**响应**
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
- `AGENT_TOKEN_REQUIRED` / `AGENT_TOKEN_INVALID` / `AGENT_TOKEN_EXPIRED`
- `AGENT_TOKEN_SCOPE_INVALID`
- `AGENT_TASK_FORBIDDEN` / `AGENT_TASK_NOT_FOUND` / `AGENT_TASK_EXPIRED`

### 13.3 /api/agent/tasks/{task_id}/complete

**请求**
```json
{ "summary": "ok", "synced": ["models", "plugins"] }
```

**响应**
```json
{
  "id": "agt_20260205_0001",
  "agentId": "comfyui-158",
  "status": "success"
}
```

**错误**
- `AGENT_TOKEN_REQUIRED` / `AGENT_TOKEN_INVALID` / `AGENT_TOKEN_EXPIRED`
- `AGENT_TOKEN_SCOPE_INVALID`
- `AGENT_TASK_FORBIDDEN` / `AGENT_TASK_NOT_FOUND` / `AGENT_TASK_EXPIRED`

### 13.4 /api/agent/tasks/{task_id}/failed

**请求**
```json
{ "error_code": "DOWNLOAD_FAILED", "message": "Download xxx.safetensors failed", "failed_items": { "models": ["xxx.safetensors"] } }
```

**响应**
```json
{
  "id": "agt_20260205_0001",
  "agentId": "comfyui-158",
  "status": "failed"
}
```

**错误**
- `AGENT_TOKEN_REQUIRED` / `AGENT_TOKEN_INVALID` / `AGENT_TOKEN_EXPIRED`
- `AGENT_TOKEN_SCOPE_INVALID`
- `AGENT_TASK_FORBIDDEN` / `AGENT_TASK_NOT_FOUND` / `AGENT_TASK_EXPIRED`

### 13.5 /api/agent/agents/{id}/heartbeat

**请求**
```json
{
  "status": "active",
  "cpu": 35,
  "mem": 62,
  "disk_free_gb": 120,
  "gpu": { "available": true, "util": 42 },
  "metrics": { "cpu": 0.42, "memory": 0.78, "disk": 0.61, "gpu": 0.55 }
}
```

**响应**
```json
{ "status": "ok", "agentId": "comfyui-158", "receivedAt": "2026-02-05T22:40:00Z" }
```

**错误**
- `AGENT_TOKEN_REQUIRED` / `AGENT_TOKEN_INVALID` / `AGENT_TOKEN_EXPIRED`
- `AGENT_TOKEN_SCOPE_INVALID`
- `AGENT_NOT_ALLOWED` / `AGENT_NOT_FOUND`

### 13.6 /api/admin/comfyui/tasks

**请求**
```json
{
  "agentId": "comfyui-158",
  "manifestId": 12,
  "actions": ["sync_models", "sync_plugins"],
  "expiresAt": "2026-02-05T23:59:59Z"
}
```

**响应**
```json
{
  "id": "agt_20260205_0001",
  "agentId": "comfyui-158",
  "manifestId": 12,
  "status": "running"
}
```

**错误**
- `AGENT_NOT_FOUND` / `AGENT_NOT_ALLOWED`
- `AGENT_MANIFEST_NOT_FOUND`
- `AGENT_BASE_URL_MISSING` / `AGENT_PUSH_FAILED`

---

### 13.7 /api/admin/comfyui/agents/{agent_id}/token

**请求**
```json
{ "ttlSeconds": 3600 }
```

**响应**
```json
{
  "token": "<jwt>",
  "expiresAt": "2026-02-05T23:59:59Z",
  "scope": "agent",
  "agentId": "comfyui-158"
}
```

**错误**
- `AGENT_NOT_FOUND` / `AGENT_NOT_ALLOWED`

### 13.8 /api/admin/comfyui/alerts

**请求**
```
GET /api/admin/comfyui/alerts?agent_id=comfyui-158&alert_type=disk_low&limit=50
```

**响应**
```json
[
  {
    "id": 1,
    "agentId": "comfyui-158",
    "alertType": "disk_low",
    "message": "disk usage 92%",
    "payload": { "disk": 0.92 },
    "created_at": "2026-02-05T22:40:00Z"
  }
]
```

**错误**
- 无（返回空数组表示无告警）

---

## 14. 幂等与原子性要求

- 下载必须 **先校验再替换**（临时目录 → sha256 → 原子替换）。
- 任务重复提交不应破坏环境（同 `task_id` 或同 `manifest_version`）。
- 失败需可重试，且可恢复到一致状态。
