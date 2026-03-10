# Coze 工具箱清单（PODI）

> 更新时间：2026-03-05
> 
> 说明：以下为当前后端实际可用的工具箱入口。导入 Coze 时使用 OpenAPI 地址；执行时按各工具箱里的接口调用。

## 地址前缀

- 线上地址前缀：`http://117.50.80.158:8099`
- 本地地址前缀：`http://127.0.0.1:8099`

## 1) 通用能力工具箱（执行类）

- OpenAPI：`/api/coze/podi/openapi.json`
- 用途：聚合全部 provider 的执行工具（按能力自动生成）。
- 鉴权：仅内网或 `SERVICE_API_TOKEN`

## 2) PODI 工具工具箱（执行类）

- OpenAPI：`/api/coze/podi/utils/openapi.json`
- 用途：仅 PODI 自研工具（如图像辅助工具）
- 鉴权：仅内网或 `SERVICE_API_TOKEN`

## 3) ComfyUI 工具箱（执行类）

- OpenAPI：`/api/coze/podi/comfyui/openapi.json`
- 用途：ComfyUI 能力执行 + `tasks/get` 轮询
- 鉴权：仅内网或 `SERVICE_API_TOKEN`

## 4) ComfyUI LoRA 查询工具箱（查询类）

- OpenAPI：`/api/coze/podi/comfyui/lora/openapi.json`
- 用途：查询 LoRA 目录、安装状态、基座筛选
- 鉴权：
  - OpenAPI：公开可访问（便于 Coze 导入）
  - 查询接口：仅内网或 `SERVICE_API_TOKEN`
- 关键接口：
  - `POST /api/coze/podi/comfyui/lora-catalog/default`（零参数，推荐）
  - `POST /api/coze/podi/comfyui/lora-catalog`（高级筛选）
- 返回字段兼容：
  - LoRA 名称数组同时返回 `loraNames` 与 `lora_names`（推荐读取 `lora_names`）
  - 未建档 LoRA 同时返回 `untrackedNames` 与 `untracked_names`
- 参数明细：
  - `lora-catalog/default`：可空参；也支持 `status/baseModel/limit/functionalOnly`（均可选，`functionalOnly` 默认 true）
  - `lora-catalog`：`executorId`（可选），`baseModel`（可选），`q`（可选），`status`（可选），`installedOnly`（可选），`includeUntracked`（可选），`limit`（可选），`functionalOnly`（可选）

## 5) KIE 工具箱（执行类）

- OpenAPI：`/api/coze/podi/kie/openapi.json`
- 用途：KIE 模型执行（图像/视频）
- 鉴权：仅内网或 `SERVICE_API_TOKEN`

## 6) KIE 模型查询工具箱（查询类）

- OpenAPI：`/api/coze/podi/kie/catalog/openapi.json`
- 用途：查询 KIE 模型参数、枚举、默认值、Coze 封装建议
- 鉴权：
  - OpenAPI：公开可访问（便于 Coze 导入）
  - 查询接口：仅内网或 `SERVICE_API_TOKEN`
- 关键接口：
  - `POST /api/coze/podi/kie/models/list/default`（零参数，推荐）
  - `POST /api/coze/podi/kie/models/list`（高级筛选）
  - `POST /api/coze/podi/kie/models/schema`
  - `POST /api/coze/podi/kie/models/{model_key}/schema`（单模型零参数）
- 返回字段兼容：
  - 模型键同时返回 `modelKeys` 与 `model_keys`
  - 媒体类型同时返回 `mediaTypes` 与 `media_types`
- 参数明细：
  - `models/list/default`：可空参；也支持 `mediaType/status/q`（均可选，默认 `all+active`）
  - `models/list`：`mediaType`（可选：`all|image|video`）、`status`（可选：`active|preview|all`）、`q`（可选）
  - `models/schema`：`modelKey`（必填）
  - `models/{model_key}/schema`：无参数（模型写在 URL）

### 6.1 KIE 单模型工具箱（查询类，按模型拆分）

- OpenAPI 模板：`/api/coze/podi/kie/catalog/{model_key}/openapi.json`
- 示例：`/api/coze/podi/kie/catalog/nano-banana-pro-image-to-image/openapi.json`
- 用途：每个模型独立一个工具箱，便于业务按需发布/灰度。

### 6.2 KIE 单模型执行工具箱（执行类，按模型拆分）

- OpenAPI 模板：`/api/coze/podi/kie/execute/{model_key}/openapi.json`
- 示例：`/api/coze/podi/kie/execute/nano-banana-2-image-to-image/openapi.json`
- 用途：每个模型一个执行工具箱，入参与该模型能力 schema 一致，避免“查询工具箱误当执行工具箱”。
- 参数明细（以 Nano Banana 2 为例）：
  - 工具路径：`POST /api/coze/podi/tools/kie/nano_banana_2_image_to_image`
  - 必填：`prompt`、`url`
  - 可选：`image_urls`、`aspect_ratio`、`resolution`、`output`

---

## 最近新增/调整（重点给 Coze 配置）

### 2026-02-28
- 新增：KIE 单模型执行工具箱 `.../kie/execute/{model_key}/openapi.json`
- 新增：`nano_banana_2_image_to_image` 执行能力（支持 `url` + `image_urls`）

### 2026-03-01
- 调整：KIE 查询工具箱默认入口改为 `POST /api/coze/podi/kie/models/list/default`（零参数）
- 调整：LoRA 查询与 KIE 查询接口参数明细补齐到文档

### 2026-03-05
- 调整：LoRA/KIE 查询接口补充 snake_case 兼容字段，便于 Coze 与中台统一解析。

### 2026-03-10
- 新增：`ComfyUI · 多图融合` 能力，已进入通用能力工具箱与 ComfyUI 工具箱。

## 7) Baidu 工具箱（执行类）

- OpenAPI：`/api/coze/podi/baidu/openapi.json`
- 用途：百度图像处理能力执行
- 鉴权：仅内网或 `SERVICE_API_TOKEN`

## 8) Volcengine 工具箱（执行类）

- OpenAPI：`/api/coze/podi/volcengine/openapi.json`
- 用途：火山能力执行（对话/图像/视频能力）
- 鉴权：仅内网或 `SERVICE_API_TOKEN`

---

## 跨工具箱通用接口（建议保留在流程中）

- 任务轮询：`POST /api/coze/podi/tasks/get`
- ComfyUI 队列汇总：`POST /api/coze/podi/comfyui/queue-summary`

---

## 建议给业务侧的固定接入方式

1. 查询型工具箱先查参数（LoRA、KIE 模型）。
2. 执行型工具箱发起任务。
3. 异步任务统一用 `tasks/get` 轮询结果。
4. 所有图片主图字段统一使用 `url`；多参考图统一使用 `image_urls`。
