# 管理端核心接口

## 用途

- 管理执行节点、能力、工作流、绑定关系与第三方密钥。
- 查询能力调用日志与指标。
- 提供管理端能力测试与基础监控。

## 鉴权

- **管理员 JWT**（`Authorization: Bearer <accessToken>`）

---

## 1) 执行节点（Executors）

### GET /api/admin/executors

### POST /api/admin/executors

**请求体（摘要）**

```json
{
  "id": "executor_comfyui_158",
  "name": "ComfyUI-158",
  "type": "comfyui",
  "base_url": "http://117.50.80.158:8079",
  "status": "active",
  "weight": 1,
  "max_concurrency": 1,
  "config": { "apiKey": "..." },
  "api_key_ids": []
}
```

> 说明：`base_url` 为示例，实际以管理端配置为准（主服务器可能调整）。

### PUT /api/admin/executors/{id}
### DELETE /api/admin/executors/{id}

**错误**

- `EXECUTOR_NOT_FOUND`

---

## 2) 能力管理（Abilities）

### GET /api/admin/abilities
### POST /api/admin/abilities
### PUT /api/admin/abilities/{id}
### DELETE /api/admin/abilities/{id}

**关键字段**

- `provider` / `capability_key` / `display_name`
- `default_params` / `input_schema` / `metadata`
- `executor_id` / `workflow_id`

**错误**

- `ABILITY_NOT_FOUND`
- `EXECUTOR_NOT_FOUND` / `WORKFLOW_NOT_FOUND`

---

## 3) 工作流管理（Workflows）

### GET /api/admin/workflows
### POST /api/admin/workflows
### PUT /api/admin/workflows/{id}
### DELETE /api/admin/workflows/{id}

**关键字段**

- `action` / `name` / `version`
- `definition`（workflow JSON）
- `metadata`

---

## 4) 绑定关系（Workflow Bindings）

### GET /api/admin/workflow-bindings
### POST /api/admin/workflow-bindings
### PUT /api/admin/workflow-bindings/{id}
### DELETE /api/admin/workflow-bindings/{id}

**关键字段**

- `action` / `workflow_id` / `executor_id`
- `priority` / `enabled`

---

## 5) API Key 管理

### GET /api/admin/api-keys
### POST /api/admin/api-keys
### PUT /api/admin/api-keys/{id}
### DELETE /api/admin/api-keys/{id}

**关键字段**

- `provider` / `name` / `key`
- `status` / `daily_quota` / `expire_at`

---

## 6) 能力测试（管理端）

> 按 provider 分流，管理端“能力测试”页调用。

- `POST /api/admin/tests/baidu/quality-upgrade`
- `POST /api/admin/tests/baidu/image-process`
- `POST /api/admin/tests/volcengine/chat`
- `POST /api/admin/tests/volcengine/image`
- `POST /api/admin/tests/kie/market`
- `POST /api/admin/tests/comfyui/workflow`

**错误（常见）**

- `EXECUTOR_NOT_FOUND` / `EXECUTOR_TYPE_NOT_*`
- `COMFYUI_TEST_FAILED` / `KIE_TASK_CREATE_FAILED`

---

## 7) 能力调用日志

### GET /api/admin/abilities/{id}/logs

- 参数：`limit`（1-200）、`offset`

### GET /api/admin/abilities/logs

- 参数：`limit`、`offset`、`abilityId`、`provider`、`capabilityKey`

### POST /api/admin/abilities/logs/{log_id}/resolve

- 仅对 ComfyUI 日志有效，用于补拉历史输出

### GET /api/admin/abilities/logs/export

- 导出 JSON/CSV
- 参数：`start` / `end` / `format`（`csv/json`）

### GET /api/admin/abilities/logs/metrics

- 参数：`windowHours`（1-720）、`provider`、`capabilityKey`、`groupByExecutor`

**错误（常见）**

- `ABILITY_LOG_NOT_FOUND` / `ABILITY_LOG_NOT_COMFYUI`
- `COMFYUI_HISTORY_HTTP_*` / `COMFYUI_STATUS_*`

**一致性要求**

- 日志状态使用 `pending/success/failed`（日志维度），不要与 AbilityTask 状态混用。
- 管理端列表必须拆分为两段状态：`提交` 与 `回调阶段`。
  - `提交`：基于 `status` 判断是否提交成功（提交中/提交成功/提交失败/已取消）。
  - `回调阶段`：基于 `callback_status/callback_http_status/callback_finished_at/callback_id` 判断（待回调/回调成功/回调失败/结果回填中/结果已回填）。
- 结果预览字段解析需按统一顺序兜底（`stored_url` → `result_assets` → `response_payload`）。
- 成功但暂无预览时，UI 文案应为“结果回填中”，避免误判为无结果。

---

## 8) 管理端仪表盘

### GET /api/admin/dashboard/metrics

- 汇总任务/评测/能力任务状态

### GET /api/admin/dashboard/logs

- 返回最近 dispatch/能力调用日志

### GET /api/admin/dashboard/system-config

- 返回系统配置概览（脱敏）

---

## 9) ComfyUI 管理

ComfyUI 相关接口较多，详见 `docs/api/modules/comfyui-admin.md`。
