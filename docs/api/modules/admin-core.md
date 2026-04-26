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
- `vendor_model_id`：可选，绑定到“模型弹药库”的模型目录项；绑定后业务配方可引用稳定模型配置，不再手填第三方模型名。

**错误**

- `ABILITY_NOT_FOUND`
- `EXECUTOR_NOT_FOUND` / `WORKFLOW_NOT_FOUND`
- `VENDOR_MODEL_NOT_FOUND`

### GET /api/admin/abilities/health/summary
### POST /api/admin/abilities/health/refresh
### GET /api/admin/abilities/health/export

用途：按最近有效调用记录汇总能力健康状态，帮助运营先看到“哪些能力需要复测”。该接口只读取日志并刷新能力健康字段，不会主动调用上游模型，也不会消耗第三方额度。

请求：

```text
GET /api/admin/abilities/health/summary?staleHours=24&limit=20
POST /api/admin/abilities/health/refresh?staleHours=24&limit=20
GET /api/admin/abilities/health/export?needsTest=true
```

筛选参数：

- `provider`：按厂商过滤，例如 `openai`、`comfyui`。
- `status`：按能力启停状态过滤，例如 `active`。
- `healthStatus`：按健康状态过滤，可选 `healthy/degraded/failed/unknown`。
- `needsTest`：只导出需要复测的能力。
- `staleOnly`：只导出超过 `staleHours` 未验证的能力。

响应：

```json
{
  "generatedAt": "2026-04-25T10:00:00Z",
  "staleHours": 24,
  "total": 18,
  "healthy": 12,
  "degraded": 2,
  "failed": 1,
  "unknown": 3,
  "staleCount": 4,
  "needsTestCount": 5,
  "items": [
    {
      "abilityId": "comfyui_fission_v2",
      "displayName": "图裂变 · 新高质量版",
      "provider": "comfyui",
      "capabilityKey": "fission_hq",
      "status": "active",
      "healthStatus": "unknown",
      "lastHealthCheckAt": null,
      "successRate": null,
      "finishedLogCount": 0,
      "latestLogStatus": null,
      "latestLogAt": null,
      "stale": true,
      "needsTest": true
    }
  ]
}
```

状态含义：

- `healthy`：最近一次有效调用成功。
- `degraded`：最近一次失败，但最近 50 次有效调用成功率仍不低于 80%。
- `failed`：最近失败且成功率低。
- `unknown`：没有有效调用记录。

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

> 该模块是中台 Key 原始表。“模型弹药库”的第三方 Key 池与这里共用 `api_keys`，普通维护优先使用“模型弹药库”。

### GET /api/admin/api-keys
### POST /api/admin/api-keys
### PUT /api/admin/api-keys/{id}
### DELETE /api/admin/api-keys/{id}

**关键字段**

- `provider` / `name` / `key`
- `status` / `daily_quota` / `expire_at`
- GET/POST/PUT 返回 `key_preview`，不得返回明文 `key`。

---

## 5.1) 模型弹药库 / Vendor API 管理

### GET /api/admin/vendor-api/providers
返回 vendor-api-ops provider 清单、支持的 `apiTypes`、执行模式、是否需要 `global-egress`，以及 `envKeyConfigured`（仅表示运行环境是否配置了该供应商密钥，不返回明文）。

### POST /api/admin/vendor-api/providers/{provider}/egress-check

请求：

```json
{ "check": "models", "includeAuth": false }
```

响应：

```json
{
  "success": true,
  "provider": "openai",
  "check": "models",
  "url": "https://api.openai.com/v1/models",
  "httpStatus": 401,
  "latencyMs": 1319,
  "message": "reachable"
}
```

### GET /api/admin/vendor-api/governance/summary
返回第三方 API 治理摘要，把供应商、模型目录、能力目录、存储密钥、环境密钥和最近调用统计聚合为一张清单。该接口用于管理端后续简化展示，不主动调用上游模型，不消耗额度。

请求：

```text
GET /api/admin/vendor-api/governance/summary?windowHours=24
```

响应：

```json
{
  "baseUrl": "http://117.50.80.158:8310",
  "windowHours": 24,
  "generatedAt": "2026-04-25T10:00:00Z",
  "totals": {
    "providerCount": 5,
    "modelCount": 8,
    "activeModelCount": 8,
    "abilityCount": 18,
    "activeAbilityCount": 18,
    "keyCount": 4,
    "activeStoredKeyCount": 3,
    "envKeyProviderCount": 1,
    "issueCount": 1
  },
  "providers": [
    {
      "provider": "openai",
      "displayName": "OpenAI",
      "providerStatus": "active",
      "requiresGlobalEgress": true,
      "envKeyConfigured": false,
      "runtimeKeyConfigured": true,
      "keyCount": 1,
      "activeStoredKeyCount": 1,
      "modelCount": 1,
      "activeModelCount": 1,
      "abilityCount": 2,
      "activeAbilityCount": 2,
      "succeededCalls": 12,
      "failedCalls": 0,
      "issues": [],
      "suggestions": []
    }
  ],
  "issues": []
}
```

### GET /api/admin/vendor-api/models
返回 backend 当前沉淀的第三方模型目录视图，包括模型 ID、支持蒙版/多图/视频、执行模式、出网要求、路由策略与成本策略。接口会优先读取 `vendor_model_catalog`，目录为空时根据 vendor-api-ops Provider 信息写入一批默认模型。

### GET /api/admin/vendor-api/usage/summary
返回 vendor-api-ops 最近一段时间的第三方调用统计，用于观察厂商、模型、Key 池和上游错误是否稳定。

请求：

```text
GET /api/admin/vendor-api/usage/summary?windowHours=24
```

响应：

```json
{
  "baseUrl": "http://127.0.0.1:8310",
  "windowHours": 24,
  "items": [
    {
      "provider": "openai",
      "model": "gpt-image-2",
      "status": "succeeded",
      "count": 18,
      "errorCode": null,
      "avgLatencyMs": 1420,
      "lastSeenAt": "2026-04-25T10:00:00Z"
    }
  ]
}
```

### POST /api/admin/vendor-api/models/sync/volcengine
从火山 Ark 模型列表接口同步模型目录到 `vendor_model_catalog`。该接口只同步模型 ID、能力边界和来源信息，不保存 API Key 明文；需要后端环境变量 `VOLCENGINE_API_KEY`。

响应：

```json
{
  "provider": "volcengine",
  "sourceUrl": "https://ark.cn-beijing.volces.com/api/v3/models",
  "total": 12,
  "created": 3,
  "updated": 9,
  "skipped": 0
}
```

### POST /api/admin/vendor-api/models
新增模型目录项。该接口只保存模型能力边界与调度策略，不保存第三方 API Key 明文。

请求：

```json
{
  "provider": "openai",
  "model": "gpt-image-2",
  "displayName": "OpenAI · GPT Image 2",
  "status": "active",
  "apiTypes": ["image_generation", "image_edit"],
  "executionModes": ["sync_then_store"],
  "supportsMask": true,
  "supportsMultipleImages": true,
  "supportsVideo": false,
  "supportsText": true,
  "requiresGlobalEgress": true,
  "source": "backend-admin",
  "routePolicy": { "executorType": "vendor_api" },
  "defaultTaskPolicy": { "timeoutSeconds": 180 },
  "inputSchema": {},
  "costPolicy": {},
  "metadata": { "outputFormats": ["png", "jpeg", "webp"] }
}
```

### PATCH /api/admin/vendor-api/models/{modelId}
更新模型目录项，可用于灰度启停、修改能力边界、补充输入 schema 或成本策略。

### GET /api/admin/vendor-api/keys
### POST /api/admin/vendor-api/keys
### PATCH /api/admin/vendor-api/keys/{keyId}
### POST /api/admin/vendor-api/keys/{keyId}/check
### POST /api/admin/vendor-api/providers/{provider}/egress-check

Key 写入中台 `api_keys` 表，返回只允许包含 `keyPreview`，不返回明文。出网检查用于判断厂商网络是否可达；当请求体 `includeAuth=true` 时，中台会优先选择 Key 池里的 active Key，并随本次请求传给 vendor-api-ops 验证厂商鉴权是否可用。单条 Key 检查会使用该 Key 自身验证，并把结果写入 `metadata.lastCheck`。

**错误**

- `VENDOR_API_EXECUTOR_UNAVAILABLE`
- `VENDOR_API_RESPONSE_INVALID`
- `VENDOR_API_AUTH_REQUIRED`
- `VENDOR_API_CLIENT_FORBIDDEN`
- `VENDOR_API_PROVIDER_NOT_SUPPORTED`
- `VENDOR_API_PROXY_UNAVAILABLE`
- `VENDOR_API_TIMEOUT`
- `VENDOR_API_KEY_NOT_FOUND`
- `VENDOR_API_KEY_MISSING`
- `VENDOR_API_KEY_DISABLED`
- `VENDOR_API_KEY_CONCURRENCY_LIMITED`
- `VENDOR_API_AUTH_FAILED`
- `VENDOR_PROVIDER_REGISTRY_UNAVAILABLE`
- `VENDOR_KEY_STATUS_UNAVAILABLE`
- `VENDOR_USAGE_SUMMARY_UNAVAILABLE`
- `VENDOR_GOVERNANCE_DB_UNAVAILABLE`
- `VENDOR_API_RECENT_FAILURES`
- `VOLCENGINE_API_KEY_MISSING`
- `VOLCENGINE_MODEL_SYNC_HTTP_ERROR`
- `VOLCENGINE_MODEL_SYNC_RESPONSE_INVALID`
- `VOLCENGINE_MODEL_SYNC_DATA_INVALID`
- `VENDOR_MODEL_DUPLICATED`
- `VENDOR_MODEL_NOT_FOUND`

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
- 返回新增（成本统计）：
  - 顶层：`total_count`、`total_success_count`、`total_failed_count`、`uncosted_count`、`total_cost`、`avg_cost_per_call`
  - 汇总：`provider_totals[]`、`currency_totals[]`（按厂商/币种的调用数、总成本、均成本）
  - bucket：`total_cost`、`avg_cost`
  - 说明：成本为估算值，来源于能力 `metadata.pricing` 与日志回填。

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
- `response_payload` 建议统一使用公开响应结构（`abilityId/provider/status/images/assets/metadata/...`），避免不同能力日志字段漂移。

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
