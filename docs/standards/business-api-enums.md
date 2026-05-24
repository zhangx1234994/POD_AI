# 中台业务 API 枚举与返回契约

更新时间：2026-05-19

本文档是业务方直接调用 `/api/business/*` 时的枚举口径。后续对外接口、交付文档、管理端 API 开放页、测评端业务接入文档必须以本文档为准。

结构化真源：`backend/app/constants/business_api_contract.py`。管理端接口页、业务交付审计接口和发布 smoke 均读取同一份枚举定义；本文档负责解释给业务方看。

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
| `businessKey` | string | 是 | 业务能力，如 `pattern_extract`、`fission`、`text_fission`、`fission_evaluate`、`outpaint`、`image_edit`。 |
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
| 文字强化裂变（文生图） | `POST /api/business/text-fission/prompts` + `POST /api/business/text-fission/runs` | `POST /api/business/runs/get` | `qwen2512-text2img-v1` |
| 图编辑 | `POST /api/business/image-edit/runs` | `POST /api/business/runs/get` | `gpt-image2-editor-v1` |
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

`image_edit.quality`：

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

预设只用于快速填充缺失参数；如果业务方显式传了 `bili`、`reference_lock`、`color_lock`、`profile`，以显式参数为准。

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

## 5.1 文字强化裂变（文生图）

文字强化裂变（文生图）的 `businessKey` 固定为 `text_fission`，当前固定版本为 `qwen2512-text2img-v1`。

调用方式是两步：

1. `POST /api/business/text-fission/prompts`：传 `imageUrl`，中台用 VL 生成 `editablePrompt`、`editableNegativePrompt`、`promptDraftId`，并返回可读的文字识别项和推荐路由。
2. `POST /api/business/text-fission/runs`：传 `imageUrl` 和用户确认后的 `editable_prompt`，可选带回 `routeDecision`、`textItems`，中台直接提交 ComfyUI 文生图，不再二次调用 VL。

约束：

- 单次固定生成 1 张图，不支持 `count/batch/batch_size/n`。
- `width/height` 不传时跟随原图尺寸；传入时按 ComfyUI 安全倍数归一化。
- 第二步必须传 `editable_prompt`，也可以传第一步返回的 `editableNegativePrompt` 作为 `editable_negative_prompt`。
- 第二步可选传 `routeDecision` 和 `textItems`，用于保留第一步的路由判断和用户确认后的文字清单；不传也保持兼容。

文字强化裂变路由枚举：

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `routeDecision` | `text2img_rebuild` | 适合进入 Qwen 文生图重绘，通常是短文字、装饰型图案。 |
| `routeDecision` | `deterministic_text_rebuild` | 文字较多或结构明确，应优先走确定性文字重建，不建议直接文生图。 |
| `routeDecision` | `general_pattern_fission` | 没有明确文字强化诉求，更适合普通图裂变或图案扩展。 |
| `routeDecision` | `reject_text2img` | 当前图不适合文字强化裂变，应拒绝进入文生图链路并给出原因。 |

## 5.2 图编辑

图编辑的 `businessKey` 固定为 `image_edit`，当前默认版本为 `gpt-image2-editor-v1`。它是“前端组件 + 中台业务 API + GPT Image 2 编辑能力”的组合业务，业务方不直接调用 OpenAI。

调用方式：

1. 组件或业务后端提交 `POST /api/business/image-edit/runs`，保存返回的 `runId`。
2. 使用 `POST /api/business/runs/get` 轮询结果；默认轻量返回，只给业务需要的状态、结果图和错误。
3. 需要排障时传 `detail=full` 或等价调试参数，才查看编译提示词、步骤、能力调用和底层响应摘要。

`editSkill`：

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `editSkill` | `local_modify` | 局部修改：按编辑指令和点选/框选提示修改局部内容。 |
| `editSkill` | `reference_element_transfer` | 参考图替换：用参考图里的对象、材质或风格替换主图指定区域。 |
| `editSkill` | `remove_inpaint` | 删除修补：删除指定对象并补齐背景。 |
| `editSkill` | `color_reference_correction` | 补色校正：按参考图修正主图局部或整体颜色关系。 |
| `editSkill` | `canvas_outpaint` | 扩展画布：中台先生成目标尺寸透明画布和 alpha mask，只让模型补全外扩区域；`preserveOriginal=true` 时结果回填后会把原图区域贴回。 |

`quality`：

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `quality` | `auto` | 自动档，由模型选择质量和耗时。 |
| `quality` | `preview` | 快速预览档，映射 OpenAI `low`。 |
| `quality` | `production` | 正式候选档，映射 OpenAI `medium`。 |
| `quality` | `premium` | 高质量档，映射 OpenAI `high`，成本更高。 |

`size`：

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `size` | `auto` | 跟随原图或由模型自动选择，默认推荐。 |
| `size` | `1024x1024` / `1536x1024` / `1024x1536` | 常用 1K 预设。 |
| `size` | `2048x2048` / `2048x1152` | 2K 预设，高耗时高成本。 |
| `size` | `3840x2160` / `2160x3840` | 4K 预设，高耗时高成本。 |
| `size` | 自定义 `宽x高` | 高级模式可用；最大边不超过 3840，边长必须是 16 的倍数，长短边不超过 3:1，总像素 655,360 到 8,294,400。 |

`image_edit.output_format`：

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `output_format` | `png` | 默认输出格式。 |
| `output_format` | `jpeg` | 更小文件，不保留透明度。 |
| `output_format` | `webp` | 内部页面或支持 WebP 的业务可用。 |

约束：

- 单次固定生成 1 张图；多图请多次提交。
- `selectionHints` 只用于告诉模型关注哪里，不等同于精确蒙版。
- `maskUrl` 只能是一个最终合并后的有效 Alpha mask，尺寸必须与主图一致。
- `reference_element_transfer` 和 `color_reference_correction` 必须提供 `referenceImages`。
- `remove_inpaint` 必须提供 `selectionHints` 或 `maskUrl`。
- `canvas_outpaint` 可不传 `instruction`；可传 `expand_left/right/top/bottom` 或 `targetWidth/targetHeight`，目标尺寸会按 16 的倍数向上取整，最终尺寸以返回结果为准。
- `canvas_outpaint` 新增错误码：`IMAGE_EDIT_CANVAS_TOO_SMALL`、`IMAGE_EDIT_CANVAS_PLACEMENT_INVALID`、`IMAGE_EDIT_CANVAS_BUILD_FAILED`。

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
| `TEXT_FISSION_PROMPT_REQUIRED` | 文字强化裂变第二步缺少确认后的提示词。 | 先调用 `/api/business/text-fission/prompts`，再传 `editable_prompt`。 |
| `TEXT_FISSION_PROMPT_EMPTY` | VL 没有返回可用提示词。 | 换图重试；如持续出现，提供图片和请求时间给中台排查。 |
| `TEXT_FISSION_PROMPT_PREPARE_FAILED` | 文字强化裂变提示词生成失败。 | 可重试；如持续失败，提供请求时间和图片地址给中台。 |
| `IMAGE_EDIT_INSTRUCTION_REQUIRED` | 图编辑缺少编辑指令。 | 补传 `instruction`。 |
| `IMAGE_EDIT_SKILL_INVALID` | 图编辑技能非法。 | 改用允许的 `editSkill`。 |
| `IMAGE_EDIT_REFERENCE_REQUIRED` | 图编辑缺少参考图。 | 参考图替换或补色校正时补传 `referenceImages`。 |
| `IMAGE_EDIT_TARGET_REQUIRED` | 图编辑缺少目标区域。 | 删除修补时补传 `selectionHints` 或 `maskUrl`。 |
| `IMAGE_EDIT_SIZE_INVALID` | 图编辑尺寸非法。 | 使用预设尺寸或满足自定义尺寸约束。 |
| `IMAGE_EDIT_MASK_SIZE_MISMATCH` | 蒙版尺寸与主图不一致。 | 重新生成与主图同尺寸的 mask。 |
| `IMAGE_EDIT_MASK_ALPHA_REQUIRED` | 蒙版缺少透明通道。 | 使用带 Alpha 通道的 mask。 |
| `IMAGE_EDIT_QUALITY_INVALID` | 图编辑质量档位非法。 | 改用 `auto/preview/production/premium`。 |
| `IMAGE_EDIT_OUTPUT_FORMAT_INVALID` | 图编辑输出格式非法。 | 改用 `png/jpeg/webp`。 |
| `VL_EVAL_IMAGE_REQUIRED` | 裂变生成图评估缺少原图或生成图。 | 补齐 `originalImageUrl` 和 `generatedImageUrl` 后重新提交。 |
| `BUSINESS_RUN_TIMEOUT` | 任务超时。 | 稍后重试，必要时联系中台排查底层能力。 |
| `BUSINESS_ABILITY_EXECUTION_FAILED` | 底层能力执行失败。 | 可重试；如持续失败，提供 `runId` 给中台。 |
| `BUSINESS_VL_PREPROCESS_FAILED` | VL 前置分析失败。 | 可重试；如持续失败，提供 `runId` 给中台。 |
| `VENDOR_API_RATE_LIMITED` | 第三方模型限流。 | 降低提交频率，稍后重试。 |
| `COMFYUI_QUEUE_FULL` | ComfyUI 队列已满。 | 按提示稍后重试。 |

## 9. 接口调用中心枚举

管理端 `API 开放 -> 接口调用中心` 使用以下枚举识别业务调用链路：

| 字段 | 允许值 | 含义 |
| --- | --- | --- |
| `endpoint_kind` | `submit` | 提交业务任务，例如 `/api/business/fission/runs`。 |
| `endpoint_kind` | `poll` | 查询业务任务结果，例如 `/api/business/runs/get`。 |
| `endpoint_kind` | `callback` | 业务回调相关接口。 |
| `status_group` | `success` | HTTP 2xx/3xx 且无平台错误码。 |
| `status_group` | `error` | HTTP 4xx/5xx 或存在平台错误码。 |
| `issueCode` | `HAS_ERROR` | 同一个 `runId` 聚合链路里存在异常响应或错误码。 |
| `issueCode` | `POLL_WITHOUT_SUBMIT` | 当前筛选范围内只有查询记录，没有提交记录。通常需要放宽时间窗口或核对 `runId`。 |
| `issueCode` | `POLLING_TOO_FREQUENT` | 同一个 `runId` 轮询次数偏高，业务方应按 `retryAfterSeconds` 控制查询频率。 |

## 10. 当前缺口

以下内容需要在后续版本补到代码、OpenAPI 和页面中：

- API 调用中心需要继续补“从调用记录直接定位业务运行详情”的深链接持久化，目前管理端已支持页面内打开业务任务详情。

已完成：

- 2026-05-15：API 调用中心已纳入发布后 smoke，`business_api_usage_center` 会检查接口可访问、分页结构正常和 `runId` 聚合可用。
- 2026-05-15：管理端“接口调用”页新增三个交付接口逐项检查，固定检查 GPT Image 2 受控裂变、ComfyUI 颜色锁定裂变、裂变生成图评估是否具备独立文档、6 类 JSON 样例、枚举说明和常见错误码；发现缺口必须先补文档和页面口径，再进入上线。
- 2026-05-15：管理端“接口调用中心”增加窗口级轮询频率提示；如果平均每次提交对应 30 次以上查询，页面会提示业务方按 `retryAfterSeconds` 或 5-10 秒间隔轮询。
- 2026-05-17：发布 smoke 新增 `business_truth_source_consistency` 门禁，检查业务版本、业务 OpenAPI、测评入口、只读编排图和本文档枚举是否一致；参数或测评入口漂移会阻断发版。
- 2026-05-17：业务运行详情复用接口调用中心枚举，入口调用证据里的轮询过频统一返回 `POLLING_TOO_FREQUENT`，避免详情页和接口调用页出现不同错误口径。
- 2026-05-18：新增后端结构化枚举真源 `business_api_contract.py`，交付审计接口返回 `enumDocs/enumValues/contractSource/contractVersion`，管理端接口页优先读取后端枚举；前端静态枚举只作为离线兜底。
