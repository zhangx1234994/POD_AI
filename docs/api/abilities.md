# 能力调用 API

> 目标：为客户端（前台 UI、自动化脚本、第三方应用）提供统一入口，按能力 ID 调用已接入的厂商能力。  
> 说明：接口字段保持统一，极少数能力可能只使用其中一部分，文档会注明差异。

## 鉴权

- 能力接口沿用系统登录逻辑，所有请求都需携带 `Authorization: Bearer <accessToken>`。
- 获取方式：
  1. `POST http://localhost:8099/api/auth/login`，请求体（示例账号）：`{"username":"admin","password":"Admin123"}`。
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
        "lora_name": "印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors"
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
> - `lastHealthCheckAt/lastHealthStatus/successRate` 会在管理端巡检后更新，调用方可据此判断能力稳定性。
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
    "requestFrom": "podi-design-web",
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
  "logId": 12345,
  "durationMs": 842,
  "result": { "...AbilityInvokeResponse..." },
  "error": null,
  "timestamp": "2025-01-12T08:12:34.567890+00:00"
}
```

失败时 `status`=`failed`，`error` 会包含 `status_code/detail`。如需鉴权，在 `callbackHeaders` 中传入自定义 Header 即可。

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

#### 火山引擎（provider=`volcengine`）

| Ability ID | 功能 | 必填字段 | 其他输入 | 输出 |
| --- | --- | --- | --- | --- |
| `volcengine_doubao_seed_1_8` | Doubao Seed 1.8 多模态对话 | `prompt` | 可选 `imageUrl`/`inputs.image_url` 进行图文对话 | `texts[0]` |
| `volcengine_doubao_seed_1_6_lite` | 轻量版多模态对话 | `prompt` | `imageUrl`、`reasoning_effort`、`max_completion_tokens` | `texts[0]` |
| `volcengine_doubao_seedream_4_5` | Seedream 4.5 文生图 | `prompt` | `negative_prompt`、`size`、`ratio`、`width`、`height`、`response_format` | 1~4 张图，`images[]` |
| `volcengine_doubao_seedream_4_0` | Seedream 4.0 文生图 | 同上 | 同上 | 1~4 张图 |
| `volcengine_doubao_seedance_1_5_pro` | Seedance 1.5 图生视频 | `prompt` | 可选 `imageUrl`、`duration`、`camera_fixed`、`watermark` | 视频链接（`videos[]`） |

#### KIE 市场模型（provider=`kie`）

| Ability ID | 类型 | 必填字段 | 可选字段 | 特性 |
| --- | --- | --- | --- | --- |
| `kie_nano_banana_pro_image_to_image` | 图生图 | `prompt` | `image_urls`（自动写入 `input.image_input`，可为空）、`aspect_ratio`、`resolution`、`output_format`、`callBackUrl` | 支持 0~多张参考图；输出 `resultUrls` |
| `kie_flux2_pro_image_to_image` | 图生图（Flux-2） | `prompt` + `image_urls/input_urls` 至少 1 条 | `aspect_ratio`、`resolution`、`callBackUrl` | 必须提供 1~8 张参考图 |
| `kie_sora2_pro_text_to_video` | 文生视频 | `prompt` | `aspect_ratio`、`n_frames`、`size`、`remove_watermark`、`character_ids`、`callBackUrl` | 输出视频 URL + 任务状态 |

> `image_urls` / `input_urls` 字段允许多行或 JSON 数组，接口会拆成数组并写入 `input_array_target`。返回体 `metadata` 携带 KIE 任务 `taskId/state`，`resultUrls` 为官方 CDN，`assets` 为落地后的 OSS。

#### ComfyUI 工作流（provider=`comfyui`）

| Ability ID | 功能 | 必填字段 | 可选参数 | 输出 |
| --- | --- | --- | --- | --- |
| `comfyui_sifang_lianxu` | 四方连续纹理生成 | `image_url`（或上传图片）、`workflow_key` | `prompt`、`patternType`(`seamless/twoway`)、`resolution`、`width/height` 等 | 1 张 seamless 纹理 |
| `comfyui_yinhua_tiqu` | 印花提取 | `image_url` + `workflow_key` | `prompt`、`negative_prompt`、`output_width/height`、`lora_name`（支持从 UI 下拉选择） | 1800×1800 设计稿 |

> ComfyUI 能力会自动把上传的 OSS 地址写入 workflow `imageList`，并把厂商输出文件落盘到 OSS；`metadata.taskId` 为 prompt ID。未来若 ComfyUI 服务暴露更多模型/LoRA，前端会根据 `/api/admin/comfyui/models` 下拉选择。

### 日志与耗时

- 每次调用 `/api/abilities/{id}/invoke` 都会在 `ability_invocation_logs` 中写一条记录，成功/失败均包含 `duration_ms`、存储后的 OSS 链接、原始请求/响应摘要。
- 日志新增 `traceId/workflowRunId` 便于串联上下游链路，`billingUnit/unitPrice/costAmount/currency` 用于成本对账（若 metadata.pricing 未配置则回退为默认值，如 ComfyUI 按 ¥0.30/张估算）。
- 可通过管理端 `/api/admin/abilities/{id}/logs` 查看最近调用记录，或在数据库中按 `ability_provider/capability_key` 统计平均耗时。
- `durationMs` 字段也随响应返回，方便调用方在客户端埋点或直接展示执行时间。

## 4. 常见错误与排查

统一能力接口使用统一错误响应（参照 `docs/error-codes.md`）。其中 ABILITY 模块最常见，可据此快速定位问题：

| 错误码 | 触发场景 | 排查建议 |
| --- | --- | --- |
| `ABILITY_001` 能力未绑定可用执行节点 | 管理端未配置 `executor_id` 或节点被禁用 | 在“能力管理”绑定一个 `active` 节点，或执行 `ensure_default_executors`/`ensure_default_abilities`。 |
| `ABILITY_004` 输入参数不合法 | 缺少图片、select 值不在枚举内等 | 对照 `inputSchema` 检查字段；ComfyUI 多图输入需以多行文本或 JSON 数组传递。 |
| `ABILITY_006` AbilityTask 排队中 | 线程池或单节点 `max_concurrency` 已满 | 等待队列或切换其他节点；ComfyUI 节点可查看 `/api/admin/comfyui/queue-status`。 |
| `ABILITY_007` 执行节点不可达 | 网络/鉴权失败，或第三方超时 | 检查执行节点 `baseUrl`、API Key、网络连通性；管理端“执行节点”页可做连通性测试。 |
| `ABILITY_008` 第三方返回错误 | 厂商接口报错 | 查看 `error.details` 中的原始错误码并参考厂商文档。 |
| `ABILITY_010` ComfyUI 队列异常 | `/queue/status` 无响应或节点挂掉 | 检查 ComfyUI 服务器状态；必要时切换到备用节点。 |
| `ABILITY_011` 能力成本配置缺失 | `metadata.pricing` 未设置且无默认值 | 在 `app/constants/abilities.py` 或管理端为能力配置 `pricing`。 |

前端可根据 `error.code` 提示具体操作（示例见 `docs/error-codes.md`）。如需进一步排查：
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
