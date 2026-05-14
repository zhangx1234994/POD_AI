# 业务能力接口

## 用途

业务能力接口是给业务方、Coze、客户端、MCP/技能复用的稳定入口。
第一阶段开放三个核心业务：花纹提取、图裂变、扩图；底层仍复用统一能力任务和 ComfyUI workflow，但对外不暴露节点、workflow、executor 等实现细节。

核心约定：

- 对外统一是 `提交业务任务 -> 返回 runId -> 轮询结果`。
- `runId` 是业务任务 ID，业务方只需要保存它。
- `taskId` 是底层能力任务 ID，仅用于排查和链路关联，不要求业务方理解。
- 业务版本由中台切默认版本；Coze 工具箱和业务方入参尽量保持不变。
- 图裂变 2026-05-12 交付的两个裂变版本和裂变评分接口，统一参考 `docs/api/examples/fission-delivery-contract-2026-05-12.md`；其中包含类图、队列/轮询兼容关系和参数聚合规则。

## 鉴权

- 业务方推荐使用 `X-PODI-API-Key: <业务 API Key>`。中台会记录 Key、业务、runId、状态码和耗时，作为后续计费、配额和排障基础。
- 兼容 `Authorization: Bearer <业务 API Key>`；系统巡检和 Coze 内部调用仍可使用 `Authorization: Bearer <SERVICE_API_TOKEN>`。
- Coze 同机/可信内网调用可通过 `COZE_TRUSTED_IPS` 或内网地址放行。
- 管理端业务能力接口仍要求管理员权限。
- 业务方登录账号调用时，只能使用账号绑定的 `tenantId/clientId`。如果传入其他业务方范围，会返回 `BUSINESS_USER_SCOPE_FORBIDDEN`；如果业务方账号没有绑定 `tenantId`，会返回 `BUSINESS_USER_SCOPE_REQUIRED`。
- 管理员和服务 Token 可显式指定 `tenantId/clientId`，用于 Coze 工具箱、巡检脚本和后台代业务方提交。
- 当前 API Key 先做身份识别和审计，不强制限流；业务方并发、日次数和额度限制仍优先走业务方配置。

---

## 0) 业务方快速接入口径

业务方只需要理解三件事：

1. 提交任务后保存 `runId`。
2. 用 `runId` 轮询 `/api/business/runs/get`。
3. Coze/内网工具箱兼容场景下，也可以把 `runId` 填到旧轮询接口 `/api/coze/podi/tasks/get` 的 `taskId` 字段。
4. 终态优先看 `status/taskStatus/imageUrls/videoUrls/texts/error`。默认查询结果保持轻量，结构化评分会在无图片输出时返回轻量 `resultPayload`；需要 `routeInfo/steps/flowSummary` 等排障字段时，查询接口传 `detail=full`。

这条链路不要求业务方传 Coze 工作流 ID。Coze 可以继续作为接入入口，但业务 API 本身已经能完成“提交任务 -> 查询结果”的闭环；灰度或默认版本命中可先用 `route-preview` 验证。

当前对外业务入口：

| 业务 | 提交接口 | 必填字段 | 常用可调字段 | 终态输出 | 业务说明 |
| --- | --- | --- | --- | --- | --- |
| 花纹提取 | `POST /api/business/pattern-extract/runs` | `imageUrl` | `prompt`、`negative_prompt`、`width`、`height`、`batch`、`lora` | `imageUrls` | 从原图中提取可复用花纹资产，通常是后续裂变和扩图的上游。 |
| 图裂变 | `POST /api/business/fission/runs` | `imageUrl` | ComfyUI 颜色锁定版：`bili`(`15%`，建议 0%-20%)、`width`、`height`、`profile`；GPT Image 2 版：`variation_strength`、`quality`、`size`、`maskUrl`；历史 ComfyUI 版本仍兼容 `prompt/image_desc/batch_size/steps/cfg` | `imageUrls` | 基于原图生成变化图；版本可在中台切换，业务方仍调用同一个入口。`bili` 是重绘幅度/裂变幅度，越高变化越明显。 |
| 裂变生成图评估 | `POST /api/business/fission-evaluate/runs` | `originalImageUrl`、`generatedImageUrl` | `context` | `texts/resultPayload` | 输入原图和裂变结果图，判断是否通过、是否建议二次裂变；只评分，不自动二次裂变。 |
| 扩图 | `POST /api/business/outpaint/runs` | `imageUrl` | `prompt`、`expand_left`、`expand_right`、`expand_top`、`expand_bottom`、`width`、`height` | `imageUrls` | 在原图四周扩展画面，适合补构图、补背景和素材延展。 |

### 0.1) 最小调用示例

业务方拿到 `X-PODI-API-Key` 后，可以直接按下面两步接入。示例中的 Key 是占位符，不要把真实 Key 写入仓库或公开文档。

提交图裂变：

```bash
curl -X POST "$PODI_BACKEND/api/business/fission/runs" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "imageUrl": "https://example.com/input.png",
    "prompt": "保持主体结构，生成同系列变化图",
    "source": "partner-api",
    "channel": "open-api",
    "traceId": "biz_trace_001",
    "callbackUrl": "https://your-service.example.com/podi/callback"
  }'
```

查询结果：

```bash
curl -X POST "$PODI_BACKEND/api/business/runs/get" \
  -H "X-PODI-API-Key: $PODI_BUSINESS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "runId": "提交接口返回的 runId"
  }'
```

管理员开通业务 Key：

```bash
curl -X POST "$PODI_BACKEND/api/admin/business/api-keys" \
  -H "Authorization: Bearer $PODI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "业务方 A · 开放接口",
    "key": "podi_live_xxx",
    "status": "active",
    "tenantId": "tenant-a",
    "clientId": "open-api",
    "allowedBusinessKeys": ["fission", "fission_evaluate", "outpaint", "pattern_extract"],
    "expireAt": "2026-12-31T23:59:59+08:00"
  }'
```

管理端“API 开放”页也可以直接生成、创建、停用业务 Key，并查看每个 Key 的调用记录。

通用追踪字段：

- `source`：调用来源，例如 `coze`、`client`、`partner-api`。
- `channel`：具体入口，例如 `coze-workflow`、`open-api`、`eval`。
- `traceId`：跨系统排查 ID，建议业务方生成并传入。
- `requestId`：业务方请求 ID，后续用于幂等和日志关联。
- `tenantId/clientId`：租户和客户端标识，用于灰度、配额、统计和隔离。
- `userId`：业务方自己的用户标识，只作为外部上下文和排查字段保留；不会直接写入平台用户外键，也不会替代平台登录用户。
- `callbackUrl`：可选。配置后任务终态会回调业务方；即使回调失败，业务方仍可用 `runId` 查询结果。

状态约定：

- `queued/running`：任务还在排队或执行，业务方继续轮询。
- `succeeded`：任务成功，读取 `imageUrls/videoUrls/texts`；结构化评分优先读取 `texts` 或轻量 `resultPayload`，完整链路证据用 `detail=full` 查询。
- `failed/cancelled/timeout`：任务不可继续，读取 `error/errorMessage` 并按错误码处理。

### 0.2) 与管理端 API 开放页对齐

管理端“API 开放”页展示的业务接口必须和本文档保持一致：

| 页面名称 | 接口 | 文档位置 | 必填/核心字段 | 冒烟口径 |
| --- | --- | --- | --- | --- |
| 业务 OpenAPI | `GET /api/business/openapi.json` | 8) OpenAPI 工具箱 | 无 | 返回 200，且包含业务提交、路由预览、任务查询工具。 |
| 花纹提取 | `POST /api/business/pattern-extract/runs` | 2) 提交花纹提取 | `imageUrl` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 图裂变 | `POST /api/business/fission/runs` | 3) 提交图裂变 | `imageUrl` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 裂变生成图评估 | `POST /api/business/fission-evaluate/runs` | 4) 提交裂变生成图评估 | `originalImageUrl`、`generatedImageUrl` | 真实提交必须确认 `runId/status/texts/resultPayload`。 |
| 扩图 | `POST /api/business/outpaint/runs` | 5) 提交扩图 | `imageUrl` | 可先用 route-preview 验证版本命中；真实出图必须确认 `runId/status/imageUrls`。 |
| 查询业务任务 | `POST /api/business/runs/get` | 6) 查询业务任务 | `runId` | 使用不存在的 `runId` 时应返回 `BUSINESS_RUN_NOT_FOUND` 或等价 404，不应返回 500。 |

维护规则：

- 页面新增业务接口时，本文档必须同步新增请求、响应和错误说明。
- 本文档新增业务接口时，管理端“API 开放”页必须同步露出或说明暂不露出的原因。
- 业务方默认只需要使用提交接口和查询接口；路由预览属于上线、灰度和排障工具。

### 0.3) 业务 API 错误处理口径

| 场景 | 常见错误码 | 业务方动作 | 平台动作 |
| --- | --- | --- | --- |
| 缺少主图或 runId | `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_RUN_ID_REQUIRED` | 修正入参后重新提交，不建议自动重试。 | 前端表单必须提前提示必填项。 |
| 鉴权或业务方范围不允许 | `AUTHORIZATION_REQUIRED`、`BUSINESS_USER_SCOPE_REQUIRED`、`BUSINESS_USER_SCOPE_FORBIDDEN` | 检查 Token、账号绑定的业务方范围或接入配置。 | 管理端账号权限页和业务方配置页给出中文处理建议。 |
| 业务版本或配方不可用 | `BUSINESS_CAPABILITY_NOT_FOUND`、`BUSINESS_RECIPE_INVALID`、`BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE` | 暂停调用该业务版本，保留 `traceId/requestId` 给平台排查。 | 检查默认版本、配方步骤、能力启停、模型门禁和回滚版本。 |
| 业务方额度或并发限制 | `BUSINESS_CLIENT_DISABLED`、`BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`、`BUSINESS_CLIENT_CONCURRENCY_LIMITED`、`BUSINESS_CLIENT_DAILY_RUN_LIMITED`、`BUSINESS_CLIENT_DAILY_QUOTA_LIMITED` | 不要高频重试；等并发释放或联系平台调整策略。 | 管理端业务方配置页必须能看到限制来源。 |
| 执行节点、队列或上游失败 | `COMFYUI_IMAGE_REQUIRED`、`COMFYUI_TIMEOUT`、`ABILITY_TASK_FAILED`、`VENDOR_API_EXECUTION_FAILED` | 可按业务策略稍后重试一次；连续失败时保留 `runId/taskId` 排查。 | 检查执行节点健康、队列、模型 Key、出网、OSS 回填和能力调用日志。 |
| 查询不到任务 | `BUSINESS_RUN_NOT_FOUND`、`BUSINESS_RUN_FORBIDDEN` | 确认 `runId` 是否属于当前业务方，不要把底层 `taskId` 当 `runId` 使用。 | 排查租户隔离、任务写入和历史数据迁移。 |
| 查询临时不可用 | `BUSINESS_RUN_TEMPORARY_UNAVAILABLE` | 稍后重试查询，不需要重新提交任务；持续出现时把 `runId/traceId` 发给平台。 | 检查数据库、索引、连接池和业务步骤查询链路，禁止把 SQL 原文返回给业务方。 |

---

## 1) 业务能力清单

### GET /api/business/capabilities

用途：返回当前可用业务能力版本、发布时间、默认状态和底层配方。

响应示例：

```json
{
  "items": [
    {
      "id": "biz_fission_v1_flux_strong_hq_softstyle",
      "businessKey": "fission",
      "version": "v1",
      "displayName": "图裂变 · FLUX Strong HQ Softstyle",
      "status": "active",
      "isDefault": true,
      "releaseTime": "2026-04-24T00:00:00",
      "recipe": {
        "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission"
      },
      "inputSchema": { "fields": [] },
      "metadata": { "entry": "business-api", "seed_version": 1 },
      "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission",
      "primaryAbilityName": "图裂变 · 高质量多元素花纹",
      "vendorModelId": null,
      "vendorModelName": null,
      "recipeSteps": [
        {
          "order": 1,
          "id": "primary",
          "type": "ability_task",
          "role": "primary",
          "enabled": true,
          "abilityId": "comfyui_flux_strong_hq_softstyle_fission",
          "abilityName": "图裂变 · 高质量多元素花纹",
          "abilityProvider": "comfyui"
        }
      ]
    }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`

---

## 1.1) 业务配方结构

业务配方用于描述一个业务版本背后调用哪些原子能力。第一阶段已经支持配置校验、前端摘要展示、运行步骤记录，以及 VL 辅助步骤的真实提交和状态追踪。

执行边界：

- `primaryAbilityId` 对应的主能力仍是出图真源，决定业务任务的最终 `status/imageUrls/error`。
- `vlAssist.enabled=true` 时，业务层会把 VL 步骤作为伴随任务提交并记录在 `steps` 中。
- 默认模式下，VL 不阻塞主能力，适合先做观测和结果积累。
- 如果配方设置 `mode=vl_then_primary`，或设置 `vlAssist.waitForResult=true` / `vlAssist.applyToPrimary=true`，业务层会先提交 VL，等 VL 成功后再提交主能力。
- 阻塞式 VL 串联默认会把 `promptCard.imageDesc` 回填到图裂变 `image_desc`，把 `promptCard.positivePrompt` 回填到花纹提取/图裂变/扩图 `prompt`；只有原请求未填写这些字段时才自动回填。
- GPT Image 2 图裂变新版使用专用编译器：VL 输出 `vlCard` 后，中台会编译成英文图片编辑提示词，并映射 `quality/size/output_format/n=1` 等 OpenAI 参数；业务方不用理解 VL 卡片和模型参数。该业务版固定一个请求生成一张图，需要多张时由业务方发起多次请求，分别获得多个 `runId`。
- ComfyUI VL 控制卡裂变新版使用 `vl_fission_control_card` 作为统一 VL 组件，输出 `fissionControlCard` 后再传给 `comfyui_flux_strong_hq_softstyle_fission_control_v1`；后续更换 VL 模型时优先改这个组件的默认 provider。
- ComfyUI 颜色锁定裂变版使用版本 `comfyui-vl-control-v2`，主能力为 `comfyui_flux_strong_hq_softstyle_fission_colorlock_v2`。VL 输出必须包含 `palette_card`，中台会把颜色卡和硬负向约束拼进 `image_desc`。`denoise` 不写死，继续按 `bili` 约定映射；其他颜色锁定强度按交付包固定。
- 裂变生成图评估底层仍是原子能力 `vl_fission_generated_image_evaluate`，但已经提供业务包装入口 `/api/business/fission-evaluate/runs`。它只输出 `pass / needs_refission / reject` 和问题标签，不在业务层自动二次裂变；业务方可按自己的策略决定是否再次调用图裂变。

推荐结构：

```json
{
  "mode": "pipeline",
  "primaryAbilityId": "ability_openai_fission",
  "vlAssist": {
    "enabled": true,
    "abilityId": "vl_analyze_image"
  },
  "steps": [
    {
      "id": "vl",
      "type": "vl_analyze",
      "role": "preprocess",
      "abilityId": "vl_analyze_image"
    },
    {
      "id": "primary",
      "type": "ability_task",
      "role": "primary",
      "abilityId": "ability_openai_fission"
    }
  ]
}
```

阻塞式串联结构：

```json
{
  "mode": "vl_then_primary",
  "primaryAbilityId": "ability_openai_fission",
  "vlAssist": {
    "enabled": true,
    "abilityId": "vl_analyze_image",
    "waitForResult": true,
    "applyToPrimary": true
  },
  "steps": [
    {
      "id": "vl",
      "type": "vl_analyze",
      "role": "preprocess",
      "abilityId": "vl_analyze_image"
    },
    {
      "id": "primary",
      "type": "ability_task",
      "role": "primary",
      "abilityId": "ability_openai_fission"
    }
  ]
}
```

校验规则：

- `primaryAbilityId` 必须指向存在的原子能力。
- `steps` 中启用的执行步骤必须配置 `abilityId`，且能力必须存在。
- `vlAssist.enabled=true` 时默认使用 `vl_analyze_image`，也可以显式指定其他 VL 能力；提交业务任务时可在 `inputs.vl_provider`、`inputs.coze_workflow_id`、`inputs.vl_prompt` 覆盖 VL 来源和分析要求。
- 阻塞式 VL 串联中，VL 失败时主能力不会提交，业务任务直接进入 `failed`，错误会保留在 `steps[0].error` 和业务任务 `error` 中。
- 未知步骤类型会被拒绝，避免把不可执行配置带到线上。

管理端已提供“VL 前置分析”开关和能力选择框；普通运营只需要切换表单，不需要直接编辑 JSON。

---

## 2) 提交花纹提取

### POST /api/business/pattern-extract/runs

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "prompt": "提取主体花纹，保留清晰边缘和面料纹理",
  "negative_prompt": "不要背景、不要阴影、不要文字水印",
  "width": 1800,
  "height": 1800,
  "batch": 1,
  "lora": "杯子1124.safetensors",
  "source": "coze",
  "channel": "coze-workflow",
  "traceId": "trace-pattern-001",
  "requestId": "req-pattern-001",
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "metadata": {
    "grayKey": "tenant-a"
  }
}
```

响应体同图裂变。

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `prompt/negative_prompt/width/height/batch/lora/timeout` 直接作为顶层字段传入。
- 旧调用仍兼容把同名参数放在 `inputs` 内。
- LoRA 为空时使用当前默认业务版本内置配置；切换默认版本由中台完成，业务方不需要替换底层 workflow。

---

## 3) 提交图裂变

### POST /api/business/fission/runs

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "prompt": "保持原始花型主体，生成更适合服装面料的变体",
  "version": null,
  "bili": 65,
  "width": 1024,
  "height": 1024,
  "image_desc": "蓝白色植物纹样，中心构图",
  "source": "coze",
  "channel": "coze-workflow",
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "inputs": {
    "兼容说明": "旧调用仍可继续把参数放在 inputs 内；新调用建议使用顶层字段"
  },
  "callbackUrl": "https://example.com/podi/callback",
  "metadata": {
    "source": "coze",
    "traceId": "trace-demo-001",
    "grayKey": "tenant-a"
  }
}
```

`bili` 口径：

- 所有图裂变业务入口里的 `bili` 都按“重绘幅度/裂变幅度”理解，0-100，值越大变化越明显。
- 后端按既定比例换算到 ComfyUI `denoise`：低值更保守，高值重绘更强；例如 `50%` 是中等幅度。
- GPT Image 2 受控版不使用 `bili`，使用 `variation_strength` 控制变化幅度；默认 `same_series`，固定一次请求生成 1 张图。

GPT Image 2 受控版请求示例：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "version": "gpt-image2-vl-v2",
  "variation_strength": "same_series",
  "quality": "preview",
  "prompt": "保留系列感，元素要明显变化",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-gpt-image2-001"
}
```

说明：该版本会先调用 `vl_analyze_image` 生成客观识别卡，再由中台归一化图案类型、编译定量提示词，最后调用 `openai_gpt_image_2_edit`。`quality=preview/candidate/premium` 会分别映射为 OpenAI 的 `low/medium/high`。`size` 不传或传 `auto` 时，中台按原图尺寸回填最终 OSS 图片；只有业务方明确传固定尺寸（如 `1024x1024`、`1536x1024`）时才改变输出画布。当前业务交付口径固定单次输出 1 张图；如果业务需要 3 张图，请提交 3 次，每次有独立 `runId`、轮询结果和回调。

ComfyUI 颜色锁定版请求示例：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "version": "comfyui-vl-control-v2",
  "bili": "15%",
  "width": 2000,
  "height": 2000,
  "profile": "pattern_color_lock_v2",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-comfyui-vl-001"
}
```

响应体：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "fission",
  "version": "v1",
  "status": "queued",
  "taskStatus": "queued",
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "taskId": "t1.fission.default.xxx",
  "retryAfterSeconds": 10,
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugUrl": null
}
```

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_REQUEST_PAYLOAD_INVALID`
- `BUSINESS_VL_PREPROCESS_FAILED`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `BUSINESS_API_KEY_INACTIVE`
- `BUSINESS_API_KEY_EXPIRED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`
- `ABILITY_TASK_FAILED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `bili/width/height/profile/prompt` 等业务字段直接作为顶层字段传入，业务方不用理解 `inputs`；`batch_size/steps/cfg` 仅作为旧 ComfyUI 版本兼容字段保留。`bili` 统一按重绘幅度理解。
- 旧调用仍兼容 `inputs.bili`、`inputs.width` 等格式；顶层字段不会破坏现有 Coze 工作流。
- 提交接口默认只返回轻量回执，业务方保存 `runId` 后调用 `/api/business/runs/get` 轮询结果；底层路由、步骤、成本、排障证据不在提交阶段返回。
- `traceId/requestId/tenantId/clientId/channel/source` 会进入业务运行记录，并继续透传到底层能力任务，后续用于排查、灰度、成本和配额统计。

---

## 4) 提交裂变生成图评估

### POST /api/business/fission-evaluate/runs

请求体：

```json
{
  "originalImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/original.png",
  "generatedImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/generated.png",
  "context": {
    "business": "fission",
    "version": "gpt-image2-vl-v2",
    "prompt": "保持原图系列感，生成同系列变化图",
    "bili": "15%"
  },
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-fission-eval-001",
  "requestId": "req-fission-eval-001"
}
```

响应体：

```json
{
  "id": "a0e199ae4b0d476a8294e1ee91bbebda",
  "runId": "a0e199ae4b0d476a8294e1ee91bbebda",
  "businessKey": "fission_evaluate",
  "version": "v1",
  "status": "queued",
  "taskId": "t1.fission_evaluate.default.xxx",
  "imageUrls": [],
  "texts": [],
  "error": null
}
```

轮询成功后重点读取 `resultPayload`、`flowSummary.output` 或 `texts` 中的评分结论：

```json
{
  "runId": "a0e199ae4b0d476a8294e1ee91bbebda",
  "businessKey": "fission_evaluate",
  "status": "succeeded",
  "resultPayload": {
    "decision": "pass",
    "score": 86,
    "problem_tags": [],
    "reason": "图案逻辑与原图一致，质量可用",
    "next_action": "accept"
  }
}
```

参数说明：

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `originalImageUrl` | 是 | 无 | 裂变前原图 URL，必须能被中台访问。 |
| `generatedImageUrl` | 是 | 无 | 裂变后生成图 URL，必须能被中台访问。 |
| `context` | 否 | `{}` | 业务上下文。建议传裂变版本、提示词、重绘幅度、profile 等，帮助评分模型判断是否符合目标。 |
| `callbackUrl` | 否 | 无 | 终态回调地址；即使回调失败也可继续用 `runId` 轮询。 |
| `traceId/requestId` | 否 | 自动生成 | 业务链路追踪字段，建议传。 |

常见错误：

- `VL_EVAL_IMAGE_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_API_KEY_INACTIVE`
- `BUSINESS_API_KEY_EXPIRED`
- `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`
- `ABILITY_TASK_FAILED`

说明：

- 该接口只做评分，不会自动二次裂变。
- 该接口已经使用业务 API Key 和 `runId` 轮询，不再要求业务方理解评测端 `evalRunId`。
- 如需继续兼容旧 Coze 轮询，可把 `runId` 填入 `/api/coze/podi/tasks/get` 的 `taskId` 字段查询。

---

## 5) 提交扩图

### POST /api/business/outpaint/runs

请求体：

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "prompt": "向左右扩展，保持背景纹理、边缘走势和色彩密度一致",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-outpaint-001",
  "expand_left": 408,
  "expand_right": 408,
  "expand_top": 0,
  "expand_bottom": 0,
  "width": 1024,
  "height": 1024,
  "inputs": {
    "兼容说明": "旧调用仍可继续把参数放在 inputs 内；新调用建议使用顶层字段"
  }
}
```

响应体同图裂变。

常见错误：

- `BUSINESS_IMAGE_URL_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_CLIENT_DISABLED`
- `BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED`
- `BUSINESS_USER_SCOPE_REQUIRED`
- `BUSINESS_USER_SCOPE_FORBIDDEN`
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `expand_left/expand_right/expand_top/expand_bottom/width/height/timeout` 直接作为顶层字段传入。
- 旧调用仍兼容 `inputs.expand_left` 等格式。

---

## 6) 查询业务任务

### POST /api/business/pattern-extract/route-preview

### POST /api/business/fission/route-preview

### POST /api/business/outpaint/route-preview

用途：在不提交真实任务、不消耗额度的情况下，预览某个业务方标识会命中哪个业务版本。主要用于默认版本切换前、灰度白名单验证、比例灰度验证。

请求体示例：

```json
{
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "metadata": {
    "grayKey": "tenant-a"
  }
}
```

响应体示例：

```json
{
  "businessKey": "fission",
  "requestedVersion": null,
  "selectedCapabilityId": "biz_fission_v2_gray",
  "selectedVersion": "v2",
  "selectedDisplayName": "图裂变 · GPT Image 2 灰度版",
  "selectedStatus": "active",
  "selectedIsDefault": false,
  "selectedBy": "rollout_allowlist",
  "routeInfo": {
    "businessVersionId": "biz_fission_v2_gray",
    "version": "v2",
    "selectedBy": "rollout_allowlist",
    "routeKeyHash": "6f8d7a9c21ab",
    "rolloutPercent": 10
  },
  "defaultCapabilityId": "biz_fission_v1_default",
  "defaultVersion": "v1",
  "activeVersions": [
    {
      "id": "biz_fission_v2_gray",
      "version": "v2",
      "displayName": "图裂变 · GPT Image 2 灰度版",
      "isDefault": false,
      "hasRollout": true
    }
  ]
}
```

说明：

- 预览接口不会创建 `BusinessRun`，不会提交底层能力任务，也不会触发 Coze/ComfyUI/vendor 调用。
- 灰度命中优先级：明确传 `version` > 灰度白名单 > 灰度比例 > 默认版本。
- 灰度标识优先读取 `metadata.grayKey`、`metadata.tenantId`、`inputs.grayKey`，也支持顶层 `tenantId/clientId/traceId/requestId`。
- 对外只返回 `routeKeyHash`，不返回业务方原始灰度标识。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`

---

### GET /api/business/runs/{runId}

用途：查询单个业务任务。

### POST /api/business/runs/get

用途：Coze 工具箱友好的查询接口。

请求体：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39"
}
```

默认返回轻量结果，字段与 Coze 轮询口径保持一致。排障时可追加：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "detail": "full"
}
```

也兼容 `includeDebug: true`。只有完整模式才返回 `routeInfo/steps/flowSummary/requestPayload/resultPayload/costBreakdown` 等内部排障字段。

Coze 旧工具箱兼容查询：

```json
{
  "taskId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39"
}
```

调用 `/api/coze/podi/tasks/get` 后返回 `taskStatus/imageUrls/debugResponse`。该入口主要给 Coze 或同机内网工具箱使用；外部业务默认使用 `/api/business/runs/get`。

默认轻量终态响应示例：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "taskId": "t1.outpaint.default.xxx",
  "status": "succeeded",
  "taskStatus": "succeeded",
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png",
  "imageUrls": [
    "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png"
  ],
  "videoUrl": null,
  "videoUrls": [],
  "text": "succeeded",
  "texts": [],
  "error": null,
  "errorMessage": null,
  "errorCode": null,
  "debugResponse": null,
  "debugUrl": null,
  "retryAfterSeconds": null,
  "expectedImageCount": null,
  "traceId": "trace-outpaint-001",
  "requestId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "durationMs": 126000,
  "createdAt": "2026-05-14T10:00:00",
  "finishedAt": "2026-05-14T10:02:06"
}
```

默认轻量响应字段说明：

| 字段 | 类型 | 含义 | 业务方处理建议 |
| --- | --- | --- | --- |
| `runId` | string | 中台业务任务 ID，也是业务方保存和轮询的主 ID。 | 提交成功后必须保存；查询 `/api/business/runs/get` 时继续传这个值。 |
| `taskId` | string/null | 底层原子能力任务 ID。 | 仅用于排障和中台定位；业务系统不需要依赖它。 |
| `status` | string | 中台业务状态，取值通常为 `queued/running/succeeded/failed/cancelled/timeout`。 | 判断任务是否结束的主字段。 |
| `taskStatus` | string | 兼容 Coze 旧轮询口径的状态字段。 | 老调用方可以继续读这个字段；含义与 `status` 保持一致。 |
| `imageUrl` | string/null | 第一张结果图的 OSS 地址。 | 只需要单张结果时读取这个字段。 |
| `imageUrls` | string[] | 全部结果图 OSS 地址。 | 裂变、扩图、花纹提取优先读取这个字段。 |
| `videoUrl` | string/null | 第一个视频结果地址。 | 当前三个裂变交付接口通常为空，后续视频能力会使用。 |
| `videoUrls` | string[] | 全部视频结果地址。 | 当前三个裂变交付接口通常为空。 |
| `text` | string/null | 第一条文本结果；没有文本结果时通常为当前状态词。 | 评分接口可能是 JSON 字符串；普通生图接口可忽略。 |
| `texts` | string[] | 全部文本结果。 | 评分接口可读取第一条并按 JSON 解析；普通生图接口通常为空数组。 |
| `resultPayload` | object/null | 结构化结果。默认轻量响应只在评分等无图片输出场景返回关键结构。 | 裂变评分优先读取 `decision/score/problem_tags/reason/next_action`。 |
| `error` | string/null | 失败摘要。 | 只在失败时读取；用于日志和人工排查。 |
| `errorMessage` | string/null | 面向调用方的失败说明。 | 展示给业务或测试同学时优先用这个字段。 |
| `errorCode` | string/null | 标准错误码。 | 程序判断失败类型时优先用这个字段，不要解析错误文案。 |
| `debugResponse` | string/object/null | 脱敏后的调试信息。 | 只用于排障，不作为业务逻辑判断依据。 |
| `debugUrl` | string/null | 中台内部排障链接。 | 内部人员使用；外部业务可忽略。 |
| `retryAfterSeconds` | number/null | 建议下次轮询间隔。 | `queued/running` 时按该值延迟重试，避免高频轮询。 |
| `expectedImageCount` | number/null | 预计出图数量。 | 可用于前端展示进度；为空时不要当作失败。 |
| `logId` | number/null | 能力调用记录 ID。 | 中台排查使用；业务方可随问题单一起提供。 |
| `traceId` | string/null | 调用方传入或中台生成的链路追踪 ID。 | 建议业务方每次提交主动传入，方便跨系统查日志。 |
| `requestId` | string/null | 调用方请求 ID。 | 建议用于业务侧幂等和排障关联。 |
| `durationMs` | number/null | 任务耗时，单位毫秒。 | 终态后用于统计耗时；排队中通常为空。 |
| `createdAt` | string/null | 任务创建时间。 | ISO 时间字符串。 |
| `startedAt` | string/null | 任务实际开始时间。 | 可用于判断排队等待时长。 |
| `finishedAt` | string/null | 任务结束时间。 | 终态后出现。 |

裂变评分 `resultPayload` 字段说明：

| 字段 | 类型 | 含义 | 业务方处理建议 |
| --- | --- | --- | --- |
| `decision` | string | 总结论，常见值为 `pass`、`needs_refission`、`reject`。 | `pass` 可直接使用；`needs_refission` 可再次调用裂变；`reject` 建议人工复核或丢弃。 |
| `score` | number | 0-100 的综合分。 | 可作为排序或阈值判断；最终动作仍以 `decision` 为准。 |
| `scores` | object | 分项评分，例如形状、材质、比例、逻辑。 | 为空或 null 时不视为接口异常。 |
| `problem_tags` | string[] | 问题标签列表。 | 用于二次裂变策略或人工筛选。 |
| `reason` | string | 模型给出的判定原因。 | 可展示给测试/运营，用于解释为什么通过或不通过。 |
| `next_action` | object | 建议动作，例如 `{"type":"accept"}`。 | 可按 `type` 做业务分流。 |
| `eval_json` | object | 更详细的评估证据。 | 默认不要求业务方解析，主要用于质量复盘。 |
| `route_json` | object | 路由或修复建议。 | 需要自动二次裂变时可参考；普通接入可忽略。 |

`detail=full` 排障响应示例：

```json
{
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "outpaint",
  "version": "v1",
  "status": "succeeded",
  "source": "partner-api",
  "channel": "open-api",
  "traceId": "trace-outpaint-001",
  "requestId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "tenantId": null,
  "clientId": null,
  "abilityId": "comfyui_flux2_klein_9b_outpaint",
  "abilityName": "扩图 · FLUX2-Klein 9B",
  "vendorModelId": null,
  "vendorModelName": null,
  "routeInfo": {
    "businessVersionId": "biz_outpaint_v1_flux2_klein_9b",
    "version": "v1",
    "selectedBy": "default",
    "routeKeyHash": "6f8d7a9c21ab"
  },
  "flowSummary": {
    "total": 2,
    "succeeded": 2,
    "failed": 0,
    "running": 0,
    "queued": 0,
    "progressPercent": 100,
    "message": "业务链路执行成功",
    "nextAction": "结果已回填，可继续检查回调状态",
    "route": {
      "businessKey": "outpaint",
      "businessVersionId": "biz_outpaint_v1_flux2_klein_9b",
      "version": "v1",
      "selectedBy": "default"
    },
    "ability": {
      "id": "comfyui_flux2_klein_9b_outpaint",
      "name": "扩图 · FLUX2-Klein 9B",
      "taskId": "task_xxx",
      "logId": 1234
    },
    "executor": {
      "id": "executor_comfyui_pattern_extract_158",
      "name": "ComfyUI 5090 · 158 · 117.50.80.158",
      "type": "comfyui",
      "abilityLogId": 1234
    },
    "output": {
      "hasOutput": true,
      "hasOssOutput": true,
      "imageCount": 1,
      "videoCount": 0,
      "textCount": 0,
      "firstImageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png"
    },
    "callback": {
      "status": null,
      "httpStatus": null,
      "error": null
    }
  },
  "steps": [
    {
      "order": 1,
      "stepType": "vl_analyze",
      "role": "preprocess",
      "displayName": "VL 图像理解",
      "status": "succeeded",
      "abilityId": "vl_analyze_image",
      "abilityName": "VL · 图像结构化分析",
      "abilityTaskId": "t1.outpaint.auto.vl_xxx",
      "executorId": "executor_vendor_api_default",
      "executorName": "第三方 API 通道",
      "executorType": "vendor-api",
      "executionEvidence": {
        "abilityLogId": 1233,
        "executorId": "executor_vendor_api_default",
        "executorName": "第三方 API 通道",
        "executorType": "vendor-api",
        "status": "succeeded",
        "hasOssOutput": false,
        "assetCount": 0
      },
      "durationMs": 1830,
      "costAmount": 0.01,
      "currency": "USD",
      "resultSummary": {
        "summary": "蓝白植物图案，主体为连续花纹",
        "imageDesc": "蓝白色植物纹样，中心构图，可用于裂变和扩图提示词",
        "positivePrompt": "蓝白植物连续花型，清新手绘风格"
      }
    },
    {
      "order": 2,
      "stepType": "ability_task",
      "role": "primary",
      "displayName": "主执行能力",
      "status": "succeeded",
      "abilityId": "comfyui_flux2_klein_9b_outpaint",
      "abilityName": "扩图 · FLUX2-Klein 9B",
      "abilityTaskId": "t1.outpaint.auto.xxx",
      "executorId": "executor_comfyui_pattern_extract_158",
      "executorName": "ComfyUI 5090 · 158 · 117.50.80.158",
      "executorType": "comfyui",
      "executionEvidence": {
        "abilityLogId": 1234,
        "executorId": "executor_comfyui_pattern_extract_158",
        "executorName": "ComfyUI 5090 · 158 · 117.50.80.158",
        "executorType": "comfyui",
        "status": "succeeded",
        "storedUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png",
        "hasOssOutput": true,
        "assetCount": 1
      }
    }
  ],
  "taskId": "t1.outpaint.default.xxx",
  "imageUrls": [
    "https://podi.oss-cn-hangzhou.aliyuncs.com/results/outpaint.png"
  ],
  "videoUrls": [],
  "texts": [],
  "error": null,
  "durationMs": 126000,
  "costAmount": 0.18,
  "currency": "USD",
  "quotaUnits": 1,
  "debugUrl": null
}
```

常见错误：

- `BUSINESS_RUN_ID_REQUIRED`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_FORBIDDEN`

说明：

- 默认轻量响应只返回业务方真正需要处理的字段，避免把 VL 卡片、原子能力原始响应、执行节点证据和 SQL 排障信息一次性返回给业务方。
- `steps` 只在 `detail=full` 或 `includeDebug=true` 时返回，是业务配方步骤状态。当前版本至少记录主执行能力；启用 VL 辅助后会额外提交并记录 VL 步骤。
- `flowSummary` 只在完整模式返回，是给管理端和排障使用的链路证据：包含业务版本、原子能力、实际执行节点、输出回填和回调状态。业务方正常轮询只需要关注 `status/taskStatus/imageUrls/videoUrls/texts/error`。
- `flowSummary.output` 会按 `imageCount/videoCount/textCount/structuredCount/resourceCount` 分开展示，管理端不得继续把所有结果都当图片处理。
- `steps[].executorId/executorName/executionEvidence` 来自能力调用日志，用于确认任务是否真的打到预期机器，以及结果是否已经落 OSS。
- 默认情况下最终出图仍以主执行能力为准，VL 伴随步骤用于链路观测和结果积累。
- 阻塞式 VL 串联开启后，主能力会等 VL 成功后再提交；查询时可能先看到 VL 运行中、主能力仍是 `planned`。
- `steps[].resultSummary` 只返回安全摘要，例如 VL 图片描述、提示词建议、图片/视频数量，不返回完整第三方原始响应或大字段。
- 结果 URL 提取同时兼容 `storedUrl/stored_url/ossUrl/url/sourceUrl`，避免底层已落 OSS 但业务层没有回填。
- `durationMs/costAmount/currency/quotaUnits` 是成本与配额字段。优先读取底层能力日志和厂商返回；若厂商未返回成本，则回退读取模型目录 `costPolicy` 或能力元数据 `pricing/costPolicy` 自动估算。

---

## 7) VL 图像理解原子能力

VL 进入统一能力弹药库，能力 ID：

- `vl_analyze_image`

调用方式仍走统一能力接口：

- `POST /api/abilities/vl_analyze_image/invoke`
- 后续也可通过业务配方把 VL 作为花纹提取/图裂变/扩图的前置分析步骤。

请求体示例：

```json
{
  "inputs": {
    "image_url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
    "provider": "volcengine_vl",
    "prompt": "分析图片主体、风格、颜色、构图，并输出适合裂变的提示词建议"
  }
}
```

结构化结果字段：

- `description`：图片描述
- `subjects`：主体
- `style`：风格
- `colors`：颜色
- `composition`：构图
- `textElements`：文字元素
- `riskFlags`：风险提示
- `promptCard`：可用于裂变/扩图的提示词建议

常见错误：

- `VL_IMAGE_REQUIRED`
- `VL_PROVIDER_ABILITY_NOT_FOUND`
- `VL_COZE_WORKFLOW_NOT_CONFIGURED`
- `VL_PROVIDER_UNSUPPORTED`

---

## 8) OpenAPI 工具箱

### GET /api/business/openapi.json

用途：给 Coze 导入“业务层工具箱”。
当前包含：

- `podi_business_fission_run`
- `podi_business_outpaint_run`
- `podi_business_pattern_extract_run`
- `podi_business_fission_route_preview`
- `podi_business_outpaint_route_preview`
- `podi_business_pattern_extract_route_preview`
- `podi_business_run_get`

OpenAPI 内每个工具都会枚举错误响应：

- `400`：缺少必要参数或业务配方非法，例如 `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_RUN_ID_REQUIRED`。
- `401`：缺少服务 Token 或不在可信内网，例如 `AUTHORIZATION_REQUIRED`。
- `403/404`：业务任务不可访问或不存在，例如 `BUSINESS_RUN_FORBIDDEN`、`BUSINESS_RUN_NOT_FOUND`。
- `429`：队列或并发限制。
- `503`：查询链路临时不可用，例如 `BUSINESS_RUN_TEMPORARY_UNAVAILABLE`，业务方可稍后重试查询。
- `403/429`：命中业务方配置限制，例如业务方停用、未开通该业务、日调用或并发达到上限。
- `500`：底层能力、ComfyUI 或第三方模型执行失败，例如 `COMFYUI_TIMEOUT`、`VENDOR_API_EXECUTION_FAILED`。

原则：

- Coze 新工作流优先调用业务 API，而不是在 Coze 内继续手搓底层编排。
- 旧 Coze workflow 不立即下线，继续保障当前业务接入稳定。
- 底层版本切换优先在中台改默认业务版本，避免业务方频繁换 workflow ID。

---

## 9) 管理端接口

### GET /api/admin/business/clients

用途：查看业务方接入配置。业务方配置用于把 `tenantId/clientId` 从“松散日志字段”升级为可启停、可限额、可限制业务范围的管理对象。

可选查询参数：

- `tenant_id`：按业务方过滤。
- `client_id`：按客户端/应用过滤。
- `status`：按状态过滤，例如 `active`、`disabled`。

### POST /api/admin/business/clients

用途：新增业务方配置。配置存在时，业务任务提交会先执行策略检查；未配置的历史调用暂时保持兼容，不强制阻断。

请求体：

```json
{
  "tenantId": "tenant-a",
  "clientId": "coze-main",
  "displayName": "业务方 A · Coze 主工作流",
  "status": "active",
  "allowedBusinessKeys": ["fission", "fission_evaluate", "outpaint"],
  "dailyRunLimit": 200,
  "dailyQuotaUnits": 200,
  "concurrentRunLimit": 5,
  "metadata": {
    "owner": "business-a"
  }
}
```

字段说明：

- `tenantId` 是业务方 ID，必填。
- `clientId` 是具体应用或工作流 ID，可为空；为空时表示该 `tenantId` 的默认策略。
- `allowedBusinessKeys` 为空表示不限制业务能力；填值后只允许调用这些业务，例如 `fission/fission_evaluate/outpaint`。
- `dailyRunLimit` 限制当日提交次数。
- `dailyQuotaUnits` 按估算额度限制当日用量；当前每次提交默认按 1 个额度估算，后续会接正式计费。
- `concurrentRunLimit` 限制该业务方同时处于排队/运行中的任务数。

常见错误：

- `BUSINESS_CLIENT_TENANT_REQUIRED`
- `BUSINESS_CLIENT_DISPLAY_NAME_REQUIRED`
- `BUSINESS_CLIENT_STATUS_INVALID`
- `BUSINESS_CLIENT_DUPLICATED`

### PATCH /api/admin/business/clients/{clientConfigId}

用途：更新业务方配置，例如临时停用、放大额度、只开放部分业务能力。

请求体可只传要修改的字段：

```json
{
  "status": "disabled",
  "dailyRunLimit": 50
}
```

常见错误：

- `BUSINESS_CLIENT_NOT_FOUND`
- `BUSINESS_CLIENT_STATUS_INVALID`
- `BUSINESS_CLIENT_DUPLICATED`

### GET /api/admin/business/api-keys

用途：查看业务 API Key。这里管理的是业务方调用 `/api/business/*` 时使用的 Key，不是第三方模型 Key。

响应字段：

- `keyPreview`：脱敏后的 Key。
- `tenantId/clientId`：Key 绑定的业务方范围。
- `allowedBusinessKeys`：允许调用的业务；为空表示允许全部业务。
- `usageCount`：累计鉴权通过次数。
- `expireAt`：过期时间，可为空。

### POST /api/admin/business/api-keys

用途：创建业务 API Key。当前先用于身份识别和调用审计，暂不强制限流。

请求体：

```json
{
  "name": "业务方 A · 开放接口",
  "key": "podi_live_xxx",
  "status": "active",
  "tenantId": "tenant-a",
  "clientId": "open-api",
  "allowedBusinessKeys": ["fission", "fission_evaluate", "outpaint"],
  "expireAt": "2026-12-31T23:59:59"
}
```

常见错误：

- `BUSINESS_API_KEY_DUPLICATED`

### PATCH /api/admin/business/api-keys/{keyId}

用途：更新业务 API Key，例如停用、延期、调整可调用业务。

常见错误：

- `BUSINESS_API_KEY_NOT_FOUND`

### GET /api/admin/business/api-key-usage

用途：查看业务 API Key 最近调用记录。每次 Key 调用业务提交、路由预览或任务查询都会写入。

可选查询参数：

- `api_key_id`
- `business_key`
- `tenant_id`
- `client_id`
- `limit`，默认 50，最大 200。

记录字段包括：Key 名称、接口路径、状态码、业务标识、runId、requestId、traceId、tenantId/clientId、错误码和耗时。

### GET /api/admin/business/capabilities

用途：管理端展示业务能力版本、发布时间、默认版本、配方来源。

响应会额外解析底层来源，便于非技术同学判断“这个业务版本到底在调用什么”：

- `primaryAbilityId` / `primaryAbilityName`：配方中的主原子能力。
- `vendorModelId` / `vendorModelName`：主原子能力绑定的模型目录项；没有绑定时为空。
- `governanceStatus`：上线前体检状态，`ready` 表示底层就绪，`blocker` 表示默认入口存在阻塞，`warning` 表示可测试但需要补治理信息。
- `governanceIssues` / `governanceSuggestions`：体检发现的问题和建议，例如主能力不存在、模型未启用、第三方密钥不可用、模型成本未配置。
- `runtimeKeyConfigured`：第三方模型所需密钥是否可用；非第三方能力可能为空。
- `modelCostConfigured`：第三方模型成本策略是否已配置；非第三方能力可能为空。
- `egressVerified`：需要出网的第三方模型是否在最近 7 天内有 active Key 带密钥出网检查成功；非出网模型可能为空。
- `latestAcceptance` / `acceptanceRecords`：人工验收记录；默认版本切换前必须有最近一次 `passed`。
- `releaseGate`：上线判断摘要，包含 `status`、`label`、`canRelease`、`canRequestDefault`、`blockers`、`warnings`、`suggestions`。管理端以它判断是否能申请默认切换。
- `latestRun`：该业务版本最近一次调用摘要，包含状态、时间、结果数量和错误摘要，供管理端快速判断版本健康度。
- `runMetrics`：该业务版本近 24 小时运行统计，包含总调用、成功、失败、排队、运行中、成功率，供默认版本切换前判断风险。

业务治理提示码：

| 提示码 | 含义 | 建议动作 |
| --- | --- | --- |
| `BUSINESS_GOVERNANCE_PRIMARY_ABILITY_MISSING` | 业务版本未绑定主能力 | 编辑业务版本，绑定真实主能力后再测试或设为默认。 |
| `BUSINESS_GOVERNANCE_PRIMARY_ABILITY_NOT_FOUND` | 主能力编号在能力目录中不存在 | 修正配方，或恢复对应能力。 |
| `BUSINESS_GOVERNANCE_PRIMARY_ABILITY_INACTIVE` | 主能力未启用 | 先启用主能力，或切换到已启用能力。 |
| `BUSINESS_GOVERNANCE_EXECUTABLE_STEP_MISSING` | 配方没有可执行步骤 | 补齐可执行步骤，避免只剩配置壳。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_NOT_FOUND` | 绑定的第三方模型目录不存在 | 修正模型绑定或重新同步模型目录。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_INACTIVE` | 绑定的第三方模型未启用 | 启用模型，或切到其他可用模型。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED` | 第三方模型缺少验收通过记录 | 在模型弹药库跑通能力测试或测评端样例，并记录模型验收通过。 |
| `BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING` | 第三方模型缺少成本策略 | 正式收费或对外开放前补成本口径。 |
| `BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING` | 第三方模型没有可用密钥 | 到模型弹药库配置并验证密钥。 |
| `BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED` | 出网模型缺少最近一次带密钥出网验证成功记录 | 在模型弹药库对该厂商 Key 执行验证，确认网络、Key 和上游账号都可用。 |

### POST /api/admin/business/capabilities

用途：新增一个业务版本，例如图裂变 v2、扩图 v2。新增后可以选择是否立即设为默认版本。

请求体：

```json
{
  "businessKey": "fission",
  "version": "v2",
  "displayName": "图裂变 · GPT Image 2 测试版",
  "description": "用于灰度验证蒙版裂变能力",
  "status": "active",
  "isDefault": false,
  "releaseTime": "2026-04-25T10:00:00",
  "primaryAbilityId": "ability_openai_fission",
  "recipe": {
    "mode": "single_ability_task"
  },
  "inputSchema": { "fields": [] },
  "outputSchema": { "fields": [] },
  "metadata": {
    "release_note": "先灰度，不直接替换默认版本",
    "rollout": {
      "enabled": true,
      "percent": 10,
      "allowlist": ["tenant-a"]
    }
  }
}
```

说明：

- `primaryAbilityId` 是必填的业务主能力；后端会自动写入 `recipe.primaryAbilityId` 和第一步配方。
- `isDefault=true` 时，后端会把同一个 `businessKey` 下其它版本改成非默认。
- 默认版本必须是 `active` 状态，并且必须通过完整上线门禁：业务验收通过、底层治理无阻断、第三方模型有验收、计价、可用 Key，出网模型还需要最近 7 天带密钥出网验证成功。
- 预置业务版本只负责初始化和补齐字段，不会在后续刷新时覆盖管理端已经切换的默认版本或启停状态。
- 核心业务必须至少保留一个可回滚保底版本；“可回滚”不只看 active 非默认，还要有最近一次验收通过、最近成功真实样本且有输出、上线门禁不阻塞。图裂变预置 `biz_fission_rollback_e7_flux2_liebian`，扩图预置 `biz_outpaint_rollback_huawen_kuotu`，用于默认版本异常时快速切回。
- `metadata.rollout` 是灰度规则；业务方不指定 `version` 时才会生效。
- 灰度命中优先级：明确传 `version` > 灰度白名单 > 灰度比例 > 默认版本。
- 灰度使用 `metadata.grayKey`、`metadata.tenantId`、`metadata.userId`、顶层 `tenantId/clientId/traceId/requestId`、用户 ID 或图片 URL 做稳定分流；对外只返回 `routeKeyHash`，不直接暴露原始标识。

常见错误：

- `BUSINESS_KEY_REQUIRED`
- `BUSINESS_VERSION_REQUIRED`
- `BUSINESS_DISPLAY_NAME_REQUIRED`
- `BUSINESS_CAPABILITY_VERSION_DUPLICATED`
- `BUSINESS_RECIPE_INVALID`
- `BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`
- `BUSINESS_ACCEPTANCE_REQUIRED`
- `BUSINESS_RELEASE_GATE_BLOCKED`
- `VENDOR_MODEL_NOT_FOUND`

### PATCH /api/admin/business/capabilities/{capabilityId}

用途：编辑业务版本，常用场景是切默认版本、替换底层原子能力、修改发布时间/说明。

请求体可以只传要修改的字段：

```json
{
  "status": "active",
  "isDefault": true,
  "primaryAbilityId": "ability_openai_fission"
}
```

常见错误同新增接口。

当本次编辑会把版本设为默认，或修改现有默认版本的状态/配方/主能力时，同样会执行完整上线门禁；未通过时返回 `BUSINESS_ACCEPTANCE_REQUIRED` 或 `BUSINESS_RELEASE_GATE_BLOCKED`。

### POST /api/admin/business/capabilities/{capabilityId}/acceptance-records

用途：记录业务版本的人工验收结论。它不改变业务流量，只把“测评端真实链路是否通过、回调和 OSS 回填是否正常”等证据写入版本元数据，方便后续切默认、灰度和回滚时有依据。

请求体：

```json
{
  "status": "passed",
  "note": "测评端真实链路通过，回调和结果回填正常。",
  "evidenceRunId": "run_xxx",
  "evidenceUrl": "https://example.com/report",
  "checklist": {
    "businessFlow": true,
    "callback": true,
    "resultAssets": true
  }
}
```

响应：返回更新后的业务版本，新增字段包括：

- `latestAcceptance`：最近一次验收记录。
- `acceptanceRecords`：最近 5 条验收记录摘要。
- `releaseGate`：会同步更新；`status=ready` 才表示没有明显上线阻断。
- `metadata.latestAcceptance` / `metadata.acceptanceRecords`：完整元数据记录，最多保留 20 条。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_ACCEPTANCE_STATUS_INVALID`

自动化入口：真实业务巡检通过后，可以用 `backend/scripts/patrol_business_api.py --mode live --record-acceptance` 自动写入验收记录。脚本会把 `runId`、实际执行节点证据、输出数量和巡检来源写入 `metadata`，后续发布门禁读取同一份验收结论。

### POST /api/admin/business/capabilities/{capabilityId}/promote

用途：把某个业务版本切为默认版本，并写入版本事件。相比直接 PATCH `isDefault=true`，这个接口语义更明确，适合管理端按钮、发布记录和后续审计。

请求体：

```json
{
  "activate": true,
  "note": "灰度验证通过，切为默认版本"
}
```

规则：

- `activate=true` 时，如果目标版本当前未启用，会先启用再设为默认。
- `activate=false` 且目标版本未启用时，返回 `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`。
- 目标版本必须先记录最近一次 `passed` 验收，否则返回 `BUSINESS_ACCEPTANCE_REQUIRED`。
- 目标版本还必须通过完整上线门禁；第三方模型缺计价、缺模型验收、缺可用 Key、出网未验证等都会返回 `BUSINESS_RELEASE_GATE_BLOCKED`。
- 成功后同一个 `businessKey` 下其它版本会自动取消默认。
- 后端会在 `metadata.releaseEvents` 追加 `promote_default` 事件，记录切换原因、操作者和时间。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`
- `BUSINESS_ACCEPTANCE_REQUIRED`
- `BUSINESS_RELEASE_GATE_BLOCKED`

### POST /api/admin/business/rollback/{businessKey}

用途：把某个业务入口回滚到上一默认版本。管理端优先使用这个接口处理线上异常，而不是让运营手工查版本、再点“设为默认”。

请求体：

```json
{
  "activate": true,
  "note": "线上失败，回滚上一稳定版"
}
```

也可以指定明确的回滚目标：

```json
{
  "targetCapabilityId": "biz_fission_v1_default",
  "activate": true,
  "note": "指定回滚到 v1"
}
```

规则：

- 不传 `targetCapabilityId` 时，后端优先读取当前默认版本 `metadata.releaseEvents` 中记录的上一默认版本。
- 如果当前默认版本没有切换记录，则退到同一 `businessKey` 下最近的 active 非默认版本。
- 回滚成功后，目标版本会成为默认版本，其它版本自动取消默认。
- 后端会在目标版本 `metadata.releaseEvents` 追加 `rollback_default` 事件，记录回滚原因、操作者和回滚前默认版本。
- 如果没有可回滚版本，返回 `BUSINESS_ROLLBACK_TARGET_NOT_FOUND`。
- 发版前必须执行 `backend/scripts/business_version_safety_audit.py`，确认花纹提取、图裂变、扩图都有 active 默认版本和 active 保底版本。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_KEY_REQUIRED`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_ROLLBACK_TARGET_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`

### POST /api/admin/business/route-preview/{businessKey}

用途：管理端灰度命中预览。它和公开 `route-preview` 一样不提交真实任务，只用于验证某个 `tenantId/clientId/grayKey` 会命中哪个版本。

请求体示例：

```json
{
  "tenantId": "tenant-a",
  "metadata": {
    "grayKey": "tenant-a"
  }
}
```

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`

### GET /api/admin/business/runs

参数：

- `business_key`：可选，`pattern_extract` / `fission` / `outpaint`
- `version`：可选，按业务版本过滤，例如 `v1`
- `status`：可选，按运行状态过滤，常见值为 `queued` / `running` / `succeeded` / `failed` / `cancelled`
- `billing_status`：可选，按计费状态过滤，取值为 `billable` / `unpriced` / `no_charge` / `billing_pending`
- `callback_status`：可选，按回调状态过滤，取值为 `success` / `failed` / `running`
- `issue_category`：可选，按链路问题过滤，取值为 `executor` / `output` / `callback` / `billing` / `parameter` / `version` / `none`
- `source`：可选，按调用来源过滤，例如 `coze` / `client` / `partner-api`
- `tenant_id`：可选，按租户/业务方过滤
- `client_id`：可选，按客户端/应用过滤
- `trace_id`：可选，按调用链路 ID 精确查询
- `limit`：默认 50，最大 200

用途：查看最近业务运行记录，为后续统计、计费、灰度分析打基础。

记录字段：

- `traceId/requestId/tenantId/clientId/channel/source`：定位一次业务调用来自哪里、属于哪个业务方或客户端。
- `durationMs`：业务任务主链路耗时，终态后回填。
- `costAmount/currency/quotaUnits/costBreakdown`：底层能力返回的成本和用量，保留做排查与成本测算。
- `billingStatus/chargeable/noChargeReason`：业务计费口径。`billable` 表示成功且有成本或额度，可进入正式账单；`no_charge` 表示失败、取消或超时，不向业务方计费；`billing_pending` 表示任务未终态；`unpriced` 表示成功但缺少定价，需要先补成本规则。
- `issueCategory/issueLabel/issueAction/issueEvidence`：链路问题分类。用于管理端快速区分执行节点、结果回填、业务回调、计费扣减、参数、版本/路由等问题。
- `retestSourceRunId/retestAttempts/retestLatestRunId/retestLatestStatus/retestRecovered/retestSummary`：复测追踪字段。原问题任务会显示复测次数、最新复测任务和是否恢复；复测任务会显示来源任务，便于从“发现问题”追到“确认恢复”。

### GET /api/admin/business/usage-summary

用途：按当前筛选统计业务调用量、成功率、失败样本、平均耗时、成本和额度消耗，给默认版本切换、灰度观察、后续收费报表使用。

参数：

- `window_hours`：统计窗口，默认 24，范围 1-2160。
- `business_key`：可选，`pattern_extract` / `fission` / `outpaint`。
- `version`：可选，按业务版本过滤。
- `status`：可选，按运行状态过滤。
- `issue_category`：可选，按链路问题过滤，取值同 `/api/admin/business/runs`。
- `source`：可选，按调用来源过滤，例如 `coze` / `client` / `partner-api`。
- `tenant_id`：可选，按租户/业务方过滤。
- `client_id`：可选，按客户端/应用过滤。
- `trace_id`：可选，按调用链路 ID 精确过滤。

响应示例：

```json
{
  "windowHours": 24,
  "filters": {
    "business_key": "fission",
    "source": "coze",
    "tenant_id": "tenant-a"
  },
  "total": 12,
  "succeeded": 10,
  "failed": 2,
  "running": 0,
  "queued": 0,
  "cancelled": 0,
  "successRate": 0.8333,
  "avgDurationMs": 128000,
  "costByCurrency": {
    "USD": 2.4
  },
  "actualCostByCurrency": {
    "USD": 2.6
  },
  "quotaUnits": 12,
  "actualQuotaUnits": 13,
  "billable": 10,
  "unpriced": 0,
  "noCharge": 2,
  "billingPending": 0,
  "byBusiness": [
    {
      "key": "fission",
      "label": "fission",
      "total": 12,
      "succeeded": 10,
      "failed": 2,
      "running": 0,
      "queued": 0,
      "cancelled": 0,
      "successRate": 0.8333,
      "avgDurationMs": 128000,
      "costByCurrency": { "USD": 2.4 },
      "actualCostByCurrency": { "USD": 2.6 },
      "quotaUnits": 12,
      "actualQuotaUnits": 13,
      "billable": 10,
      "unpriced": 0,
      "noCharge": 2,
      "billingPending": 0,
      "latestAt": "2026-04-25T10:00:00"
    }
  ],
  "bySource": [],
  "byTenant": [],
  "byClient": [],
  "byVersion": [],
  "byIssue": [
    {
      "key": "executor",
      "label": "执行节点问题",
      "total": 2,
      "succeeded": 0,
      "failed": 2,
      "running": 0,
      "queued": 0,
      "cancelled": 0,
      "severity": "danger",
      "action": "检查执行节点连通性、队列、模型依赖和能力日志。"
    }
  ],
  "unresolvedIssues": [
    {
      "key": "executor",
      "label": "执行节点问题",
      "total": 1,
      "failed": 1,
      "running": 0,
      "queued": 0,
      "cancelled": 0,
      "retested": 1,
      "retestAttempts": 2,
      "severity": "danger",
      "action": "检查执行节点连通性、队列、模型依赖和能力日志。"
    }
  ],
  "recentUnresolvedIssues": [
    {
      "id": "run_xxx",
      "runId": "run_xxx",
      "businessKey": "fission",
      "version": "v2",
      "status": "failed",
      "source": "coze",
      "tenantId": "tenant-a",
      "clientId": "coze-main",
      "traceId": "trace-demo-001",
      "issueCategory": "executor",
      "issueLabel": "执行节点问题",
      "issueAction": "检查执行节点连通性、队列、模型依赖和能力日志。",
      "retestAttempts": 2,
      "retestLatestRunId": "run_retest_xxx",
      "retestLatestStatus": "failed",
      "createdAt": "2026-04-25T10:00:00"
    }
  ],
  "recentFailures": [
    {
      "id": "run_xxx",
      "runId": "run_xxx",
      "businessKey": "fission",
      "version": "v2",
      "status": "failed",
      "source": "coze",
      "channel": "coze-workflow",
      "tenantId": "tenant-a",
      "clientId": "coze-main",
      "traceId": "trace-demo-001",
      "error": "TASK_FAILED",
      "createdAt": "2026-04-25T10:00:00"
    }
  ]
}
```

计费口径：

- `costByCurrency/quotaUnits` 只统计 `billable` 的成功任务，用于后续正式账单。
- `actualCostByCurrency/actualQuotaUnits` 统计底层实际返回的所有成本和用量，用于内部排查和供应商成本复盘。
- 失败、取消、超时任务即使底层返回了成本，也会进入 `noCharge`，不进入业务方正式账单。
- 内部巡检、免计费或测试来源的成功任务也会进入 `noCharge`。典型巡检标识为 `source=business-api-patrol`、`tenantId=podi-internal-patrol`、`metadata.patrol=true`；这类任务仍保留成本用于内部复盘，但不进入业务收费账单。
- `unresolvedIssues/recentUnresolvedIssues` 会排除已经复测成功且有业务结果回填的原问题任务；复测任务本身不会重复计入原问题清单。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`

### GET /api/admin/business/runs/export

用途：按当前筛选导出业务运行 CSV，便于把“执行节点问题 / 结果回填问题 / 业务回调问题”等清单交给运维或业务方复核。

参数同 `/api/admin/business/runs`，其中 `limit` 默认 1000、最大 1000。导出内容包含业务、版本、状态、链路问题、处理建议、入口、业务方、客户端、排障编号、能力、输出数量、计费状态、回调状态和错误信息。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`

### POST /api/admin/business/runs/{runId}/retest

用途：按旧任务的原始入参创建一条新的复测任务。复测不会修改旧任务状态，也不会沿用旧任务的业务回调地址，避免管理端测试误回调业务方。

处理规则：

- 保留原业务、版本、租户、客户端和主要业务参数。
- 新任务来源固定为 `admin-retest`，渠道固定为 `manual-retest`。
- 新任务 `metadata.adminRetest` 会记录原 `runId/traceId/requestId/status`，便于复盘。
- 旧任务仍处于 `queued/running` 时不允许复测。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_NOT_FINISHED`
- `BUSINESS_RUN_RETEST_PAYLOAD_INVALID`

### POST /api/admin/business/runs/bulk/retest

用途：批量复测当前已加载的问题任务。管理端默认只对失败、取消或链路问题分类不为 `none` 的记录发起复测。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "onlyFailed": true
}
```

响应示例：

```json
{
  "action": "retest",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "items": [
    { "runId": "run_a", "newRunId": "run_new", "ok": true, "status": "queued", "message": "已创建新的复测任务。" },
    { "runId": "run_b", "ok": false, "status": "skipped", "message": "当前记录没有明显链路问题，已跳过。" }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

### POST /api/admin/business/runs/{runId}/callback/retry

用途：单条重试业务终态回调。仅用于任务已终态且配置了 `callbackUrl` 的记录；回调成功后会刷新 `callbackStatus/callbackHttpStatus/callbackError`。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_CALLBACK_NOT_CONFIGURED`
- `BUSINESS_RUN_NOT_FINISHED`

### POST /api/admin/business/runs/{runId}/billing/retry

用途：对单条业务任务重试计费扣减。用于“成功且可计费，但套餐/钱包扣减缺失或失败”的记录。

处理规则：

- 仅允许已终态且 `billingStatus=billable` 的任务扣费。
- 缺少平台用户 `userId` 时拒绝扣费，避免无法归属到账户；业务方外部 `userId` 不等同于平台钱包账户。
- 有可用套餐时优先按 `quotaUnits` 扣套餐，幂等键为 `business_run_package:{runId}`。
- 无可用套餐时再按 `costAmount + currency` 换算钱包点数；`USD` 按 `WALLET_POINTS_PER_USD` 换算；缺少成本时可退到 `quotaUnits`，幂等键为 `business_run:{runId}`。
- 结果写回 `costBreakdown.billingSettlement`；套餐路径同时写 `packageSettlement`，钱包路径同时写 `walletSettlement`。
- 同时写 `business_operation_logs`，方便审计是谁触发了重试。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_NOT_FINISHED`
- `BUSINESS_RUN_NOT_BILLABLE`
- `BUSINESS_RUN_UNPRICED`
- `BUSINESS_RUN_USER_REQUIRED`

### POST /api/admin/business/runs/{runId}/billing/refund

用途：对已扣费的业务任务执行套餐或钱包退回。用于“失败任务被误扣费”或人工确认需要退款的场景。

处理规则：

- 套餐扣减优先退回套餐，幂等键为 `business_run_package_refund:{runId}`。
- 钱包扣费通过钱包调账接口写正向流水，幂等键为 `business_run_refund:{runId}`。
- 不删除原扣减流水，保留完整审计链。
- 结果写回 `costBreakdown.billingSettlement.status=refunded`，并同步更新 `packageSettlement` 或 `walletSettlement`。
- 同时写 `business_operation_logs`。

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_NOT_FOUND`
- `BUSINESS_RUN_NOT_FINISHED`
- `BUSINESS_RUN_USER_REQUIRED`
- `BUSINESS_WALLET_SETTLEMENT_NOT_FOUND`
- `BUSINESS_PACKAGE_SETTLEMENT_NOT_FOUND`
- `BUSINESS_PACKAGE_SETTLEMENT_INVALID`

### POST /api/admin/business/runs/bulk/callback-retry

用途：批量重试当前筛选出的回调失败任务。管理端默认只对 `callbackStatus=failed` 或存在 `callbackError` 的已加载记录发起批量重试。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "onlyFailed": true
}
```

响应示例：

```json
{
  "action": "callback_retry",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "items": [
    { "runId": "run_a", "ok": true, "status": "success" },
    { "runId": "run_b", "ok": false, "status": "skipped", "message": "当前不是回调失败状态，已跳过。" }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

### POST /api/admin/business/runs/bulk/mark-ignored

用途：把一批已人工确认的问题记录标记为“无需处理”。该操作不修改真实任务状态，只在结果载荷中写入管理侧处理结论，后续链路问题分类会显示为“已标记无需处理”。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "note": "已人工确认，本轮暂不继续处理。"
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

### POST /api/admin/business/runs/issue-checklist

用途：把当前已加载的问题任务生成排障清单，供值班、复盘或交给执行节点维护同学处理。该接口只读任务状态，不重试任务、不改业务结果。

请求体示例：

```json
{
  "runIds": ["run_a", "run_b"],
  "onlyFailed": true
}
```

响应示例：

```json
{
  "generatedAt": "2026-05-06T10:00:00",
  "total": 2,
  "issueCount": 1,
  "skippedCount": 1,
  "byCategory": { "executor": 1 },
  "bySeverity": { "danger": 1 },
  "markdown": "# 业务运行排障清单\n...",
  "items": [
    {
      "runId": "run_a",
      "businessKey": "fission",
      "status": "failed",
      "issueCategory": "executor",
      "issueLabel": "执行节点问题",
      "issueSeverity": "danger",
      "recommendedActions": ["检查执行节点健康、队列长度、模型文件和工作流依赖。"],
      "diagnostics": ["任务状态：failed", "执行节点：ComfyUI 4090"]
    }
  ]
}
```

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`
- `BUSINESS_RUN_IDS_REQUIRED`
- `BUSINESS_RUN_BULK_LIMIT_EXCEEDED`

说明：

- 统计接口只读业务运行记录，不触发任何任务重试。
- `costByCurrency/quotaUnits` 当前来自底层能力日志、任务结果回填或模型/能力成本规则估算；如果三者都没有成本信息，对应任务会进入 `unpriced`。
- 管理端“业务能力”页的统计卡片、业务分布、来源/业务方分布和最近失败列表均来自该接口。
