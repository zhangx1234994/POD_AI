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

## 4.1) 业务能力治理

### GET /api/admin/business/capabilities
### POST /api/admin/business/capabilities
### PATCH /api/admin/business/capabilities/{capabilityId}
### POST /api/admin/business/capabilities/{capabilityId}/promote
### POST /api/admin/business/rollback/{businessKey}

用途：维护图裂变、扩图等业务能力版本，支持默认版本切换、回滚和灰度配方管理。

### POST /api/admin/business/capabilities/{capabilityId}/default-approvals

提交“设为默认版本”的审批申请。目标版本必须是 `active`，已是默认版本或已有待审批申请时会拒绝。

请求：

```json
{
  "note": "灰度验证通过，申请切默认"
}
```

错误：

- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`
- `BUSINESS_DEFAULT_ALREADY_ACTIVE`
- `BUSINESS_DEFAULT_APPROVAL_PENDING`

### GET /api/admin/business/default-approvals

查询默认版本审批记录。

```text
GET /api/admin/business/default-approvals?status=pending&business_key=fission&limit=20
```

### POST /api/admin/business/default-approvals/{approvalId}/approve
### POST /api/admin/business/default-approvals/{approvalId}/reject

审批或驳回默认版本切换。审批通过后会将目标版本切为默认版本，并把同业务其他版本取消默认。

请求：

```json
{
  "note": "确认发布"
}
```

错误：

- `BUSINESS_DEFAULT_APPROVAL_NOT_FOUND`
- `BUSINESS_DEFAULT_APPROVAL_ALREADY_DECIDED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`

### GET /api/admin/business/operation-logs

查询业务能力治理操作日志，管理端用于追踪默认版本申请、审批、驳回等关键动作。

```text
GET /api/admin/business/operation-logs?business_key=fission&limit=20
```

响应摘要：

```json
{
  "items": [
    {
      "id": "bizop_xxx",
      "action": "approve_default_approval",
      "targetType": "business_default_approval",
      "targetId": "bizappr_xxx",
      "businessKey": "fission",
      "actorUsername": "admin",
      "note": "确认发布",
      "createdAt": "2026-04-29T12:05:00"
    }
  ]
}
```

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
如果 vendor-api-ops 临时未授权或不可达，该接口会降级返回空 `items`，避免管理端总览页被单个能力服务拖垮；详细风险仍通过 `/api/admin/vendor-api/governance/summary` 展示。

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

- 汇总任务/评测/能力任务状态。
- 同时返回 `strategy_summary`，用于管理端首页展示近 24 小时业务调用、成功率、计费待处理、回调风险、成本与额度口径。

### GET /api/admin/dashboard/logs

- 返回最近 dispatch/能力调用日志

### GET /api/admin/dashboard/system-config

- 返回系统配置概览（脱敏）

### POST /api/admin/dashboard/strategy-summary/snapshots

用途：保存一份战略指标快照，给周报和阶段复盘使用。

请求：

```json
{
  "windowHours": 168,
  "note": "weekly"
}
```

响应：

```json
{
  "id": "strategy_xxx",
  "generatedAt": "2026-04-29T12:00:00Z",
  "windowHours": 168,
  "note": "weekly",
  "summary": {
    "window_hours": 168,
    "business_total": 12,
    "business_succeeded": 10,
    "business_failed": 2,
    "success_rate": 0.8333,
    "billable": 8,
    "unpriced": 2,
    "no_charge": 2,
    "billing_pending": 2,
    "callback_failed": 0,
    "callback_missing": 0,
    "wallet_settled": 0,
    "wallet_failed": 0,
    "cost_by_currency": {"CNY": 1.23},
    "quota_units": 100,
    "risk_count": 4
  }
}
```

### GET /api/admin/dashboard/strategy-summary/snapshots

- 参数：`limit`，默认 8。
- 返回最近保存的战略指标快照。

### POST /api/admin/dashboard/weekly-report/run

用途：生成一份轻量周报 Markdown，并登记记录。当前阶段不自动发送外部通知；如果请求 `send=true` 但未配置 webhook，会返回 `sendStatus=failed`，但报告文件仍会保存。

请求：

```json
{
  "windowHours": 168,
  "note": "weekly-report",
  "send": false,
  "webhookFormat": "generic"
}
```

### GET /api/admin/dashboard/weekly-report/records

- 参数：`limit`，默认 5。
- 返回最近周报记录。

### POST /api/admin/dashboard/release-preflight/run

用途：运行轻量发布门禁，不触发真实付费生图。当前检查项包括后端存活、Coze 工具箱文档、内部任务查询、ComfyUI 队列、测评目录、评测运行健康、周报/账单守护状态。

请求：

```json
{
  "mode": "light",
  "baseUrl": "http://127.0.0.1:8099",
  "expectServerUrl": "http://10.11.0.7:8099"
}
```

响应重点字段：

- `status`：`passed/warning/blocked`。
- `canRelease`：是否没有阻塞项。
- `blockingCount`：阻塞项数量。
- `warningCount`：提醒项数量。
- `checks[]`：每个检查项的结果、详情和处理建议。

### GET /api/admin/dashboard/release-preflight/snapshots

- 参数：`limit`，默认 5。
- 返回最近发布门禁记录。

### POST /api/admin/dashboard/release-patrol/records

用途：人工登记完整巡检结果。完整巡检会真实提交启用的测评工作流，可能产生成本，因此不在管理端自动触发。

请求：

```json
{
  "status": "passed",
  "command": "python3 backend/scripts/patrol_eval_workflows.py ...",
  "reportPath": "reports/eval_patrol_20260429_120000.json",
  "note": "人工确认完整巡检通过",
  "summary": {
    "total": 22,
    "failedOrUnfinished": 0,
    "abilityHealthEvidence": []
  }
}
```

### POST /api/admin/dashboard/release-patrol/import-report

用途：从后端工作目录内的 JSON 巡检报告导入完整巡检记录。路径必须在 backend 目录内，避免任意文件读取。

导入新版 `backend/scripts/patrol_eval_workflows.py` 生成的报告时，后端会自动归一化：

- `total`：本次巡检工作流总数。
- `succeeded`：状态成功且有图片或结构化结果回填的数量。
- `failedOrUnfinished`：失败、未完成或“成功但无回填”的数量。
- `outputReady/noOutput`：结果回填数量和无回填数量。
- `failedItems`：失败项明细，包含工作流、runId、taskId、错误摘要。
- `abilityHealthEvidence`：每条工作流的健康证据，管理端用于展示“最近巡检健康证据”。

### GET /api/admin/dashboard/release-patrol/records

- 参数：`limit`，默认 5。
- 返回最近完整巡检记录。

### POST /api/admin/dashboard/release-decisions/records

用途：登记本次上线结论。该接口不执行部署，只把“可上线 / 暂缓 / 阻塞”的人工判断和当时的门禁、巡检摘要落成记录，便于复盘。

请求：

```json
{
  "status": "approved",
  "title": "确认可上线：可以上线",
  "preflightId": "preflight_xxx",
  "patrolId": "patrol_xxx",
  "note": "轻量门禁、完整巡检和能力状态均已确认",
  "summary": {
    "readinessTitle": "可以上线",
    "blockers": [],
    "warnings": []
  }
}
```

字段说明：

- `status`：`approved/deferred/blocked`，分别表示确认可上线、暂缓上线、阻塞上线。
- `preflightId`：最近轻量门禁记录 ID，可为空。
- `patrolId`：最近完整巡检记录 ID，可为空。
- `summary`：记录当时页面展示的阻塞项、提醒项和结论摘要。

### GET /api/admin/dashboard/release-decisions/records

- 参数：`limit`，默认 5。
- 返回最近上线结论登记。

**错误（常见）**

- `REPORT_PATH_REQUIRED`
- `REPORT_PATH_OUTSIDE_BACKEND`
- `REPORT_NOT_FOUND`
- `REPORT_JSON_INVALID`
- `REPORT_JSON_NOT_OBJECT`
- `RELEASE_DECISION_STATUS_INVALID`

---

## 9) ComfyUI 管理

ComfyUI 相关接口较多，详见 `docs/api/modules/comfyui-admin.md`。
