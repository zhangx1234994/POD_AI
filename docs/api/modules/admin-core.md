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

### GET /api/admin/business/quality-samples
### POST /api/admin/business/quality-samples
### PATCH /api/admin/business/quality-samples/{sampleId}
### DELETE /api/admin/business/quality-samples/{sampleId}

维护固定质量样例库。样例用于候选版本同批复跑、测评端只读复用和默认版本切换前的质量证据留存。

关键字段：

- `businessKey` / `sampleKey`：同一业务下的稳定样例标识。
- `imageUrl`：公网 HTTP(S) 图片 URL，管理端可先通过 OSS 直传填入。
- `prompt` / `generatedImageUrl` / `inputTags` / `defaultParams`：复跑时自动带入的提示词、对照图、标签和参数。
- `changeNote`：可选，写入样例版本历史。

错误：

- `BUSINESS_QUALITY_SAMPLE_BUSINESS_KEY_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_KEY_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID`
- `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID`
- `BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED`
- `BUSINESS_QUALITY_SAMPLE_NOT_FOUND`

### POST /api/admin/business/quality-samples/import

批量导入或更新固定质量样例。请求体支持 `businessKey` 作为默认业务，`items[]` 中每条仍可覆盖；服务端按 `businessKey + sampleKey` upsert，`dryRun=true` 只做预检查。

请求：

```json
{
  "businessKey": "fission",
  "dryRun": false,
  "changeNote": "运营批量导入",
  "items": [
    {
      "sampleKey": "dense-pattern-a",
      "label": "满版图案 A",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/...",
      "inputTags": ["满版图案"],
      "defaultParams": {"quality": "preview"}
    }
  ]
}
```

错误：

- `BUSINESS_QUALITY_SAMPLE_IMPORT_EMPTY`
- `BUSINESS_QUALITY_SAMPLE_IMPORT_LIMIT_EXCEEDED`
- `BUSINESS_QUALITY_SAMPLE_BUSINESS_KEY_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_KEY_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED`
- `BUSINESS_QUALITY_SAMPLE_LABEL_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_REQUIRED`
- `BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID`
- `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID`

### GET /api/admin/business/quality-samples/{sampleId}/versions

查询固定样例每次新增、更新、导入、归档时保存的快照，便于运营和研发追溯“换图/换参数”对出图效果的影响。

错误：

- `BUSINESS_QUALITY_SAMPLE_NOT_FOUND`

### GET /api/admin/business/output-reviews/export

导出业务输出质量复盘明细。主要用于固定样例同批对照复盘，可按 `batch_id` 精确导出某一批，也可按 `business_key` / `version` / `window_hours` 导出窗口内标注记录。

请求参数：

- `window_hours`：默认 `168`，范围 `1-2160`。
- `business_key`：可选，业务过滤。
- `version`：可选，版本过滤。
- `batch_id`：可选，固定样例复跑批次过滤。
- `limit`：默认 `5000`，范围 `1-10000`。

响应：`text/csv; charset=utf-8`，列包含 `batch_id`、业务、样例、runId、版本、质量档位、下一步动作、输入/问题标签、输出 URL、备注和标注人。

错误：

- `ADMIN_ONLY`
- `422` 参数范围校验失败

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
      "supportedApiTypes": ["image_generation", "image_edit"],
      "executionModes": ["sync_then_store"],
      "runtimeKeyConfigured": true,
      "keyCount": 1,
      "activeStoredKeyCount": 1,
      "disabledKeyCount": 0,
      "cooldownKeyCount": 0,
      "exhaustedKeyCount": 0,
      "errorKeyCount": 0,
      "uncheckedKeyCount": 0,
      "staleKeyCheckCount": 0,
      "failedKeyCheckCount": 0,
      "modelCount": 1,
      "activeModelCount": 1,
      "abilityCount": 2,
      "activeAbilityCount": 2,
      "succeededCalls": 12,
      "failedCalls": 0,
      "queuedCalls": 0,
      "runningCalls": 0,
      "issues": [],
      "suggestions": []
    }
  ],
  "issues": []
}
```

说明：

- `failedCalls` 只统计明确失败的调用；排队和运行中分别进入 `queuedCalls`、`runningCalls`，避免把正常排队误判为失败。
- `uncheckedKeyCount` / `staleKeyCheckCount` / `failedKeyCheckCount` 用于判断 active Key 是否从未验证、验证超过 7 天或最近验证失败。
- `issues` 会聚合密钥缺失、配额接近上限、密钥最近报错、Key 未验证/验证过期/验证失败、模型缺少计价、已有成功调用但未计价、任务排队/运行中/失败等治理风险。
- 该接口只做读侧汇总，不会主动调用第三方厂商，也不会消耗额度。

### GET /api/admin/vendor-api/models
返回 backend 当前沉淀的第三方模型目录视图，包括模型 ID、支持蒙版/多图/视频、执行模式、出网要求、路由策略与成本策略。接口会优先读取 `vendor_model_catalog`，目录为空时根据 vendor-api-ops Provider 信息写入一批默认模型。

响应中会附带模型上线门禁：

```json
{
  "items": [
    {
      "id": 1,
      "provider": "openai",
      "model": "gpt-image-2",
      "displayName": "OpenAI · GPT Image 2",
      "latestAcceptance": {
        "status": "passed",
        "note": "能力测试已跑通，OSS 回填正常",
        "createdAt": "2026-05-06T10:00:00Z"
      },
      "auditRecords": [
        {
          "action": "record_acceptance",
          "note": "能力测试已跑通，OSS 回填正常",
          "createdAt": "2026-05-06T10:00:00Z"
        }
      ],
      "releaseGate": {
        "status": "ready",
        "label": "生产可用",
        "canRelease": true,
        "acceptancePassed": true,
        "runtimeKeyConfigured": true,
        "egressVerified": true,
        "blockers": [],
        "warnings": [],
        "suggestions": [
          "基础门禁通过，可进入业务绑定和小流量验证。"
        ],
        "primaryIssue": null,
        "primaryActionLabel": "生产可用",
        "primaryAction": "基础门禁通过，可进入业务绑定和小流量验证。",
        "primarySeverity": "success"
      }
    }
  ]
}
```

门禁规则：

- 未启用、缺少模型验收、缺少可用密钥、所有密钥最近验证失败会进入 `blockers`。
- 缺少能力类型、返回方式、计价策略、密钥未验证/验证过期会进入 `warnings`。
- 对 `requiresGlobalEgress=true` 的模型，只有最近 7 天内存在一次 active Key 的带密钥出网验证成功，`egressVerified` 才为 true；否则会提示 `VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED`。
- `primaryIssue/primaryActionLabel/primaryAction/primarySeverity` 固定按“启用模型 -> 补密钥/验密钥 -> 查出网 -> 跑验收 -> 补计价”的业务顺序返回，避免在缺密钥时误提示先验收。
- 业务能力引用第三方模型时，会同步检查该模型是否有 `passed` 验收记录。

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
  "costPolicy": {
    "currency": "CNY",
    "billingUnit": "image",
    "unitPrice": 0.3,
    "quotaUnits": 1,
    "pricingVersion": "v1"
  },
  "metadata": { "outputFormats": ["png", "jpeg", "webp"] }
}
```

### PATCH /api/admin/vendor-api/models/{modelId}
更新模型目录项，可用于灰度启停、修改能力边界、补充输入 schema 或成本策略。

`costPolicy` 约定：

- `currency`：成本币种，如 `CNY`、`USD`
- `billingUnit`：计费单位，如 `run`、`image`、`video`、`second`、`token`
- `unitPrice`：单价，不能小于 0
- `quotaUnits`：平台套餐额度消耗，不能小于 0
- `quantityField`：可选，按返回/用量字段计算数量，例如 `output_count`
- `pricingVersion`：定价版本，便于后续调价追溯

后端会兼容 `unit_price/quota_units/pricing_version` 等蛇形字段，并统一归一为驼峰字段。

说明：

- 普通编辑 `metadata` 不会误删 `latestAcceptance`、`acceptanceRecords` 与 `modelAuditRecords`。
- 每次编辑会追加 `auditRecords`，用于管理端展示最近处理记录。

### POST /api/admin/vendor-api/models/bulk-action
批量处理模型目录项，用于上线前收口：批量启用/停用、批量记录验收、批量应用计价策略。每条成功处理的模型都会写入 `auditRecords`。

请求：

```json
{
  "modelIds": [1, 2, 3],
  "action": "record_acceptance",
  "note": "能力测试已跑通，结果回填正常",
  "acceptance": {
    "status": "passed",
    "note": "能力测试已跑通，结果回填正常",
    "metadata": {
      "source": "admin-model-catalog-bulk"
    }
  }
}
```

`action` 可选：

- `enable`：批量启用模型。
- `disable`：批量停用模型。
- `record_acceptance`：批量记录验收。
- `apply_cost_policy`：批量应用 `costPolicy`，仍会执行计价规则校验。

响应：

```json
{
  "action": "record_acceptance",
  "total": 3,
  "updated": 2,
  "failed": 1,
  "items": [
    {
      "modelId": 1,
      "success": true,
      "model": {
        "id": 1,
        "releaseGate": {
          "primaryActionLabel": "补密钥"
        }
      }
    },
    {
      "modelId": 999,
      "success": false,
      "error": "VENDOR_MODEL_NOT_FOUND"
    }
  ]
}
```

常见错误：

- `VENDOR_MODEL_BULK_ACTION_INVALID`
- `VENDOR_MODEL_BULK_MODEL_IDS_REQUIRED`
- `VENDOR_MODEL_COST_POLICY_INVALID`
- `VENDOR_MODEL_NOT_FOUND`

### POST /api/admin/vendor-api/models/{modelId}/acceptance-records
记录第三方模型验收结果。上线前常用 `status=passed`，用于说明该模型已经通过能力测试或测评端真实链路验证。

请求：

```json
{
  "status": "passed",
  "note": "能力测试已跑通，OSS 回填正常",
  "evidenceRunId": "run_vendor_test",
  "evidenceUrl": "https://example.com/evidence",
  "metadata": {
    "source": "admin-model-catalog"
  }
}
```

响应：返回更新后的模型目录项，包含 `latestAcceptance`、`acceptanceRecords` 与 `releaseGate`。

常见错误：

- `VENDOR_MODEL_NOT_FOUND`
- `VENDOR_MODEL_ACCEPTANCE_STATUS_INVALID`

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
- `VENDOR_API_KEY_QUOTA_EXHAUSTED`
- `VENDOR_API_KEY_QUOTA_NEAR_LIMIT`
- `VENDOR_API_KEY_RECENT_ERROR`
- `VENDOR_MODEL_COST_POLICY_MISSING`
- `VENDOR_API_UNCOSTED_SUCCESS_CALLS`
- `VENDOR_API_TASKS_QUEUED`
- `VENDOR_API_TASKS_RUNNING_LONG`
- `VENDOR_API_TASK_FAILURES`
- `VOLCENGINE_API_KEY_MISSING`
- `VOLCENGINE_MODEL_SYNC_HTTP_ERROR`
- `VOLCENGINE_MODEL_SYNC_RESPONSE_INVALID`
- `VOLCENGINE_MODEL_SYNC_DATA_INVALID`
- `VENDOR_MODEL_DUPLICATED`
- `VENDOR_MODEL_NOT_FOUND`
- `VENDOR_MODEL_INACTIVE`
- `VENDOR_MODEL_COST_POLICY_INVALID`
- `VENDOR_MODEL_ACCEPTANCE_STATUS_INVALID`
- `VENDOR_MODEL_ACCEPTANCE_REQUIRED`
- `VENDOR_MODEL_RUNTIME_KEY_MISSING`
- `VENDOR_MODEL_KEY_CHECK_FAILED`
- `VENDOR_MODEL_KEY_CHECK_PARTIAL_FAILED`
- `VENDOR_MODEL_KEY_NEVER_CHECKED`
- `VENDOR_MODEL_KEY_CHECK_STALE`
- `VENDOR_MODEL_API_TYPES_MISSING`
- `VENDOR_MODEL_EXECUTION_MODE_MISSING`
- `VENDOR_MODEL_COST_POLICY_MISSING`
- `VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED`

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

- 参数：`limit`（1-200）、`offset`、`search`、`callbackFailed`
- `search` 会查询能力名、能力标识、厂商、节点、任务编号、追踪编号、错误摘要、结果摘要等字段。
- `callbackFailed=true` 只返回回调失败、回调 HTTP 4xx/5xx、或存在回调错误信息的记录。

### GET /api/admin/abilities/logs

- 参数：`limit`、`offset`、`abilityId`、`provider`、`capabilityKey`、`status`、`source`、`templateId`、`templatePublished`、`search`、`callbackFailed`
- 管理端必须使用该接口的后端分页与筛选结果，不允许只在当前页做本地过滤，否则会误导排障。

### POST /api/admin/abilities/logs/{log_id}/resolve

- 仅对 ComfyUI 日志有效，用于补拉历史输出

### GET /api/admin/abilities/logs/export

- 导出 JSON/CSV
- 参数：`start` / `end` / `format`（`csv/json`），并支持与调用清单一致的 `provider`、`capabilityKey`、`status`、`source`、`search`、`callbackFailed` 等筛选。
- CSV 会展开 `output_summary` 为 `output_kind/output_image_count/output_video_count/output_text_count/output_structured_count/output_asset_count/output_primary_url/output_text_preview`，便于人工排障时直接判断是图片、视频、文字、结构化结果还是普通资源。

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
- 日志响应会额外返回 `output_summary`，用于区分图片、视频、文字、结构化结果和普通资源：`image_count/video_count/text_count/structured_count/asset_count/primary_kind/primary_url/text_preview/has_output`。
- 成功但暂无预览时，UI 文案应为“结果回填中”，避免误判为无结果。
- `response_payload` 建议统一使用公开响应结构（`abilityId/provider/status/images/videoUrls/texts/assets/metadata/...`），避免不同能力日志字段漂移。

---

## 8) 管理端仪表盘

### GET /api/admin/dashboard/metrics

- 汇总任务/评测/能力任务状态。
- 同时返回 `strategy_summary`，用于管理端首页展示近 24 小时业务调用、成功率、计费待处理、回调风险、成本与额度口径。
- `strategy_summary` 现在包含 `north_star` 与 `indicators`：前者是“成功业务交付”北极星，后者固定覆盖业务成功率、计费完整度、回调健康、扣费闭环、风险闭环 5 个 KPI。每个指标都返回 `status/detail/action`，管理端直接展示中文下一步动作。

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
    "north_star": {
      "key": "north_star",
      "title": "北极星：成功业务交付",
      "value": "10 次",
      "target": "持续增长，且不能靠失败或无回填堆量",
      "status": "warning",
      "detail": "有成功交付，但仍存在风险信号。",
      "action": "先处理失败、回调和计费风险，再扩大发版或接入流量。"
    },
    "indicators": [
      {
        "key": "business_success_rate",
        "title": "业务成功率",
        "value": "83%",
        "target": ">= 90%",
        "status": "warning",
        "detail": "统计窗口内业务调用 12 次，失败 2 次。",
        "action": "成功率低于目标时，先看业务调用详情里的五段链路判定。"
      }
    ],
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

用途：运行轻量发布门禁，不触发真实付费生图。当前检查项包括后端存活、Coze 工具箱文档、内部任务查询、ComfyUI 队列、测评目录、评测运行健康、三大核心业务默认版本治理、账号权限上线检查、周报/账单守护状态。

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

关键检查项：

- `business_capability_governance`：花纹提取、图裂变、扩图必须存在 active 默认版本，且默认版本要绑定主能力、可执行配方、可用第三方密钥；底层阻塞会直接阻断上线。
- `auth_scope_summary`：必须至少有一个 active 管理员；业务方账号、可用邀请码不能缺业务范围，过期邀请码不能继续激活；业务 API 权限边界和角色边界必须声明并已生效。
- `internal_tasks_get`：必须返回 `404 TASK_NOT_FOUND`，不能返回 `401 INTERNAL_ONLY`。
- `comfyui_queue_summary`：必须能看到 active ComfyUI 队列，节点不可达时需要先恢复或标记离线。

### GET /api/admin/dashboard/release-preflight/snapshots

- 参数：`limit`，默认 5。
- 返回最近发布门禁记录。

### GET /api/admin/comfyui/queue-summary

用途：读取所有启用的 ComfyUI 执行节点队列，并对比中台内部任务队列，用于判断 GPU 是否被充分利用、是否存在“中台执行中但 ComfyUI 队列不可见”、节点不可达等问题。

请求参数：

- `executorIds`：可重复传入，限制只检查指定执行节点；不传时检查所有 active 的 ComfyUI 节点。

响应重点字段：

- `totalRunning/totalPending/totalCount`：ComfyUI 侧实际运行、等待、总数。
- `totalCapacity/totalIdleSlots/utilization`：按执行节点并发上限计算的总容量、空闲槽位、利用率。
- `backendQueuedTotal/backendRunningTotal/backendActiveTotal`：中台内部待下发、执行中、总活跃任务数。
- `feedGapServers`：中台有待下发任务但 ComfyUI 仍有空闲容量的节点数。
- `backendBlockedServers`：中台显示执行中但 ComfyUI 队列为空的节点数。
- `routeEvidenceWindowHours/routeEvidenceTotal/routeEvidenceCoveredServers/recentRouteMissingServers`：近 24 小时真实任务命中统计，用于判断 158/233 是否都被路由到。
- `diagnostics[]`：面向运维的诊断项，可能包含 `COMFYUI_EXECUTOR_UNAVAILABLE`、`COMFYUI_BACKEND_RUNNING_NOT_VISIBLE`、`COMFYUI_FEED_GAP`、`COMFYUI_ROUTE_EVIDENCE_MISSING`、`COMFYUI_EXECUTOR_EMPTY`。
- `servers[]`：每台节点的名称、标签、队列、容量、中台任务、近 24 小时真实命中证据和诊断结果；前端应优先展示 `executorName/tags/baseUrl`，避免只用“117”这类模糊称呼。

错误与降级：

- 单台节点不可达时不让整个接口失败；该节点 `supported=false`，并写入 `message/diagnosis/feedDiagnosis`。
- 全部节点不可达时仍返回 200，`diagnostics[]` 标记阻塞原因，前端必须展示为业务风险。

### GET /api/admin/comfyui/workflow-compatibility

用途：检查 active 的 ComfyUI 能力在当前路由机器上是否缺节点、缺模型或路由配置不一致。该接口不提交真实任务、不消耗出图额度，用于上线前和日常巡检。

请求参数：

- `executorIds`：可重复传入，限制只检查指定执行节点；不传时检查所有 active 的 ComfyUI 节点。

响应重点字段：

- `okCount/warningCount/failedCount`：能力对齐结论，`failedCount>0` 视为上线阻断。
- `servers[]`：每台执行节点的 `/object_info` 读取状态。
- `workflows[].expectedExecutorIds`：该能力应参与路由的机器。
- `workflows[].compatibleExecutorIds`：实际依赖完整的机器。
- `workflows[].servers[].missingNodes/missingModels`：缺失的自定义节点和模型文件。

错误与降级：

- 单台节点不可达不会让接口整体失败；该节点会进入 `reachable=false`。
- 工作流图缺失或没有可检查执行节点时，workflow `status=failed`，发版前必须补齐配置。
- 可能涉及错误码：`COMFYUI_BASE_URL_MISSING`、`COMFYUI_OBJECT_INFO_ERROR`、`COMFYUI_OBJECT_INFO_INVALID`、`COMFYUI_WORKFLOW_GRAPH_MISSING`、`COMFYUI_NO_ROUTED_EXECUTOR`、`COMFYUI_ROUTING_BINDING_MISMATCH`。

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

### GET /api/admin/dashboard/health-watch/status

用途：读取线上自检守护状态，用于管理端总览页确认定时巡检是否真的在运行。接口只读取固定白名单 systemd 单元，不接受前端传入 unit 名称或命令。

请求：无请求体。

响应示例：

```json
{
  "generatedAt": "2026-05-03T00:42:10Z",
  "supported": true,
  "items": [
    {
      "unit": "podi-business-health-watch.timer",
      "title": "业务轻量自检定时器",
      "kind": "timer",
      "status": "healthy",
      "summary": "定时器运行中，下次触发：2026-05-03 08:51:32 CST。",
      "loadState": "loaded",
      "activeState": "active",
      "subState": "waiting",
      "unitFileState": "enabled",
      "result": "success",
      "execMainStatus": 0,
      "lastTrigger": "2026-05-03 08:36:02 CST",
      "nextElapse": "2026-05-03 08:51:32 CST",
      "recentLogs": []
    }
  ],
  "issues": []
}
```

字段说明：

- `supported`：当前后端运行环境是否能读取 systemd。线上 114 应为 `true`；本地开发环境可能为 `false`。
- `items[].status`：`healthy/running/failed/disabled/unavailable/unknown`。
- `items[].kind`：`timer` 表示定时器，`service` 表示最近一次执行。
- `issues`：需要人工处理的问题摘要。注意：定时器未安装、未启用或最近执行失败都会进入 `issues`，但接口本身仍返回 200。

错误：

- 认证失败沿用管理端统一认证错误。
- systemd 不可用、unit 未安装、unit 执行失败不会作为 HTTP 错误抛出，而是写入 `items[].status` 与 `issues`，避免页面因为守护异常整体白屏。

### POST /api/admin/dashboard/release-decisions/records

用途：登记本次发版结论。该接口不执行部署，只把“可发版 / 暂缓 / 阻塞”的人工判断和当时的门禁、巡检摘要落成记录，便于复盘。

请求：

```json
{
  "status": "approved",
  "title": "确认可发版：可以发版",
  "preflightId": "preflight_xxx",
  "patrolId": "patrol_xxx",
  "note": "轻量门禁、完整巡检和能力状态均已确认",
  "summary": {
    "readinessTitle": "可以发版",
    "blockers": [],
    "warnings": []
  }
}
```

字段说明：

- `status`：`approved/deferred/blocked`，分别表示确认可发版、暂缓发版、阻塞发版。
- `preflightId`：最近轻量门禁记录 ID，可为空。
- `patrolId`：最近完整巡检记录 ID，可为空。
- `summary`：记录当时页面展示的阻塞项、提醒项和结论摘要。

### GET /api/admin/dashboard/release-decisions/records

- 参数：`limit`，默认 5。
- 返回最近发版结论登记。

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
