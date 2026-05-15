# 逐功能上线检查表

本文件固定“每个功能上线前必须逐项检查”的口径。它解决的问题是：服务健康、页面能打开、接口能返回，并不代表某个功能的参数、节点、回填和展示都正确。

## 1. 使用原则

- 一次上线如果改了某个业务功能，必须为这个功能补一行检查记录。
- 检查对象不是“服务”，而是“业务功能”：例如 GPT Image 2 受控裂变、ComfyUI 颜色锁定裂变、裂变评分。
- 每行必须同时覆盖接口、页面、真实 payload、执行节点、结果回填和错误展示。
- ComfyUI 类功能必须额外检查目标机器的 workflow 节点和模型依赖，不能只看队列健康。
- 检查结论要能回到 `runId`、能力调用记录、OSS 链接或巡检报告，不能只写“已看”。

## 2. 通用检查项

| 检查项 | 必须确认什么 | 证据 |
| --- | --- | --- |
| 接口入口 | 业务方调用的是稳定业务 API 还是 Coze 工具箱，路径是否正确。 | 接口文档、调用记录 |
| 入参字段 | 字段名、必填项、默认值、枚举值是否和交付文档一致。 | JSON 样例、实际请求 payload |
| 参数映射 | 业务字段是否正确映射到底层模型或 ComfyUI 节点。 | 能力调用记录、步骤详情 |
| 默认值 | 不填时是否走约定默认值，例如尺寸默认跟原图、单次固定一图。 | runId 详情、结果图 |
| 执行节点 | 是否命中允许的执行节点；多机能力是否真的可路由。 | ComfyUI 队列、路由证据 |
| 节点依赖 | ComfyUI workflow 需要的自定义节点、模型、LoRA 是否在目标机器存在。 | workflow compatibility |
| 结果回填 | 图片、视频、文字、结构化结果是否进入平台结果字段和 OSS。 | 查询返回、OSS 链接 |
| 页面展示 | 测评端/管理端名称、参数文案、结果图浏览和错误提示是否用户能理解。 | 页面走查截图或记录 |
| 错误路径 | 缺参、节点缺失、队列满、依赖失败、超时是否有可读错误码。 | 错误样例、错误码总表 |
| 交付材料 | 请求、提交返回、轮询请求、运行中、成功、失败六类样例是否齐全。 | 交付目录 |

## 3. 第一批功能检查表

| 功能 | 入口 | 必查重点 | 当前结论 |
| --- | --- | --- | --- |
| GPT Image 2 + VL 受控裂变 | `/api/business/fission/runs` | `imageUrl`、`variation_strength`、`quality`、`size`、`maskUrl`；一次请求固定一张图；尺寸默认跟原图；默认轻量返回。 | 已固化到交付目录 01 和管理端接口页。 |
| ComfyUI 颜色锁定裂变 | `/api/business/fission/runs` | `bili` 是重绘幅度，不是相似度；`profile/variation_preset/reference_lock/color_lock` 映射正确；158/233 必须通过 workflow 节点兼容检查；OSS 回填正常。 | 已固化到交付目录 02；该新业务不依赖 233 缺失的 `String` 节点，继续保留双机路由。 |
| 裂变生成图评估 | `/api/business/fission-evaluate/runs` | `originalImageUrl`、`generatedImageUrl`、`context`；`decision` 枚举可读；缺图返回 `VL_EVAL_IMAGE_REQUIRED`。 | 已固化到交付目录 03 和管理端接口页。 |
| 旧四方连续裂变 | Coze 工具箱 / 既有工作流 | `String`、`KSampler`、`SaveImage` 等节点存在；失败和回填可读；若 233 未补齐 `String`，必须只允许 158。 | 纳入上线前 workflow compatibility 检查。2026-05-15 调整为 158 单机路由，避免命中 233 后失败再 fallback。 |

## 4. 当前 ComfyUI 节点差异策略

2026-05-15 复核：158 有 `String` / `StringConcatenate` / `SaveImage`，233 有 `KSampler` / `SaveImage`，但缺 `String`。233 之前做过安全加固，当前不为了少数低频工作流强行改服务器权限。

临时策略：

- 依赖 `String` 的低频/轻量工作流只走 5090：`sifang_lianxu`、`huawen_kuotu`、`flux2_9b_liebian_sifang`。
- 高频或耗时较长且 233 已验证正常的主线业务继续保留 158/233 路由，例如 `comfyui-vl-control-v2` 颜色锁定裂变。
- 如果 5090 队列满或不可达，这几个低频工作流应返回可读的队列/节点不可用错误，不再静默落到 233。
- 后续如果要恢复双机路由，必须先确认 233 `/object_info` 能返回 `String` 节点，再把允许节点改回双机。

## 5. 发版前执行顺序

1. 先查接口文档和管理端“接口调用”页，确认功能是否归到正确业务分类。
2. 用测评端或业务巡检提交真实样例，记录 `runId`。
3. 打开业务任务详情，确认每个处理步骤、能力调用、执行节点和结果回填。
4. 对 ComfyUI 功能运行 workflow compatibility，确认目标机器没有缺节点或缺模型。
5. 用业务查询接口取最终结果，确认轻量返回体字段够业务方使用。
6. 触发至少一个错误路径，确认错误码和提示可读。
7. 把检查结论写入测试报告或 TODO 进展。

## 6. 不允许上线的情况

- 页面显示成功，但查询接口没有结果图或结果字段为空。
- ComfyUI 目标机器缺自定义节点或模型，却仍宣称双机完全健康。
- 业务字段改名或含义改变，但测评端文案、交付文档、错误码总表没有同步。
- 交付文档缺请求/响应/错误样例。
- 只跑了 health、build 或 smoke，没有逐功能跑真实样例。

## 7. 相关入口

- 业务主线：`docs/standards/business-mainline-contract.md`
- 业务接口枚举：`docs/standards/business-api-enums.md`
- 图裂变交付目录：`docs/api/examples/fission-business-delivery/`
- 发布 SOP：`docs/standards/release-sop.md`
- 早检 SOP：`docs/standards/morning-ops-check.md`
