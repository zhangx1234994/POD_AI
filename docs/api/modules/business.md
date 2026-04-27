# 业务能力接口

## 用途

业务能力接口是给业务方、Coze、客户端、MCP/技能复用的稳定入口。
第一阶段先开放两个样板业务：图裂变、扩图；底层仍复用统一能力任务和 ComfyUI workflow，但对外不暴露节点、workflow、executor 等实现细节。

核心约定：

- 对外统一是 `提交业务任务 -> 返回 runId -> 轮询结果`。
- `runId` 是业务任务 ID，业务方只需要保存它。
- `taskId` 是底层能力任务 ID，仅用于排查和链路关联，不要求业务方理解。
- 业务版本由中台切默认版本；Coze 工具箱和业务方入参尽量保持不变。

## 鉴权

- 推荐使用 `Authorization: Bearer <SERVICE_API_TOKEN>`。
- Coze 同机/可信内网调用可通过 `COZE_TRUSTED_IPS` 或内网地址放行。
- 管理端业务能力接口仍要求管理员权限。

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
- 阻塞式 VL 串联会把 `promptCard.imageDesc` 回填到图裂变 `image_desc`，把 `promptCard.positivePrompt` 回填到图裂变/扩图 `prompt`；只有原请求未填写这些字段时才自动回填。

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

## 2) 提交图裂变

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

响应体：

```json
{
  "id": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "runId": "d7f2f7f37d1d47ad8dd2a9d7d3cb3d39",
  "businessKey": "fission",
  "version": "v1",
  "status": "queued",
  "source": "coze",
  "channel": "coze-workflow",
  "traceId": "trace-demo-001",
  "requestId": "req-demo-001",
  "tenantId": "tenant-a",
  "clientId": "coze-main-workflow",
  "taskId": "t1.fission.default.xxx",
  "imageUrls": [],
  "videoUrls": [],
  "texts": [],
  "error": null,
  "durationMs": null,
  "costAmount": null,
  "currency": null,
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
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `ABILITY_TASK_FAILED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `bili/width/height/image_desc/batch_size/steps/cfg` 直接作为顶层字段传入，业务方不用理解 `inputs`。
- 旧调用仍兼容 `inputs.bili`、`inputs.width` 等格式；顶层字段不会破坏现有 Coze 工作流。
- `traceId/requestId/tenantId/clientId/channel/source` 会进入业务运行记录，并继续透传到底层能力任务，后续用于排查、灰度、成本和配额统计。

---

## 3) 提交扩图

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
- `BUSINESS_CLIENT_CONCURRENCY_LIMITED`
- `BUSINESS_CLIENT_DAILY_RUN_LIMITED`
- `BUSINESS_CLIENT_DAILY_QUOTA_LIMITED`
- `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT`

说明：

- 新接入建议把 `expand_left/expand_right/expand_top/expand_bottom/width/height/timeout` 直接作为顶层字段传入。
- 旧调用仍兼容 `inputs.expand_left` 等格式。

---

## 4) 查询业务任务

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

终态响应示例：

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
      "abilityTaskId": "t1.outpaint.auto.xxx"
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

- `steps` 是业务配方步骤状态。当前版本至少记录主执行能力；启用 VL 辅助后会额外提交并记录 VL 步骤。
- 默认情况下最终出图仍以主执行能力为准，VL 伴随步骤用于链路观测和结果积累。
- 阻塞式 VL 串联开启后，主能力会等 VL 成功后再提交；查询时可能先看到 VL 运行中、主能力仍是 `planned`。
- `steps[].resultSummary` 只返回安全摘要，例如 VL 图片描述、提示词建议、图片/视频数量，不返回完整第三方原始响应或大字段。
- `durationMs/costAmount/currency/quotaUnits` 是成本与配额预留字段。现阶段以底层能力日志和厂商返回为准，缺失时返回 `null`，不会影响业务轮询。

---

## 5) VL 图像理解原子能力

VL 进入统一能力弹药库，能力 ID：

- `vl_analyze_image`

调用方式仍走统一能力接口：

- `POST /api/abilities/vl_analyze_image/invoke`
- 后续也可通过业务配方把 VL 作为图裂变/扩图的前置分析步骤。

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

## 6) OpenAPI 工具箱

### GET /api/business/openapi.json

用途：给 Coze 导入“业务层工具箱”。
当前包含：

- `podi_business_fission_run`
- `podi_business_outpaint_run`
- `podi_business_fission_route_preview`
- `podi_business_outpaint_route_preview`
- `podi_business_run_get`

OpenAPI 内每个工具都会枚举错误响应：

- `400`：缺少必要参数或业务配方非法，例如 `BUSINESS_IMAGE_URL_REQUIRED`、`BUSINESS_RUN_ID_REQUIRED`。
- `401`：缺少服务 Token 或不在可信内网，例如 `AUTHORIZATION_REQUIRED`。
- `403/404`：业务任务不可访问或不存在，例如 `BUSINESS_RUN_FORBIDDEN`、`BUSINESS_RUN_NOT_FOUND`。
- `429`：队列或并发限制。
- `403/429`：命中业务方配置限制，例如业务方停用、未开通该业务、日调用或并发达到上限。
- `500`：底层能力、ComfyUI 或第三方模型执行失败，例如 `COMFYUI_TIMEOUT`、`VENDOR_API_EXECUTION_FAILED`。

原则：

- Coze 新工作流优先调用业务 API，而不是在 Coze 内继续手搓底层编排。
- 旧 Coze workflow 不立即下线，继续保障当前业务接入稳定。
- 底层版本切换优先在中台改默认业务版本，避免业务方频繁换 workflow ID。

---

## 7) 管理端接口

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
  "allowedBusinessKeys": ["fission", "outpaint"],
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
- `allowedBusinessKeys` 为空表示不限制业务能力；填值后只允许调用这些业务，例如 `fission/outpaint`。
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

### GET /api/admin/business/capabilities

用途：管理端展示业务能力版本、发布时间、默认版本、配方来源。

响应会额外解析底层来源，便于非技术同学判断“这个业务版本到底在调用什么”：

- `primaryAbilityId` / `primaryAbilityName`：配方中的主原子能力。
- `vendorModelId` / `vendorModelName`：主原子能力绑定的模型目录项；没有绑定时为空。
- `latestRun`：该业务版本最近一次调用摘要，包含状态、时间、结果数量和错误摘要，供管理端快速判断版本健康度。
- `runMetrics`：该业务版本近 24 小时运行统计，包含总调用、成功、失败、排队、运行中、成功率，供默认版本切换前判断风险。

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
- 默认版本必须是 `active` 状态，避免业务入口指向不可用版本。
- 预置业务版本只负责初始化和补齐字段，不会在后续刷新时覆盖管理端已经切换的默认版本或启停状态。
- 核心业务必须至少保留一个 active 非默认保底版本；图裂变预置 `biz_fission_rollback_e7_flux2_liebian`，扩图预置 `biz_outpaint_rollback_huawen_kuotu`，用于默认版本异常时快速切回。
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
- 成功后同一个 `businessKey` 下其它版本会自动取消默认。
- 后端会在 `metadata.releaseEvents` 追加 `promote_default` 事件，记录切换原因、操作者和时间。

常见错误：

- `ADMIN_ONLY`
- `BUSINESS_CAPABILITY_NOT_FOUND`
- `BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE`

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
- 发版前必须执行 `backend/scripts/business_version_safety_audit.py`，确认图裂变、扩图都有 active 默认版本和 active 保底版本。

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

- `business_key`：可选，`fission` / `outpaint`
- `version`：可选，按业务版本过滤，例如 `v1`
- `status`：可选，按运行状态过滤，常见值为 `queued` / `running` / `succeeded` / `failed` / `cancelled`
- `source`：可选，按调用来源过滤，例如 `coze` / `client` / `partner-api`
- `tenant_id`：可选，按租户/业务方过滤
- `client_id`：可选，按客户端/应用过滤
- `trace_id`：可选，按调用链路 ID 精确查询
- `limit`：默认 50，最大 200

用途：查看最近业务运行记录，为后续统计、计费、灰度分析打基础。

记录字段：

- `traceId/requestId/tenantId/clientId/channel/source`：定位一次业务调用来自哪里、属于哪个业务方或客户端。
- `durationMs`：业务任务主链路耗时，终态后回填。
- `costAmount/currency/quotaUnits/costBreakdown`：成本和配额预留字段，后续收费系统会基于这些字段做正式账单。

### GET /api/admin/business/usage-summary

用途：按当前筛选统计业务调用量、成功率、失败样本、平均耗时、成本和额度消耗，给默认版本切换、灰度观察、后续收费报表使用。

参数：

- `window_hours`：统计窗口，默认 24，范围 1-2160。
- `business_key`：可选，`fission` / `outpaint`。
- `version`：可选，按业务版本过滤。
- `status`：可选，按运行状态过滤。
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
  "quotaUnits": 12,
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
      "quotaUnits": 12,
      "latestAt": "2026-04-25T10:00:00"
    }
  ],
  "bySource": [],
  "byTenant": [],
  "byClient": [],
  "byVersion": [],
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

常见错误：

- `AUTHORIZATION_REQUIRED`
- `ADMIN_ONLY`

说明：

- 统计接口只读业务运行记录，不触发任何任务重试。
- `costByCurrency/quotaUnits` 当前来自底层能力日志或任务结果回填；如果厂商没有返回成本信息，对应字段会为空或为 0。
- 管理端“业务能力”页的统计卡片、业务分布、来源/业务方分布和最近失败列表均来自该接口。
