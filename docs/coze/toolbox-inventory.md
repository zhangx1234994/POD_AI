# Coze 工具箱清单（PODI）

> 更新时间：2026-04-15
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

### 3.1 ComfyUI 单功能工具箱（执行类，按功能拆分）

- OpenAPI 模板：`/api/coze/podi/comfyui/execute/{tool}/openapi.json`
- 现有独立工具箱：
  - `/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json`
  - `/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json`
  - `/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json`
  - `/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json`
  - `/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json`
  - `/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json`
  - `/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json`
- 用途：每个功能单独一个工具箱，便于 Coze 单独测试、单独发布、单独回滚。
- 导入说明：OpenAPI 地址可直接公网导入；真正执行接口与 `tasks/get` 仍按服务端鉴权规则校验。

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

### 2026-03-17
- 调整：`ComfyUI · 多图融合` 参数口径升级为新 workflow 版本：
  - `url`：主图
  - `image_url_2`：辅图 1
  - `image_url_3`：辅图 2
  - `width` / `height`（不传则沿用 workflow 默认 `1024x1024`）
  - `prompt` / `negative_prompt`
  - `seed`
  - 无 `lora` 入参
- 调整：旧 `image_urls` 仅作为后端兼容解析保留，不再作为 Coze 推荐入参。

### 2026-03-19
- 新增：`ComfyUI · 8步加速可换LoRA`，为 `印花提取` 工作流的独立 Coze 工具封装。
- 说明：该工具与现有 `印花提取` 业务能力隔离，统计口径独立，不影响线上已有业务链路。
- 关键入参：
  - `url`：主图 URL
  - `lora`：效果 LoRA，映射到工作流节点 `390`
  - `width` / `height`：输出尺寸，映射到工作流节点 `400`
  - `prompt` / `negative_prompt`
  - `batch`
- 新增：独立导入地址 `/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json`

### 2026-03-28
- 新增：`ComfyUI · E7裂变重绘`，基于 E7 + FLUX2 的裂变重绘独立工具。
- 关键入参：
  - `url`：主图 URL
  - `prompt`：单文本裂变提示词，建议直接接 VL 输出
  - `bili`：0-100，和旧裂变工作流保持一致；数值越高越接近原图，后端按 `0→0.95、50→0.75、100→0.55` 线性换算为 denoise，并设置下限 `0.55`，小数先取整
  - `steps` / `cfg` / `seed`
  - `batch_size`
  - `width` / `height`：不传默认原图尺寸，传入则按输入值执行
- 兼容说明：后端仍兼容旧字段 `similarity`，但 Coze 推荐入参统一使用 `bili`
- 新增：独立导入地址 `/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json`

### 2026-04-14
- 新增：`ComfyUI · 背景抠图`
  - 独立导入地址：`/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json`
  - 入参：`url`
  - 最终输出节点：`4`
- 新增：`ComfyUI · 头部抠像`
  - 独立导入地址：`/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json`
  - 入参：`url`
  - 最终输出节点：`140`
  - 说明：业务统一先走 OSS URL，再交给 workflow 执行
- 新增：`ComfyUI · FLUX2裂变+四方`
  - 独立导入地址：`/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json`
  - 入参：`url`、`prompt`
  - 最终输出节点：`111`
  - 说明：仅覆写节点 `141.url` 与 `132.inStr`，节点 `104` 等默认内部参数保持不变

### 2026-04-15
- 新增：`ComfyUI · 裂变文字强化`
  - 独立导入地址：`/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json`
  - 入参：`url`、`prompt`、`bili`
  - 最终输出节点：`29`
  - 说明：
    - 统一使用 `LoadImagesFromURL` 读取 OSS 图片
    - `prompt` 写入节点 `13.text1`
    - `bili` 复用裂变相似度映射，换算到节点 `27.denoise`
    - `seed/steps/cfg` 暂由中台默认值兜底

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
