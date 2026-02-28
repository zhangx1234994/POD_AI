# Coze 插件接口

> 工具箱总清单见：`docs/coze/toolbox-inventory.md`
> 开发准则见：`docs/standards/coze-toolbox-development-standard.md`

## 用途

- 将 PODI 能力以 Coze Studio Tools 形式暴露。
- 提供统一的“提交 + 回调查询 + 队列状态”能力。

## 鉴权

- **内网访问优先**：由 `COZE_TRUSTED_IPS` 放行。
- **或使用服务 Token**：`Authorization: Bearer <SERVICE_API_TOKEN>`。
- 未命中内网/Token 时返回 `INTERNAL_ONLY`。

---

## 1) OpenAPI 文档

### GET /api/coze/podi/openapi.json

**用途**：Coze 插件导入的 OpenAPI 地址。

**示例**

```bash
curl http://127.0.0.1:8099/api/coze/podi/openapi.json
```

### GET /api/coze/podi/comfyui/lora/openapi.json

**用途**：LoRA 查询专用工具箱（仅含零参数接口 `POST /api/coze/podi/comfyui/lora-catalog/default`，不含任何执行能力）。

**示例**

```bash
curl http://127.0.0.1:8099/api/coze/podi/comfyui/lora/openapi.json
```

### GET /api/coze/podi/kie/catalog/openapi.json

**用途**：KIE 模型查询专用工具箱（仅查询模型与参数，不执行生图/生视频）。

**示例**

```bash
curl http://127.0.0.1:8099/api/coze/podi/kie/catalog/openapi.json
```

### GET /api/coze/podi/kie/catalog/{model_key}/openapi.json

**用途**：单模型专用工具箱（每个模型一个独立工具箱，零参数查询 schema）。

**示例**

```bash
curl http://127.0.0.1:8099/api/coze/podi/kie/catalog/nano-banana-pro-image-to-image/openapi.json
```

### GET /api/coze/podi/kie/execute/{model_key}/openapi.json

**用途**：单模型执行工具箱（提交任务 + 任务轮询）。

**示例**

```bash
curl http://127.0.0.1:8099/api/coze/podi/kie/execute/nano-banana-2-image-to-image/openapi.json
```

---

## 2) 能力列表（可选）

### GET /api/coze/podi/abilities

**用途**：返回可导入 Coze 的能力列表（等同能力清单）。

---

## 3) 调用能力（Tool）

### POST /api/coze/podi/tools/{provider}/{capability_key}

**用途**：执行指定能力（Coze 工具调用）。

**请求体（示例）**

```json
{
  "prompt": "印花提取",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png",
  "output": "callback"
}
```

**响应体（示例）**

```json
{
  "text": null,
  "imageUrl": null,
  "imageUrls": [],
  "taskId": "t1.comfyui.executor_xxx.0e860bd7681542dda28fcc001b2cf372",
  "taskStatus": "running",
  "executorId": "executor_comfyui_xxx",
  "executorName": "ComfyUI-主节点"
}
```

**错误（常见）**

- `INTERNAL_ONLY`
- `ABILITY_NOT_FOUND` / `ABILITY_INACTIVE`
- `EXECUTOR_NOT_FOUND` / `EXECUTOR_TYPE_NOT_*`
- `Q1001` / `Q2001`（队列满）

---

## 4) 查询任务结果

### POST /api/coze/podi/tasks/get

**用途**：轮询异步任务结果（回调 id）。

**请求体**

```json
{ "taskId": "t1.comfyui.executor_xxx.0e860bd7681542dda28fcc001b2cf372" }
```

**响应体（示例）**

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png",
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png"],
  "taskId": "t1.comfyui.executor_xxx.0e860bd7681542dda28fcc001b2cf372",
  "taskStatus": "succeeded",
  "executorId": "executor_comfyui_xxx",
  "executorName": "ComfyUI-主节点",
  "logId": 12345,
  "requestId": "req_7d0f...",
  "debugResponse": null
}
```

**说明**

- `taskId` 兼容新旧格式：`t1.<provider>.<executor>.<hex>` 或 `<hex>`。
- 若任务仍在运行，`taskStatus=running` 且 `imageUrls` 为空。
- KIE 长耗时任务会先返回 `running`，后续轮询直至有结果或 `KIE_TIMEOUT`。
- `taskStatus` 对外统一为：`queued` / `running` / `succeeded` / `failed`。
- 队列强约束错误统一返回：`taskId = ERR|Qxxxx|...` 且 `taskStatus = failed`。

**错误**

- `TASK_ID_REQUIRED` / `TASK_NOT_FOUND`
- `TASK_FAILED` / `TASK_TIMEOUT` / `KIE_TIMEOUT`
- `ERR|Q1001|...` / `ERR|Q2001|...`（队列与并发限制，写在 taskId）

---

## 5) ComfyUI 队列汇总

### POST /api/coze/podi/comfyui/queue-summary

**用途**：返回多节点队列状态，用于 Coze 工作流路由。

**响应体（示例）**

```json
{
  "totalRunning": 2,
  "totalPending": 4,
  "servers": [
    { "executorId": "executor_comfyui_xxx", "running": 1, "pending": 2 }
  ]
}
```

**错误**

- `COMFYUI_QUEUE_STATUS_ERROR` / `COMFYUI_QUEUE_STATUS_INVALID`

---

## 6) ComfyUI LoRA 查询（独立工具）

### POST /api/coze/podi/comfyui/lora-catalog/default

**用途**

- 零参数直接返回 LoRA 目录（默认 `status=active`）。
- 给 Coze 非技术同学直接用，不需要填筛选参数。

**请求体（可选）**

```json
{
  "status": "active",
  "baseModel": "",
  "limit": 500
}
```

不传也可直接调用。

**响应体**

- 与 `/api/coze/podi/comfyui/lora-catalog` 相同。

---

### POST /api/coze/podi/comfyui/lora-catalog

**用途**

- 独立查询当前 LoRA 目录（给开发/工作流工具箱直接使用）。
- 可按 `baseModel`（基座模型）筛选，避免模型与 LoRA 不匹配。
- 传 `executorId` 时会返回该服务器安装状态（`installed=true/false`）。

**请求体（示例）**

```json
{
  "executorId": "executor_comfyui_seamless_117",
  "baseModel": "qwen_image_edit",
  "q": "印花",
  "status": "active",
  "installedOnly": false,
  "includeUntracked": true,
  "limit": 500
}
```

**响应体（示例）**

```json
{
  "executorId": "executor_comfyui_seamless_117",
  "baseUrl": "http://117.50.216.233:8079",
  "count": 2,
  "installedCount": 1,
  "loraNames": ["杯子1124.safetensors", "印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors"],
  "untrackedNames": ["new_lora_xxx.safetensors"],
  "items": [
    {
      "fileName": "杯子1124.safetensors",
      "displayName": "杯子1124.safetensors",
      "status": "active",
      "installed": true,
      "baseModels": ["qwen_image_edit"],
      "tags": ["提取", "印花"]
    }
  ]
}
```

**说明**

- `loraNames` 可直接给工具箱做下拉选项。
- `includeUntracked=true` 时会额外返回服务器已安装、但目录尚未建档的 LoRA（`untrackedNames`）。
- 若未传 `executorId`，只返回目录数据，不做“是否安装”判定。

---

## 7) KIE 模型查询（独立工具）

> 该工具箱用于“动态拉模型参数”，方便 Coze/业务侧按模型渲染入参，不替代现有执行接口。

**参数明细（查询工具箱）**

| 接口 | 是否必填请求体 | 参数 |
| --- | --- | --- |
| `POST /api/coze/podi/kie/models/list/default` | 否 | `mediaType`、`status`、`q`（可不传，默认 `all+active`） |
| `POST /api/coze/podi/kie/models/list` | 否 | `mediaType`、`status`、`q` |
| `POST /api/coze/podi/kie/models/schema` | 是 | `modelKey` |
| `POST /api/coze/podi/kie/models/{model_key}/schema` | 否 | 无（模型写在 URL） |

### POST /api/coze/podi/kie/models/list

**用途**

- 列出 KIE 可用模型（图片/视频分开）。
- 返回每个模型的 `modelKey`、参数能力概览、文档地址、能力映射信息。

**请求体（示例）**

```json
{
  "mediaType": "image",
  "status": "active",
  "q": "banana"
}
```

### POST /api/coze/podi/kie/models/list/default

**用途**

- 零参数返回结构化模型列表（默认 `mediaType=all`、`status=active`）。
- 推荐 Coze 工具箱直接使用这个接口，避免参数配置错误。

**请求体（可选）**

```json
{
  "mediaType": "all",
  "status": "active",
  "q": ""
}
```

不传也可直接调用。

**响应体（示例）**

```json
{
  "count": 2,
  "items": [
    {
      "modelKey": "nano_banana_pro_image_to_image",
      "displayName": "Nano Banana Pro 图生图",
      "providerModel": "nano-banana-pro",
      "mediaType": "image",
      "status": "active",
      "abilityKey": "nano_banana_pro_image_to_image",
      "docsUrl": "https://kie.ai/zh-CN/nano-banana-pro"
    }
  ]
}
```

### POST /api/coze/podi/kie/models/schema

**用途**

- 按 `modelKey` 查询标准化参数结构。
- 同时返回 Coze 封装建议（必填参数、分隔规则、payload 模板）。

**请求体（示例）**

```json
{
  "modelKey": "nano_banana_pro_image_to_image"
}
```

**响应体（示例）**

```json
{
  "model": {
    "modelKey": "nano_banana_pro_image_to_image",
    "mediaType": "image",
    "fields": [
      { "name": "prompt", "type": "string", "required": true },
      { "name": "url", "type": "string", "required": true },
      { "name": "image_urls", "type": "string_list", "required": false }
    ]
  },
  "cozeSuggestion": {
    "requiredParams": ["prompt", "url"],
    "transformRules": [
      "`url` 为主图（图1）；`image_urls` 按顺序映射为图2、图3...",
      "`image_urls` 建议用换行分隔；也支持逗号分隔（仅在 http 前拆分）"
    ],
    "payloadTemplate": {
      "modelKey": "nano_banana_pro_image_to_image",
      "inputs": { "prompt": "", "url": "", "image_urls": "" }
    }
  }
}
```

**错误**

- `KIE_MODEL_KEY_REQUIRED`
- `KIE_MODEL_NOT_FOUND`

---

### POST /api/coze/podi/kie/models/{model_key}/schema

**用途**

- 单模型零参数查询接口（用于“一个模型一个工具箱”）。
- 适配 `model_key` 支持 `-` 与 `_` 两种写法。

**请求体**

- 无

**示例**

```bash
curl -X POST http://127.0.0.1:8099/api/coze/podi/kie/models/nano-banana-pro-image-to-image/schema
```

---

## 8) 最近新增工具箱（参数速查）

> 更新时间：2026-03-01

| 工具箱 | OpenAPI | 主要接口 | 必填参数 | 说明 |
| --- | --- | --- | --- | --- |
| ComfyUI LoRA 查询 | `/api/coze/podi/comfyui/lora/openapi.json` | `POST /api/coze/podi/comfyui/lora-catalog/default` | 无 | 零参数，直接返回 LoRA 清单 |
| KIE 模型查询 | `/api/coze/podi/kie/catalog/openapi.json` | `POST /api/coze/podi/kie/models/list/default` | 无 | 零参数，返回结构化模型列表 |
| KIE 单模型参数查询 | `/api/coze/podi/kie/catalog/{model_key}/openapi.json` | `POST /api/coze/podi/kie/models/{model_key}/schema` | 无 | 一模型一工具箱，直接出 schema |
| KIE 单模型执行（示例：Nano Banana 2） | `/api/coze/podi/kie/execute/nano-banana-2-image-to-image/openapi.json` | `POST /api/coze/podi/tools/kie/nano_banana_2_image_to_image` | `prompt`、`url` | 提交执行任务，结果用 `/tasks/get` 轮询 |
