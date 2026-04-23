# Coze 工具箱清单（PODI）

> 更新时间：2026-04-23
> 
> 说明：以下为当前后端实际可用的工具箱入口。导入 Coze 时使用 OpenAPI 地址；执行时按各工具箱里的接口调用。

## 地址前缀

- 当前控制面地址前缀：`http://<podi-backend-host>:8099`
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
- 用途：每个功能单独一个工具箱，便于 Coze 单独测试、单独发布、单独回滚。
- 导入说明：OpenAPI 地址可直接公网导入；真正执行接口与 `tasks/get` 仍按服务端鉴权规则校验。

| 工具箱 | OpenAPI | 推荐入参 | 最终输出 / 说明 |
| --- | --- | --- | --- |
| 背景抠图 | `/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json` | `url` | 最终输出节点 `4` |
| 头部抠像 | `/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json` | `url` | 最终输出节点 `140`；业务统一先走 OSS URL |
| FLUX2-Klein 扩图 | `/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json` | `url`、`expand_left`、`expand_right`、`expand_top`、`expand_bottom` | 后端先上传图片到 ComfyUI input 目录，再写入节点 `76`；扩图 prompt 固定内置、seed 每次自动随机；最终输出节点 `9` |
| 多图融合 | `/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json` | `url`、`image_url_2`、`image_url_3`、`width`、`height`、`prompt`、`negative_prompt`、`seed` | 无 `lora`；`width/height` 不传则沿用 workflow 默认 `1024x1024` |
| E7裂变重绘 | `/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json` | `url`、`prompt`、`bili`、`steps`、`cfg`、`seed`、`batch_size`、`width`、`height` | `bili` 为业务口径，后端兼容旧字段 `similarity` |
| 多元素花纹裂变 | `/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json` | `url`、`prompt`、`image_desc`、`bili`、`width`、`height` | 基于 `05_flux_strong_hq_softstyle_api.json`；固定 profile 参数，保留旧图裂变 `bili -> denoise` 口径，最终输出节点 `31` |
| FLUX2裂变+四方 | `/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json` | `url`、`prompt` | 仅覆写 `141.url` 与 `132.inStr`；节点 `104` 等内部默认参数保持不变；最终输出节点 `111` |
| 裂变文字强化 | `/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json` | `url`、`prompt`、`bili` | `prompt` 写入节点 `13.text1`，`bili` 映射到节点 `27.denoise`，最终输出节点 `29` |
| 8步加速可换LoRA | `/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json` | `url`、`lora`、`width`、`height`、`prompt`、`negative_prompt`、`batch` | 与线上印花提取业务链路隔离，统计口径独立 |

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

## 当前重点说明（Coze 接线时优先看这一节）

- 多图融合当前正式口径为：`url`、`image_url_2`、`image_url_3`、`width`、`height`、`prompt`、`negative_prompt`、`seed`；旧 `image_urls` 只保留后端兼容解析，不再作为推荐入参。
- E7 裂变当前业务口径为 `bili`；后端执行仍兼容旧字段 `similarity`。当前映射：`0→0.95`、`50→0.75`、`100→0.55`，最低钳制 `0.55`。
- 多元素花纹裂变沿用图裂变的 `bili` 口径，默认 `90 ≈ denoise 0.59`；`image_desc` 预留给上游 VL / Coze，不建议普通业务手填；`width/height` 为空时默认跟随原图尺寸。
- `FLUX2裂变+四方` 与 `裂变文字强化` 都依赖上游 Coze 节点生成 `prompt`；中台和评测链路已验证可执行，当前主要待优化点是上游提示词质量，不是工具箱契约本身。
- `背景抠图` 存在中间过程图，正式回填只认最终输出节点 `4`。
- `头部抠像` 的 `Florence2Run` 与 `SegmentAnythingUltra V2` 保持 workflow 内部默认值，不在工具箱侧暴露附加文本参数。

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
4. 所有图片主图字段统一使用 `url`；多参考图优先使用独立字段（如 `image_url_2`、`image_url_3`），不要优先依赖历史兼容字段。
