# 原子能力调用 API

> 目标：为内部编排、测评端、管理端和高级开发提供统一入口，按能力 ID 调用已接入的厂商能力。
> 普通业务方正式接入优先使用 `/api/business/*`，不要直接对接本接口，除非单独约定为高级开发接入。
> 说明：接口字段保持统一，极少数能力可能只使用其中一部分，文档会注明差异。

## 鉴权

- 能力接口沿用系统登录逻辑，所有请求需携带 `Authorization: Bearer <accessToken>`。
- 若已配置 `SERVICE_API_TOKEN`，也可直接使用该 token（适用于内部服务间调用）。
- 获取方式：
  1. `POST /api/auth/login`，账号密码由管理员分配（不要在文档内写死真实账号）。
  2. 响应返回 `accessToken`/`refreshToken`，将 `accessToken` 放入后续能力接口的 Authorization 头中。
  3. `POST /api/auth/refresh` 可用 `refreshToken` 换新 `accessToken`。

## 1. 获取能力清单

- **URL**：`GET /api/abilities`
- **返回**：`AbilityListResponse`

```json
{
  "items": [
    {
      "id": "comfyui_yinhua_tiqu",
      "provider": "comfyui",
      "category": "image_generation",
      "capabilityKey": "yinhua_tiqu",
      "displayName": "ComfyUI · 印花提取",
      "description": "Qwen Image Edit + 印花 LoRA，输出 1800×1800 设计稿。",
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
      "inputSchema": { "...": "同管理端 schema" },
      "metadata": {
        "api_type": "comfyui_workflow",
        "requires_image_input": true,
        "workflow_key": "yinhua_tiqu"
      },
      "requiresImage": true,
      "supportsMultipleImages": false,
      "maxOutputImages": null,
      "lastHealthCheckAt": "2025-01-12T14:22:01Z",
      "lastHealthStatus": "healthy",
      "successRate": 0.97
    }
  ]
}
```

> 字段说明：
> - `defaultParams` 为当前默认参数（用于前端表单初始值）。
> - `inputSchema` 复用管理端 schema（字段名 + 类型 + 中英标签），客户端可动态渲染。
> - `abilityType` 指明调度方式（api/comfyui/workflow/tool），`workflowId` 可选绑定内部 Workflow，用于低代码编排。
> - `metadata` 里包含 `api_type/model_id/workflow_key` 等运行时信息。
> - `requiresImage / supportsMultipleImages / maxOutputImages` 可帮助 UI 决定是否展示上传控件与多图预览。
> - `lastHealthCheckAt/lastHealthStatus/successRate` 会在管理端实时测试或正式调用结束后自动汇总最近调用日志，调用方可据此判断能力稳定性；定时巡检后续会复用同一组字段。
> - 如需记录调用成本，可在 `metadata.pricing` 写入如下结构（单位/币种自定义）：
>
>   ```jsonc
>   "metadata": {
>     "pricing": {
>       "currency": "CNY",
>       "unit": "per_image",
>       "list_price": 0.5,
>       "discount_price": 0.3
>     }
>   }
>   ```
>
>   管理端会以 “折扣价/单位 · 对外价/单位” 的形式展示，并将其附在能力调用清单和日志中。ComfyUI 若未配置，则默认按 ¥0.30/每张估算。

### 获取单个能力

`GET /api/abilities/{abilityId}` 返回与列表项相同的结构，方便直接查询。

## 2. 调用指定能力

- **URL**：`POST /api/abilities/{abilityId}/invoke`
- **鉴权**：用户侧 Bearer Token，走 `get_current_user`
- **请求体**：`AbilityInvokeRequest`

```jsonc
{
  "executorId": "可选，覆盖能力默认节点",
  "inputs": {
    "prompt": "春日田野风景，布面油画风格",
    "output_width": 1024,
    "output_height": 1024,
    "lora_name": "YinHuaTiQu-LoRA-V2"
  },
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/xxx/input.png",
  "imageBase64": null,
  "images": [
    {
      "name": "reference-A",
      "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/xxx/refA.png"
    }
  ],
  "metadata": {
    "requestFrom": "podi-eval-web",
    "traceId": "optional-trace"
  }
}
```

> 约定：
> - `inputs`：能力特有参数，字段名称与 `inputSchema`+`defaultParams` 一致。
> - `imageUrl`/`imageBase64`：单图入口；`images[]`：用于多图流程（ComfyUI/KIE 会自动转成 `imageList` 或 `input.image_input`）。
> - `executorId`：一般不需要传，只有在多台 ComfyUI 节点做 A/B 测试时才会覆盖。
> - `metadata`：调用方自定义上下文（日志可见，不参与能力逻辑）。
> - **执行器必须配置**：每个能力都要在管理端（或 `/api/admin/abilities/{id}`）绑定一个可用的 `executor_id`，否则调用会返回 `400 ABILITY_EXECUTOR_NOT_CONFIGURED`。常见原因是执行节点尚未创建或被禁用。

#### 生产画布交付门禁

对需要进入实物生产的图片任务，业务端可在 `metadata.productionCanvas` 声明最终生产文件：

```json
{
  "enabled": true,
  "targetWidth": 2717,
  "targetHeight": 1476,
  "targetDpi": 150,
  "mode": "cover",
  "purpose": "agent_design_surface"
}
```

中台会在模型候选图回填到自有 OSS 后，统一归一为精确像素和 DPI，并执行预检。只有该步骤成功，异步能力任务才会进入 `succeeded`；结果会带 `_productionCanvas` 证据。配置非法或输出缺图时返回 `PRODUCTION_CANVAS_CONFIG_INVALID` / `PRODUCTION_CANVAS_SOURCE_MISSING`；归一或预检失败时任务保持失败，不扣成功费用，也不得进入设计篮或生产订单。

#### Packy · GPT Image 2（中台托管）

- 能力 ID：`packy_gpt_image_2_generate`、`packy_gpt_image_2_edit`；provider 固定为 `openai_compatible`，经本机 `vendor-api-ops` 调用。
- 配置：仅在中台运行环境设置 `OPENAI_COMPATIBLE_BASE_URL=https://www.packyapi.com` 与 `OPENAI_COMPATIBLE_API_KEY`。业务客户端不得持有或请求该密钥。
- 文生图：调用 `/v1/images/generations`，当前受控模型为 `gpt-image-2`，单次固定生成 1 张。
- 图片编辑：调用 `/v1/images/edits`，Packy 要求 multipart 字段名为 `image`，当前能力只接受 1 张主图。若输入额外参考图，返回 `VENDOR_API_INPUT_LIMIT_EXCEEDED`，不会静默忽略。
- 可选尺寸由能力 schema 限定为 Packy 已验证预设；进入实物生产仍必须通过生产画布交付门禁，不能用模型输出尺寸替代最终生产尺寸。
- 参考：[Packy GPT Image 文档](https://docs.packyapi.com/docs/paint/GPTImage.html)。

### KIE · Veo3.1 Fast 视频生成

- 能力：`provider=kie`，`capabilityKey=veo3_1_fast_video`
- 模型：后端强制 `model=veo3_fast`，调用方即使传入其他 `model` 也不会透传给 KIE。
- 提交接口：`/api/v1/veo/generate`
- 查询接口：`/api/v1/veo/record-info`
- 输入：
  - `prompt`：必填，描述镜头、动作、产品稳定性要求。
  - `imageUrl` 或 `images[]`：可选；提供后会整理为 KIE `imageUrls`，最多 3 张。
  - `inputs.generationType`：可选，`TEXT_2_VIDEO` / `FIRST_AND_LAST_FRAMES_2_VIDEO` / `REFERENCE_2_VIDEO`。无参考图时后端会自动改为 `TEXT_2_VIDEO`。
  - `inputs.aspectRatio`：可选，`16:9` / `9:16` / `Auto`。
  - `inputs.enableTranslation`：默认 `true`。
  - `inputs.enableFallback`：不作为表单能力开放；后端固定为 `false`，避免成本和效果不可控。
- 输出：
  - `videos[]` / `metadata.taskId`：统一能力响应会把视频结果归入 `videos`，同时保留 KIE 任务 ID。
  - 兼容字段 `resultUrls` 仍可能存在，但视频业务应优先读取 `videos` 或业务 API 的 `videoUrls`。
- 错误：复用 KIE 统一错误契约，如 `KIE_API_KEY_MISSING`、`KIE_TASK_CREATE_FAILED`、`KIE_TASK_ID_MISSING`、`KIE_STATUS_ERROR`、`KIE_TIMEOUT`。

#### 回调（可选）

- `callbackUrl`：如需异步通知，在请求体顶层提供 HTTPS 地址，服务端会在成功或失败后 POST 回执。仍会同步返回 `AbilityInvokeResponse`，回调只是额外通知。
- `callbackHeaders`：可传入字典（如 `{"Authorization":"Bearer xxx"}`）用于 webhook 鉴权。
- 回调 payload 示例：

```json
{
  "status": "success",
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "requestId": "f61f2dd0f7dd4f479e7d97f6b0fa0f8b",
  "logId": 12345,
  "durationMs": 842,
  "result": { ...AbilityInvokeResponse 同步返回体... },
  "error": null,
  "timestamp": "2025-01-12T08:12:34.567890+00:00"
}
```

失败时 `status`=`failed`，`error` 会包含 `status_code/detail`。

### 响应体：`AbilityInvokeResponse`

```json
{
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "status": "succeeded",
  "requestId": "f61f2dd0f7dd4f479e7d97f6b0fa0f8b",
  "logId": 12345,
  "durationMs": 842,
  "images": [
    {
      "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/xxx/output.png",
      "sourceUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/xxx/output.png",
      "type": "image"
    }
  ],
  "videos": null,
  "texts": null,
  "assets": [
    {
      "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/xxx/output.png",
      "tag": "comfyui-image"
    }
  ],
  "metadata": {
    "model": null,
    "state": null,
    "taskId": "prompt-87c5c0..."
  },
  "raw": {
    "...": "原始返回（剪裁敏感字段）"
  }
}
```

统一字段解释：

| 字段 | 说明 |
| ---- | ---- |
| `status` | 目前恒为 `succeeded`（同步接口）；后续扩展异步工作流时可能出现 `queued`/`running`。 |
| `requestId` | 服务器生成的链路 ID，可与日志、OSS 文件名关联。 |
| `logId` | `ability_invocation_logs` 主键；后台管理页“最近调用记录”模块也会显示。 |
| `durationMs` | 单次调用耗时，单位毫秒；同样写入日志表，可用于 SLA/统计。 |
| `images/videos` | 标准化输出资产（包含 `ossUrl`、原厂 `sourceUrl`、或 `base64`）。部分能力（如火山多图）会返回多个条目。 |
| `assets` | 对应 `media_ingest_service` 返回的完整资产列表（含 `tag/contentType/size`）。 |
| `metadata` | 轻量信息：模型 ID、KIE 任务 state、ComfyUI promptId 等。 |
| `raw` | 厂商原始响应（必要字段已脱敏/截断）。 |

### PODI 内部能力：连续图生产锁边

- 能力 ID：`podi_seamless_production_normalize`
- 用途：仅接收已通过平铺预览审核的二方/四方连续图候选，确定性锁定指定轴的首尾像素；它不负责生成花纹，也不能替代视觉接缝检查、目标尺寸适配或印刷生产校验。
- 请求：

```json
{
  "inputs": {
    "repeat_axis": "both",
    "tiled_review_confirmed": true
  },
  "imageUrl": "https://aichuangpin.oss-cn-hangzhou.aliyuncs.com/example/repeat-candidate.png"
}
```

- 响应：`images[0].ossUrl` 是锁边后的 PNG；`raw.request.edgeEvidence` 给出 horizontal/vertical 的 `before.meanAbs`、`before.maxAbs`、`after.meanAbs`、`after.maxAbs` 与 `lockedAxes`。只有处理后的目标轴 `maxAbs=0` 时才允许进入下一步生产画布适配。
- 错误：`SEAMLESS_REPEAT_AXIS_INVALID`、`SEAMLESS_TILED_REVIEW_REQUIRED`、`SEAMLESS_IMAGE_TOO_SMALL`、`SEAMLESS_IMAGE_TOO_LARGE`、`SEAMLESS_NORMALIZE_FAILED`、`SEAMLESS_NORMALIZE_UPLOAD_FAILED`。错误含义以 [错误码总表](../standards/error-catalog.md) 为准。

## 3. 异步任务模式

当一次要提交大量任务，或单次调用需要较长时间时，可使用任务队列接口。后端会将任务排队到线程池（默认 4 并发，可通过环境变量 `ABILITY_TASK_MAX_WORKERS` 调整），任务完成后可以轮询查询，也可以配置回调 URL。

### 3.1 创建任务

- **URL**：`POST /api/ability-tasks`
- **Body**：与同步调用完全一致，额外包含 `abilityId`

```jsonc
{
  "abilityId": "comfyui_yinhua_tiqu",
  "executorId": "executor_comfyui_pattern_extract_158",
  "inputs": { "...": "同 invoke" },
  "imageUrl": "https://.../input.png",
  "callbackUrl": "https://example.com/ability-callback",
  "callbackHeaders": {
    "Authorization": "Bearer webhook-token"
  }
}
```

### 3.2 返回

```json
{
  "id": "task_8c9a7d0be6b24652",
  "abilityId": "comfyui_yinhua_tiqu",
  "abilityName": "ComfyUI · 印花提取",
  "provider": "comfyui",
  "capabilityKey": "yinhua_tiqu",
  "status": "queued",
  "logId": null,
  "durationMs": null,
  "requestPayload": { "...": "原始入参，Base64 自动省略" },
  "resultPayload": null,
  "errorMessage": null,
  "callbackUrl": "https://example.com/ability-callback",
  "createdAt": "2025-01-12T08:12:00Z",
  "updatedAt": "2025-01-12T08:12:00Z",
  "startedAt": null,
  "finishedAt": null
}
```

任务状态值：

| 状态 | 说明 |
| --- | --- |
| `queued` | 已入队，等待执行 |
| `running` | 正在执行 |
| `succeeded` | 执行成功，`resultPayload` 为完整 `AbilityInvokeResponse` |
| `failed` | 执行失败，`errorMessage` 会包含错误描述 |

### 3.3 查询任务

- `GET /api/ability-tasks/{taskId}`：查询单个任务；非 admin 用户仅能查看自己的任务。
- `GET /api/ability-tasks?limit=20`：列出最近任务（默认按创建时间倒序）。

### 3.4 回调

提交同步或异步调用时都可以提供 `callbackUrl`，任务完成后会 POST：

```json
{
  "status": "success",
  "abilityId": "...",
  "provider": "...",
  "requestId": "f61f2dd0f7dd4f479e7d97f6b0fa0f8b",
  "taskId": "t1.comfyui.executor_xxx.f61f2dd0f7dd4f479e7d97f6b0fa0f8b",
  "logId": 12345,
  "durationMs": 842,
  "result": { "...AbilityInvokeResponse..." },
  "error": null,
  "timestamp": "2025-01-12T08:12:34.567890+00:00"
}
```

失败时 `status`=`failed`，`error` 会包含 `status_code/detail`。如需鉴权，在 `callbackHeaders` 中传入自定义 Header 即可。
`taskId` 字段为可解析格式（`t1.<provider>.<executorId>.<raw>`），用于快速定位执行节点。

### 各能力注意事项

#### 百度图像增强（provider=`baidu`）

| Ability ID | 功能 | 必填输入 | 可选参数 | 输出 |
| --- | --- | --- | --- | --- |
| `baidu_quality_upgrade` | 无损放大 2K/4K | `imageUrl` 或 `imageBase64` | `resolution`=`1k/2k/4k`，`type`=`auto/clarity/detail/texture` | 单张图片（base64 + OSS） |
| `baidu_colourize` | 老照片上色 | 同上 | 无 | 单张图片 |
| `baidu_remove_moire` | 摩尔纹去除 | 同上 | 无 | 单张图片 |
| `baidu_stretch_restore` | 拉伸修复 | 同上 | 无 | 单张图片 |
| `baidu_dehaze` | 去雾增强 | 同上 | 无 | 单张图片 |
| `baidu_contrast_enhance` | 对比度增强 | 同上 | 无 | 单张图片 |
| `baidu_denoise` | 去噪净化 | 同上 | 无 | 单张图片 |

> 以上能力均通过 `/rest/2.0/image-process` 系列接口实现，输出固定为 1 张图，`images[0].base64`/`assets[0].ossUrl` 可直接展示。

#### VL 组件（provider=`vl`）

| Ability ID | 功能 | 必填字段 | 可选字段 | 输出 |
| --- | --- | --- | --- | --- |
| `vl_analyze_image` | 通用图像结构化分析 | `image_url` 或 `imageUrl` | `prompt`、`provider`、`coze_workflow_id` | `texts[0]` 为结构化 JSON |
| `vl_fission_control_card` | 图裂变控制卡 | `image_url` 或 `imageUrl` | `provider`、`prompt`、`coze_workflow_id` | `fissionControlCard`，含 `prompt_main/prompt_control/control_cards` |
| `vl_fission_generated_image_evaluate` | 裂变生成图评估 | `original_image`、`generated_image` | `context`、`provider`、`coze_workflow_id` | `decision/score/scores/problem_tags/reason/next_action` |

> VL 组件是中台的集中入口。当前 `volcengine_vl` 默认映射到 `volcengine_doubao_seed_2_0_lite`（Doubao-Seed-2.0-lite）；后续如果更换 VL 模型，优先改 VL 组件的 `provider_ability_map`，依赖它的图裂变版本不需要逐个改配方。生成图评估只负责给出结果判断，不自动二次裂变。

#### 火山引擎（provider=`volcengine`）

| Ability ID | 功能 | 必填字段 | 其他输入 | 输出 |
| --- | --- | --- | --- | --- |
| `volcengine_doubao_seed_2_0_lite` | Doubao-Seed-2.0-lite VL（当前默认） | `prompt` | 可选 `imageUrl`/`inputs.image_url` 进行图文对话 | `texts[0]` |
| `volcengine_doubao_seed_1_8` | Doubao Seed 1.8 多模态对话 | `prompt` | 可选 `imageUrl`/`inputs.image_url` 进行图文对话 | `texts[0]` |
| `volcengine_doubao_seed_1_6_lite` | 轻量版多模态对话 | `prompt` | `imageUrl`、`reasoning_effort`、`max_completion_tokens` | `texts[0]` |
| `volcengine_doubao_seedream_4_5` | Seedream 4.5 文生图（支持参考图） | `prompt` | `image_urls`/`image_url`（参考图，可选）、`negative_prompt`、`size`、`width`、`height`、`response_format` | 图片数组 `images[]`（按 provider 实际返回） |
| `volcengine_doubao_seedream_4_0` | Seedream 4.0 文生图（支持参考图） | 同上 | 同上 | 图片数组 `images[]`（按 provider 实际返回） |
| `volcengine_doubao_seedance_1_5_pro` | Seedance 1.5 图生视频 | `prompt` | 可选 `imageUrl`、`duration`、`camera_fixed`、`watermark` | 视频链接（`videos[]`） |

> 参考图传参说明：PODI 会将 `image_urls/image_url` 同步写入火山参数 `reference_image_urls`（Ark API 识别的字段），用于图生图/风格参考。该参考属于“弱约束”，是否严格遵循取决于模型能力与提示词表达。
>
> 成本字段（估算，CNY，已写入 `metadata.pricing`）：
> - 对话类：`¥0.05 / 次`（对外价 `¥0.08`）
> - 图像类：`¥0.30 / 张`（对外价 `¥0.45`）
> - 视频类：`¥1.50 / 次`（对外价 `¥2.00`）

#### KIE 市场模型（provider=`kie`）

| Ability ID | 类型 | 必填字段 | 可选字段 | 特性 |
| --- | --- | --- | --- | --- |
| `kie_nano_banana_pro_image_to_image` | 图生图 | `prompt` + `image_url` 至少 1 张 | `image_urls`（可选多参考图）、`aspect_ratio`、`resolution`、`output_format`、`callBackUrl` | 支持 1~多张参考图；输出 `resultUrls` |
| `kie_nano_banana_2_lite_image_to_image` | 图生图（轻量编辑） | `prompt` + `image_url` | `image_urls`、`aspect_ratio`、`callBackUrl` | KIE Nano Banana 2 Lite，适合低成本快速试图 |
| `kie_gpt_image_2_text_to_image` | 文生图 | `prompt` | `aspect_ratio`、`callBackUrl` | KIE 中转 GPT Image 2 文生图；不替代 OpenAI 官方直连能力 |
| `kie_gpt_image_2_image_to_image` | 图生图 / 图片编辑 | `prompt` + `image_url` | `image_urls`、`aspect_ratio`、`callBackUrl` | KIE 中转 GPT Image 2 图生图，主图和补充参考图会写入 `input_urls` |
| `kie_flux2_pro_image_to_image` | 图生图（Flux-2） | `prompt` + `image_urls/input_urls` 至少 1 条 | `aspect_ratio`、`resolution`、`callBackUrl` | 必须提供 1~8 张参考图 |
| `kie_sora2_pro_text_to_video` | 文生视频 | `prompt` | `aspect_ratio`、`n_frames`、`size`、`remove_watermark`、`character_ids`、`callBackUrl` | 输出视频 URL + 任务状态 |

> `image_url` 会作为主图；`image_urls` / `input_urls` 字段允许多行或 JSON 数组，接口会拆成数组并写入对应模型的输入数组（例如 GPT Image 2 图生图为 `input_urls`，Nano Banana 2 Lite 为 `image_urls`）。返回体 `metadata` 携带 KIE 任务 `taskId/state`，`resultUrls` / `imageUrls` 为官方 CDN，`assets` 为落地后的 OSS。
>
> 成本字段（估算，USD，已写入 `metadata.pricing/pricing_tiers`）：
> - Nano Banana Pro：1K/2K `$0.04`，4K `$0.07`
> - Flux-2 Pro：1K `$0.025`，2K `$0.035`
> - Sora2 Pro：10s `$0.375`，15-25s `$0.675`

#### ComfyUI 工作流（provider=`comfyui`）

| Ability ID | 功能 | 必填字段 | 可选参数 | 输出 |
| --- | --- | --- | --- | --- |
| `comfyui_sifang_lianxu` | 四方连续纹理生成 | `image_url`（或上传图片）、`workflow_key` | `prompt`、`patternType`(`seamless/twoway`)、`resolution`、`width/height` 等 | 1 张 seamless 纹理 |
| `comfyui_yinhua_tiqu` | 印花提取 | `image_url` + `workflow_key` | `prompt`、`negative_prompt`、`output_width/height`、`lora_name`（支持从 UI 下拉选择） | 1800×1800 设计稿 |
| `comfyui_flux_strong_hq_softstyle_fission_control_v1` | VL 控制卡裂变 | `image_url`、`vl_result` | `width`、`height`、`bili`(`50%`)、`profile`、`seed` | 1 张裂变图 |
| `comfyui_flux_strong_hq_softstyle_fission_colorlock_v2` | VL 颜色锁定裂变 | `image_url`、`vl_result` | `width`、`height`、`bili`(`80%`)、`profile`(`pattern_risk_routed_v4`)、`reference_lock`、`color_lock` | 1 张裂变图 |

> ComfyUI 能力会自动把上传的 OSS 地址写入 workflow `imageList`，并把厂商输出文件落盘到 OSS；`metadata.taskId` 为 prompt ID。未来若 ComfyUI 服务暴露更多模型/LoRA，前端会根据 `/api/admin/comfyui/models` 下拉选择。
>
> 颜色锁定裂变 v2 已按 2026-05-14 修补包升级为智能风险路由：`bili` 不再强行限制在 0%-20%，后端根据 `pattern_risk_type + bili` 路由实际 `denoise`。`reference_lock` 映射 IPAdapter 权重，建议 0.34-0.50；`color_lock` 映射 ColorMatch 强度，建议 0.75-1.00。建议区间只用于文案提示，不作为接口硬拦截。

#### 其他能力成本基线（估算）

- Baidu 图像处理：`¥0.10 / 张`（对外价 `¥0.15`）
- PODI 工具类（扩边/设置 DPI/缩放）：`¥0.02 / 张`（对外价 `¥0.03`）
- 如需发版前巡检，请执行：`python3 backend/scripts/audit_ability_pricing.py`

### 日志与耗时

- 每次调用 `/api/abilities/{id}/invoke` 都会在 `ability_invocation_logs` 中写一条记录，成功/失败均包含 `duration_ms`、存储后的 OSS 链接、原始请求/响应摘要。
- 日志新增 `traceId/workflowRunId` 便于串联上下游链路，`billingUnit/unitPrice/costAmount/currency` 用于成本对账（若 metadata.pricing 未配置则回退为默认值，如 ComfyUI 按 ¥0.30/张估算）。
- 可通过管理端 `/api/admin/abilities/{id}/logs` 查看最近调用记录，或在数据库中按 `ability_provider/capability_key` 统计平均耗时。
- `durationMs` 字段也随响应返回，方便调用方在客户端埋点或直接展示执行时间。

## 4. 常见错误与排查

统一能力接口使用统一错误响应（参照 `docs/standards/error-catalog.md` 与 `docs/standards/error-contract.md`）。其中 ABILITY 模块最常见，可据此快速定位问题：

| 错误码 | 触发场景 | 排查建议 |
| --- | --- | --- |
| `ABILITY_001` 能力未绑定可用执行节点 | 管理端未配置 `executor_id` 或节点被禁用 | 在“能力管理”绑定一个 `active` 节点，或执行 `ensure_default_executors`/`ensure_default_abilities`。 |
| `ABILITY_004` 输入参数不合法 | 缺少图片、select 值不在枚举内等 | 对照 `inputSchema` 检查字段；ComfyUI 多图输入需以多行文本或 JSON 数组传递。 |
| `ABILITY_006` AbilityTask 排队中 | 线程池或单节点 `max_concurrency` 已满 | 等待队列或切换其他节点；ComfyUI 节点可查看 `/api/admin/comfyui/queue-status`。 |
| `ABILITY_007` 执行节点不可达 | 网络/鉴权失败，或第三方超时 | 检查执行节点 `baseUrl`、API Key、网络连通性；管理端“执行节点”页可做连通性测试。 |
| `ABILITY_008` 第三方返回错误 | 厂商接口报错 | 查看 `error.details` 中的原始错误码并参考厂商文档。 |
| `ABILITY_010` ComfyUI 队列异常 | `/queue/status` 无响应或节点挂掉 | 检查 ComfyUI 服务器状态；必要时切换到备用节点。 |
| `ABILITY_011` 能力成本配置缺失 | `metadata.pricing` 未设置且无默认值 | 在 `app/constants/abilities.py` 或管理端为能力配置 `pricing`。 |

前端可根据 `error.code` 提示具体操作（示例见 `docs/standards/error-contract.md`）。如需进一步排查：
- 查看 `ability_invocation_logs` 或 `/api/admin/abilities/{id}/logs`，日志中会有 `requestPayload/responsePayload` 摘要与 `error_detail`；
- 对 ComfyUI 能力，结合 `/api/admin/comfyui/queue-status` 与服务器日志判断是否卡在队列；
- 若配置了 `callbackUrl`，失败时会在回调 payload 的 `error` 中看到 `status_code/detail`。

## 5. 工作流接口（规划）

- **URL（占位）**：`POST /api/workflows/{workflowId}/execute`
- 与能力接口保持一致的 `inputs/images/metadata` 结构，只是 `workflowId` 指向我们自定义组合（例如“图裂变工作流”会在内部串联 VL 识别 + ComfyUI 扩散）。
- 待工作流调度层完成后再发布。

---

> 实施建议：
> 1. 所有新增能力必须在 `app/constants/abilities.py` 中维护好 `defaults/input_schema/metadata`，才能自动出现在 `GET /api/abilities` 列表。
> 2. 若能力存在多输出、特殊输入，优先在 metadata 中补充 `max_output_images`、`input_array_target` 等信息，便于客户端读取。
> 3. 正式对外开放前，可结合 `ability_invocation_logs` 做调用风控/配额统计。
