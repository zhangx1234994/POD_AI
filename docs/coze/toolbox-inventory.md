# Coze 工具箱清单（PODI）

> 更新时间：2026-02-28
> 
> 说明：以下为当前后端实际可用的工具箱入口。导入 Coze 时使用 OpenAPI 地址；执行时按各工具箱里的接口调用。

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
  - `POST /api/coze/podi/kie/models/list`
  - `POST /api/coze/podi/kie/models/schema`
  - `POST /api/coze/podi/kie/models/{model_key}/schema`（单模型零参数）

### 6.1 KIE 单模型工具箱（查询类，按模型拆分）

- OpenAPI 模板：`/api/coze/podi/kie/catalog/{model_key}/openapi.json`
- 示例：`/api/coze/podi/kie/catalog/nano-banana-pro-image-to-image/openapi.json`
- 用途：每个模型独立一个工具箱，便于业务按需发布/灰度。

### 6.2 KIE 单模型执行工具箱（执行类，按模型拆分）

- OpenAPI 模板：`/api/coze/podi/kie/execute/{model_key}/openapi.json`
- 示例：`/api/coze/podi/kie/execute/nano-banana-2-image-to-image/openapi.json`
- 用途：每个模型一个执行工具箱，入参与该模型能力 schema 一致，避免“查询工具箱误当执行工具箱”。

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
