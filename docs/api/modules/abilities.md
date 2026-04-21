# 统一能力调用接口

## 用途

- 对外统一暴露“能力清单 + 调用 + 异步任务”。
- 前端/业务系统仅需对接这一套接口。

## 鉴权

- **读取清单**：`GET /api/abilities` 无需登录。
- **调用/任务**：需 `Authorization: Bearer <accessToken>`，或使用 `SERVICE_API_TOKEN`。

---

## 1) 能力清单

### GET /api/abilities

**用途**：返回所有已激活能力的基础信息、默认参数与输入 schema。

**新增口径**

- `businessStatus`：业务可见状态，不暴露中台内部治理术语。
  - `availabilityCode/availabilityLabel`：`available/可用`、`testing/测试中`、`unavailable/暂不可用`
  - `stabilityCode/stabilityLabel`：`stable/稳定`、`optimizing/优化中`、`experimental/实验性`
- `businessPresentation`：业务可见的简化展示层，不要求业务理解中台内部概念。
  - `visible`：是否建议在业务列表中展示
  - `sortOrder`：排序值，数值越小越靠前
  - `categoryLabel`：给业务看的分类名称
  - `usageHint`：一句话使用提示
  - `operationLabel`：一句话动作名称（如“图像扩展”“抠图”“图像裂变”）
- `metadata.governance`：中台内部治理真源，给管理端/内部配置使用，不建议直接面向业务透出。
  - `scopes`：`internal/admin/eval/coze/client`
  - `release_status`：`draft/internal_ready/eval_ready/published/deprecated`
  - `route_policy`：`fixed/queue_aware/fallback_allowed`
  - `quality_status`：`untested/usable/needs_optimization`
- `metadata.routing`：中台路由真源，给调度层和管理端使用。
  - `selection_policy`：`auto/fixed/queue/weight/round_robin`
  - `required_executor_tags`
  - `allowed_executor_ids`
  - `fallback_to_default`
  - `action`
  - `workflow_key`

**响应示例**

```json
{
  "items": [
    {
      "id": "comfyui_yinhua_tiqu",
      "provider": "comfyui",
      "category": "image_generation",
      "capabilityKey": "yinhua_tiqu",
      "version": "v1",
      "displayName": "ComfyUI · 印花提取",
      "description": "Qwen Image Edit + 印花 LoRA",
      "status": "active",
      "abilityType": "comfyui",
      "workflowId": "workflow_comfyui_pattern_extract_v1",
      "executorId": "executor_comfyui_pattern_extract_158",
      "defaultParams": {
        "workflow_key": "yinhua_tiqu",
        "timeout": 420,
        "output_width": 1800,
        "output_height": 1800,
        "lora_name": "杯子1124.safetensors"
      },
      "inputSchema": { "fields": [] },
      "metadata": {
        "api_type": "comfyui_workflow",
        "requires_image_input": true,
        "routing": {
          "selection_policy": "queue",
          "required_executor_tags": ["pattern_extract"],
          "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
          "fallback_to_default": true,
          "action": "generic",
          "workflow_key": "yinhua_tiqu"
        },
        "governance": {
          "scopes": ["admin", "eval", "coze"],
          "release_status": "published",
          "route_policy": "queue_aware",
          "quality_status": "usable"
        }
      },
      "businessStatus": {
        "availabilityCode": "available",
        "availabilityLabel": "可用",
        "stabilityCode": "stable",
        "stabilityLabel": "稳定",
        "surfaceLabels": ["管理端", "测评端", "Coze"]
      },
      "businessPresentation": {
        "visible": true,
        "sortOrder": 200,
        "categoryLabel": "图片生成",
        "usageHint": "适合在 Coze 工作流中作为图像节点使用",
        "operationLabel": "图案提取"
      },
      "requiresImage": true,
      "supportsMultipleImages": false,
      "maxOutputImages": null
    }
  ]
}
```

### GET /api/abilities/{abilityId}

**用途**：获取单个能力详情。

---

## 2) 能力调用

### POST /api/abilities/{abilityId}/invoke

**用途**：调用指定能力并返回结果（同步）。

**请求体**

```json
{
  "executorId": "可选，覆盖能力默认节点",
  "inputs": {
    "prompt": "春日田野风景，布面油画风格",
    "output_width": 1024,
    "output_height": 1024
  },
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png",
  "imageBase64": null,
  "images": [
    { "name": "ref-1", "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/ref1.png" }
  ],
  "metadata": {
    "requestFrom": "podi-eval-web",
    "traceId": "trace-001"
  },
  "callbackUrl": "https://example.com/webhook",
  "callbackHeaders": { "Authorization": "Bearer xxx" }
}
```

**响应体**

```json
{
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "status": "succeeded",
  "requestId": "req_7d0f...",
  "logId": 12345,
  "durationMs": 842,
  "images": [
    { "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png", "type": "image" }
  ],
  "assets": [
    { "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png", "tag": "comfyui-image" }
  ],
  "metadata": {
    "taskId": "prompt-87c5c0..."
  },
  "raw": {
    "...": "原始返回（已脱敏）"
  }
}
```

**错误（常见）**

- `ABILITY_NOT_FOUND` / `ABILITY_INACTIVE`
- `ABILITY_EXECUTOR_NOT_CONFIGURED`
- `EXECUTOR_NOT_FOUND` / `EXECUTOR_TYPE_NOT_*`
- `IMAGE_REQUIRED` / `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT` / `KIE_TIMEOUT`

---

## 3) 能力选项（公共）

### GET /api/abilities/options

**用途**：获取能力选项（供前端动态表单使用）。

**请求参数**

- `status`：默认 `active`
- `provider`：可选（如 `comfyui` / `volcengine` / `kie`）

**说明**

- 公共 options 也会返回 `business_status`、`presentation` 与 `governance`。
- 业务前端应优先使用：
  - `business_status` 渲染“可用性/稳定度”
  - `presentation.category_label / usage_hint / operation_label` 渲染列表与引导文案
- 管理端或内部平台可读取 `governance` 做分层、发布判断，并读取 `metadata.routing` 做路由判断。

---

## 4) 异步任务

### POST /api/ability-tasks

**用途**：提交异步任务（与 invoke 参数一致，额外带 abilityId）。

**请求体**

```json
{
  "abilityId": "comfyui_yinhua_tiqu",
  "inputs": { "prompt": "印花提取" },
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png"
}
```

**响应体**

```json
{
  "id": "f61f2dd0f7dd4f479e7d97f6b0fa0f8b",
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "status": "queued",
  "logId": 12345,
  "createdAt": "2026-02-09T10:00:00Z"
}
```

### GET /api/ability-tasks

**用途**：查询最近任务列表（默认 20 条）。

**参数**：`limit`（1-200）

### GET /api/ability-tasks/{taskId}

**用途**：查询单个任务状态与结果。

**响应体**（状态字段）

- `status`：`queued` / `running` / `succeeded` / `failed`
- `submitStatus`：`pending/submitting/submit_failed/submitted`
- `callbackStatus`：`waiting/running/success/failed/not_configured`
- `finalStatus`：`pending/running/success/failed/canceled`
- `errorCode`：标准错误码（可为空）
- `resultPayload`：成功结果（含图片/视频/文本）
- `errorMessage`：失败原因

**一致性说明**

- `AbilityTask.status` 与“能力调用日志 status”不是同一维度：
  - AbilityTask：`queued/running/succeeded/failed/cancelled`
  - Ability Log：`pending/success/failed`
- 前端显示必须按统一映射渲染，避免把 `success` 与 `succeeded` 误判为不同结果。
- 结果预览读取顺序统一见：`docs/standards/interface-consistency.md`。

**错误**

- `TASK_NOT_FOUND`

---

## 6) 管理端能力模板（新增）

> 以下接口均为管理员接口（`/api/admin/abilities/*`），用于“能力配置模板化”，不影响线上调用链路。
> 管理端入口：`能力目录` 列表可查看模板状态；`能力详情/测试 -> 元信息` 中可执行校验/发布/回滚。

### GET /api/admin/abilities/{ability_id}/template

用途：查看模板当前版本与历史快照。

### POST /api/admin/abilities/{ability_id}/template/validate

用途：校验模板结构（参数/schema/metadata），返回错误与警告。

### POST /api/admin/abilities/{ability_id}/template/publish

用途：把当前能力配置固化为模板快照并设为当前版本（可用于回滚基线）。

### POST /api/admin/abilities/{ability_id}/template/rollback

用途：按 `templateId` 回滚能力配置（`default_params/input_schema/metadata`）。

**错误（新增）**

- `ABILITY_TEMPLATE_INVALID`
- `ABILITY_TEMPLATE_NOT_FOUND`

### GET /api/admin/abilities/logs（补充）

用途：查看全局能力调用清单（管理端“能力调用”页）。

新增筛选参数：

- `templateId`：按“能力当前模板版本 ID”筛选
- `templatePublished`：按模板发布状态筛选（`true/false`）

返回新增字段：

- `abilityCurrentTemplateId`：能力当前模板版本 ID（可为空）
- `abilityTemplateHistoryCount`：模板历史快照数量
- `abilityTemplatePublished`：是否已发布模板

### GET /api/admin/abilities/logs/export（补充）

用途：导出全局能力调用清单（CSV/JSON）。

新增筛选参数与 `/api/admin/abilities/logs` 一致：

- `templateId`
- `templatePublished`

CSV 新增列：

- `ability_current_template_id`
- `ability_template_history_count`
- `ability_template_published`

---

## 5) 回调（可选）

当 `callbackUrl` 被提供时，服务端会在任务完成/失败后 POST 回调。示例：

```json
{
  "status": "success",
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "requestId": "req_7d0f...",
  "logId": 12345,
  "durationMs": 842,
  "result": { "images": ["..."] },
  "error": null,
  "timestamp": "2026-02-09T10:02:01Z"
}
```
