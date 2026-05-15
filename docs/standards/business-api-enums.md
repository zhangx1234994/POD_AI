# 中台业务 API 枚举与返回契约

更新时间：2026-05-15

本文档是业务方直接调用 `/api/business/*` 时的枚举口径。后续对外接口、交付文档、管理端 API 开放页、测评端业务接入文档必须以本文档为准。

## 1. 任务状态

对外统一只暴露 4 个状态：

| 字段 | 允许值 | 含义 | 业务方建议 |
| --- | --- | --- | --- |
| `status` / `taskStatus` | `queued` | 已进入中台队列，尚未真正执行。 | 按 `retryAfterSeconds` 继续轮询。 |
| `status` / `taskStatus` | `running` | 正在执行或等待底层能力回填。 | 按 `retryAfterSeconds` 继续轮询。 |
| `status` / `taskStatus` | `succeeded` | 业务任务成功，结果字段可读取。 | 读取 `imageUrls/videoUrls/texts/assets/resultPayload`。 |
| `status` / `taskStatus` | `failed` | 业务任务失败或被平台判定无法继续。 | 读取 `errorCode/errorMessage/debugResponse`，按错误码处理。 |

内部历史状态如 `pending/processing/completed/done/cancelled/timeout` 不直接暴露给业务方，统一折算到以上 4 个状态。

## 2. 查询与返回字段

| 字段 | 类型 | 必有 | 含义 |
| --- | --- | --- | --- |
| `runId` | string | 是 | 业务运行 ID，业务方轮询和排查的主键。 |
| `taskId` | string/null | 是 | 中台内部任务 ID，主要用于排查。 |
| `businessKey` | string | 是 | 业务能力，如 `fission`、`fission_evaluate`、`outpaint`。 |
| `version` | string/null | 是 | 命中的业务版本。 |
| `status` | enum | 是 | 同任务状态。 |
| `taskStatus` | enum | 是 | 兼容 Coze 工具箱口径，同任务状态。 |
| `retryAfterSeconds` | number | 是 | 建议下次轮询间隔，默认 10 秒。 |
| `imageUrl` | string/null | 是 | 首张图片结果。无图片时为 null。 |
| `imageUrls` | string[] | 是 | 图片结果列表。 |
| `videoUrl` | string/null | 是 | 首个视频结果。无视频时为 null。 |
| `videoUrls` | string[] | 是 | 视频结果列表。 |
| `text` | string/null | 是 | 首段文本结果。无文本时为 null。 |
| `texts` | string[] | 是 | 文本结果列表。 |
| `assets` | object[] | 是 | 统一资源列表，图片/视频/文件都可进入该字段。 |
| `resultPayload` | object/null | 否 | 结构化结果，评分、VL 分析等能力会使用。 |
| `errorCode` | string/null | 是 | 标准错误码。 |
| `errorMessage` | string/null | 是 | 面向业务方的错误说明。 |
| `debugResponse` | object/string/null | 是 | 排障信息。默认轻量返回，不含敏感密钥。 |
| `debugUrl` | string/null | 是 | 管理端排障链接，当前可为空。 |

## 3. 业务入口

| 业务 | 提交接口 | 查询接口 | 固定版本建议 |
| --- | --- | --- | --- |
| GPT Image 2 受控裂变 | `POST /api/business/fission/runs` | `POST /api/business/runs/get` | `gpt-image2-vl-v2` |
| ComfyUI 颜色锁定裂变 | `POST /api/business/fission/runs` | `POST /api/business/runs/get` | `comfyui-vl-control-v2` |
| 裂变生成图评估 | `POST /api/business/fission-evaluate/runs` | `POST /api/business/runs/get` | `generated-image-eval-v1` |
| 扩图 | `POST /api/business/outpaint/runs` | `POST /api/business/runs/get` | 当前默认版本 |
| 花纹提取 | `POST /api/business/pattern-extract/runs` | `POST /api/business/runs/get` | 当前默认版本 |

## 4. 图裂变参数枚举

### 4.1 GPT Image 2 受控裂变

`variation_strength`：

| 值 | 含义 |
| --- | --- |
| `conservative` | 保守裂变，更接近原图。 |
| `same_series` | 同系列裂变，默认推荐。 |
| `creative_same_series` | 更开放的同系列变化。 |

`quality`：

| 值 | 含义 |
| --- | --- |
| `preview` | 快速预览，适合内部测试和批量初筛。 |
| `candidate` | 候选质量，适合交给业务方看效果。 |
| `premium` | 高质量档，成本更高。 |

`size`：

| 值 | 含义 |
| --- | --- |
| `auto` | 默认按原图尺寸和比例处理。 |
| `1024x1024` | 正方形 1K。 |
| `1536x1024` | 横图。 |
| `1024x1536` | 竖图。 |
| `2048x2048` | 正方形 2K。 |
| `2048x1152` | 16:9 横图。 |
| `3840x2160` | 4K 横图。 |
| `2160x3840` | 4K 竖图。 |

### 4.2 ComfyUI 颜色锁定裂变

`profile`：

| 值 | 含义 |
| --- | --- |
| `pattern_risk_routed_v4` | 智能风险路由，默认推荐。 |
| `pattern_color_lock_v2` | 颜色锁定基础版，用于旧样本对照。 |
| `pattern_color_lock_strict_v2` | 严格颜色锁定，更像原图但裂变感更弱。 |
| `pattern_default_v1` | 历史兼容值，不推荐新业务使用。 |

`variation_preset`：

| 值 | 含义 |
| --- | --- |
| `default-high` | 高幅度默认：`bili=80%`、`reference_lock=0.42`、`color_lock=0.90`。 |
| `safe` | 保守稳定：`bili=30%`、`reference_lock=0.50`、`color_lock=1.00`。 |
| `object-strong` | 对象变化更强：`bili=100%`、`reference_lock=0.34`、`color_lock=0.90`。 |
| `color-free` | 配色更自由：`bili=80%`、`reference_lock=0.42`、`color_lock=0.75`。 |

`bili` 不是相似度，是重绘幅度。值越大变化越明显。当前只做文案建议，不做接口硬限制。

## 5. 裂变评分枚举

`decision`：

| 值 | 含义 |
| --- | --- |
| `pass` | 通过。 |
| `needs_refission` | 建议二次裂变。 |
| `reject` | 不通过。 |

`next_action.type`：

| 值 | 含义 |
| --- | --- |
| `accept` | 接受当前结果。 |
| `refission_repeat` | 建议重复裂变。 |
| `reject` | 拒绝当前结果。 |

## 6. 路由预览枚举

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `selectedBy` | `explicit` | 调用方明确传入版本。 |
| `selectedBy` | `default` | 命中当前默认版本。 |
| `selectedBy` | `rollout_allowlist` | 命中灰度白名单。 |
| `selectedBy` | `rollout_percent` | 命中灰度比例。 |
| `selectedStatus` | `active` | 版本启用，可路由。 |
| `selectedStatus` | `disabled` | 版本停用，不应作为实际执行版本。 |
| `selectedStatus` | `archived` | 历史归档，只能用于记录或对照。 |

## 7. 计费与回调状态

当前计费和回调状态主要供管理端排障使用，对业务方默认不要求处理。

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `billingStatus` | `billable` | 可计费且已完成结算。 |
| `billingStatus` | `unpriced` | 成功但缺少定价策略。 |
| `billingStatus` | `no_charge` | 明确免计费。 |
| `billingStatus` | `billing_pending` | 等待计费处理。 |
| `callbackStatus` | `pending` | 等待回调或尚未进入回调。 |
| `callbackStatus` | `succeeded` | 回调成功。 |
| `callbackStatus` | `failed` | 回调失败。 |
| `callbackStatus` | `skipped` | 未配置回调或无需回调。 |

## 8. 常见错误码

完整错误码以 `docs/standards/error-catalog.md` 为准。业务接口常见错误如下：

| 错误码 | 含义 | 业务方处理 |
| --- | --- | --- |
| `BUSINESS_IMAGE_URL_REQUIRED` | 缺少图片地址。 | 补传 `imageUrl`。 |
| `BUSINESS_RUN_ID_REQUIRED` | 查询缺少 `runId`。 | 使用提交返回的 `runId` 查询。 |
| `BUSINESS_RUN_NOT_FOUND` | 任务不存在或不属于当前 Key。 | 检查 `runId` 和 API Key。 |
| `BUSINESS_API_KEY_REQUIRED` | 缺少业务 API Key。 | 在请求头传 `X-PODI-API-Key`。 |
| `BUSINESS_API_KEY_INVALID` | Key 不存在或已失效。 | 更换有效 Key。 |
| `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED` | Key 无权调用该业务。 | 联系中台补授权。 |
| `BUSINESS_USER_SCOPE_FORBIDDEN` | 租户或用户范围不匹配。 | 检查 `tenantId/clientId/userId`。 |
| `BUSINESS_RUN_TIMEOUT` | 任务超时。 | 稍后重试，必要时联系中台排查底层能力。 |
| `BUSINESS_ABILITY_EXECUTION_FAILED` | 底层能力执行失败。 | 可重试；如持续失败，提供 `runId` 给中台。 |
| `BUSINESS_VL_PREPROCESS_FAILED` | VL 前置分析失败。 | 可重试；如持续失败，提供 `runId` 给中台。 |
| `VENDOR_API_RATE_LIMITED` | 第三方模型限流。 | 降低提交频率，稍后重试。 |
| `COMFYUI_QUEUE_FULL` | ComfyUI 队列已满。 | 按提示稍后重试。 |

## 9. 当前缺口

以下内容需要在后续版本补到代码、OpenAPI 和页面中：

- `profile/mode/pattern_risk_type/selectedStatus/selectedBy` 需要在 OpenAPI schema 中显式写入 `enum`。
- API 调用记录需要独立页面，支持筛选、分页、导出和按 `runId` 聚合。
- API 调用记录需要区分提交接口、查询接口、回调接口，避免查询轮询淹没真实业务提交。
- 发版门禁需要检查业务 OpenAPI 中 `status/type/mode/profile/quality/size` 字段是否缺枚举说明。
