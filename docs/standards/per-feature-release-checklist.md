# 逐功能上线检查表

本文件固定“每个功能上线前必须逐项检查”的口径。它解决的问题是：服务健康、页面能打开、接口能返回，并不代表某个功能的参数、节点、回填和展示都正确。

## 1. 使用原则

- 一次上线如果改了某个业务功能，必须为这个功能补一行检查记录。
- 检查对象不是“服务”，而是“业务功能”：例如 GPT Image 2 受控裂变、ComfyUI 颜色锁定裂变、裂变评分。
- 每行必须同时覆盖接口、页面、真实 payload、执行节点、结果回填和错误展示。
- ComfyUI 类功能必须额外检查目标机器的 workflow 节点和模型依赖，不能只看队列健康。
- 检查结论要能回到 `runId`、能力调用记录、OSS 链接或巡检报告，不能只写“已看”。
- 默认按“版本升级”处理同一业务目标；只有业务目标、输入输出、独立验收边界或计费边界变化时才新增业务入口。不能把一次交付包修补直接新增成一个功能。
- 功能名称必须稳定，“新版”只能作为角标或状态；若不确定是新功能还是版本升级，必须先确认。
- 管理端“接口调用”页必须读取后端 `/api/admin/business/delivery-contracts` 的 `featureReleaseChecks`，不允许只展示前端静态清单。
- 发布 smoke 必须包含 `per_feature_release_audit`，至少检查逐功能门禁审计结构、四类核心功能是否齐全、证据项是否可读。

## 2. 通用检查项

| 检查项 | 必须确认什么 | 证据 |
| --- | --- | --- |
| 接口入口 | 业务方调用的是稳定业务 API 还是 Coze 工具箱，路径是否正确。 | 接口文档、调用记录 |
| 入参字段 | 字段名、必填项、默认值、枚举值是否和交付文档一致。 | JSON 样例、实际请求 payload |
| 参数映射 | 业务字段是否正确映射到底层模型或 ComfyUI 节点。 | 能力调用记录、步骤详情 |
| 参数组合矩阵 | 至少覆盖必填最小请求、默认值、不填、只填单边尺寸、同时填写宽高、非 8 倍数尺寸、预设和显式参数冲突。 | 单元测试、实际请求 payload |
| 默认值 | 不填时是否走约定默认值，例如尺寸默认跟原图、单次固定一图。 | runId 详情、结果图 |
| 返回契约 | 对外查询默认是否为轻量返回；`detail=full` 或等价调试开关是否才返回步骤、请求、路由等排障字段。 | `/api/business/runs/get` 简版/调试版响应 |
| 执行节点 | 是否命中允许的执行节点；多机能力是否真的可路由。 | ComfyUI 队列、路由证据 |
| 节点依赖 | ComfyUI workflow 需要的自定义节点、模型、LoRA 是否在目标机器存在。 | workflow compatibility |
| 结果回填 | 图片、视频、文字、结构化结果是否进入平台结果字段和 OSS。 | 查询返回、OSS 链接 |
| 页面展示 | 测评端/管理端名称、参数文案、结果图浏览和错误提示是否用户能理解。 | 页面走查截图或记录 |
| 版本关系 | 本次是新功能还是版本升级；版本升级是否保留原业务名、发布时间、更新时间和更新说明。 | 业务版本卡片、版本管理页 |
| 接口调用记录 | 提交、轮询、回调或查询记录是否能按 `runId/requestId/traceId` 聚合。 | 管理端接口调用页 |
| 错误路径 | 缺参、节点缺失、队列满、依赖失败、超时是否有可读错误码。 | 错误样例、错误码总表 |
| 失败副作用 | 缺参、鉴权失败、业务范围不允许等提交前错误，是否不会创建 `BusinessRun`、步骤、扣费、回调或 queued 脏任务。 | 负向测试 + 数据库/管理端任务查询 |
| 交付材料 | 请求、提交返回、轮询请求、运行中、成功、失败六类样例是否齐全。 | 交付目录 |

## 3. 第一批功能检查表

| 功能 | 入口 | 必查重点 | 当前结论 |
| --- | --- | --- | --- |
| GPT Image 2 + VL 受控裂变 | `/api/business/fission/runs` | `imageUrl`、`variation_strength`、`quality`、`size`、`maskUrl`；一次请求固定一张图；尺寸默认跟原图；默认轻量返回。 | 已固化到交付目录 01 和管理端接口页。 |
| ComfyUI 颜色锁定裂变 | `/api/business/fission/runs` | `bili` 是重绘幅度，不是相似度；`profile/variation_preset/reference_lock/color_lock` 映射正确；158/233 必须通过 workflow 节点兼容检查；OSS 回填正常。 | 已固化到交付目录 02；该新业务不依赖 233 缺失的 `String` 节点，继续保留双机路由。 |
| 裂变生成图评估 | `/api/business/fission-evaluate/runs` | `originalImageUrl`、`generatedImageUrl`、`context`；`decision` 枚举可读；缺图返回 `VL_EVAL_IMAGE_REQUIRED`。 | 已固化到交付目录 03 和管理端接口页。 |
| 文字强化裂变（文生图） | `/api/business/text-fission/prompts` + `/api/business/text-fission/runs` | 第一步返回可编辑提示词；第二步必须显式传 `editable_prompt`；采样步数、强度、随机种子等内部参数不暴露给用户；默认查询轻量返回，调试版才返回步骤与路由；缺 `editable_prompt` 直接返回 `TEXT_FISSION_PROMPT_REQUIRED` 且不创建 queued 脏任务。 | 2026-05-19 已完成真实跑图、简版/调试版返回、缺参无副作用回归。 |
| 旧四方连续裂变 | Coze 工具箱 / 既有工作流 | `String`、`KSampler`、`SaveImage` 等节点存在；失败和回填可读；233/158 都必须通过 workflow compatibility。 | 纳入上线前 workflow compatibility 检查。2026-05-16 233 已恢复 `String` 并强制跑通旧四方/花纹扩图/FLUX2裂变+四方，允许恢复双机路由。 |

## 4. 当前 ComfyUI 节点差异策略

2026-05-15 复核：158 有 `String` / `StringConcatenate` / `SaveImage`，233 有 `KSampler` / `SaveImage`，但缺 `String`。因此先做临时 158-only 规避。

2026-05-16 复核：233 已在白名单保护下恢复 `String`、`ComposeRGBAImageFromMask`、`Text _O`、`Get Image Size`，并强制跑通 `sifang_lianxu`、`huawen_kuotu`、`flux2_9b_liebian_sifang`、`toubu_kouxiang`。临时 158-only 策略可以移除，恢复队列路由。

当前策略：

- 依赖 `String` 的低频/轻量工作流恢复 158/233 双机队列路由：`sifang_lianxu`、`huawen_kuotu`、`flux2_9b_liebian_sifang`。
- 高频主线业务继续保留 158/233 路由，例如 `comfyui-vl-control-v2` 颜色锁定裂变。
- 如果任一 ComfyUI 节点再次缺自定义节点或模型，先修服务器同构；只有真实业务需要止血时，才做临时路由限制，并必须写明恢复条件。

## 5. 发版前执行顺序

1. 先查接口文档和管理端“接口调用”页，确认功能是否归到正确业务分类。
2. 用测评端或业务巡检提交真实样例，记录 `runId`。
3. 按参数组合矩阵跑一轮最小用例；涉及尺寸、比例、数量、预设、枚举的功能必须检查最终底层 payload。
4. 打开业务任务详情，确认每个处理步骤、能力调用、执行节点和结果回填。
5. 对 ComfyUI 功能运行 workflow compatibility，确认目标机器没有缺节点或缺模型。
6. 对 ComfyUI/GPU 主链路跑至少一条真实任务；第三方商业模型可因成本跳过真实调用，但必须记录原因。
7. 用业务查询接口取最终结果，确认轻量返回体字段够业务方使用。
8. 用调试查询接口取同一个 `runId`，确认步骤、请求、路由、执行节点等排障字段只在调试版出现。
9. 打开接口调用记录，确认提交、轮询和结果查询能聚合到同一个 `runId`。
10. 触发至少一个错误路径，确认错误码和提示可读。
11. 对提交前错误追加副作用检查，确认没有生成 queued/running 脏任务、步骤、计费或回调。
12. 把检查结论写入测试报告或 TODO 进展。

## 6. 不允许上线的情况

- 页面显示成功，但查询接口没有结果图或结果字段为空。
- ComfyUI 目标机器缺自定义节点或模型，却仍宣称双机完全健康。
- 业务字段改名或含义改变，但测评端文案、交付文档、错误码总表没有同步。
- 交付文档缺请求/响应/错误样例。
- 只跑了 health、build 或 smoke，没有逐功能跑真实样例。
- 只验证错误返回码，没有验证错误请求是否留下业务任务、步骤、计费或回调副作用。
- 对外查询接口默认返回体包含大段步骤、请求、路由或底层调试信息，导致业务方拿到过重 JSON。
- 图裂变类页面仍显示“相似度”，或没有把 `bili/similarity` 统一解释为“重绘幅度”。
- 同一业务目标被误新增成功能，或功能名被随意改动导致测试/业务方找不到原入口。

## 7. 相关入口

- 业务主线：`docs/standards/business-mainline-contract.md`
- 业务接口枚举：`docs/standards/business-api-enums.md`
- 图裂变交付目录：`docs/api/examples/fission-business-delivery/`
- 发布 SOP：`docs/standards/release-sop.md`
- 早检 SOP：`docs/standards/morning-ops-check.md`

## 8. 动态审计输出

2026-05-19 起，逐功能上线门禁不再只靠本文档和前端静态表。后端交付审计接口会输出：

- `featureReleaseChecks[].status`：`done` 表示证据闭环，`doing` 表示需要复核，`todo` 表示暂不能标记可交付。
- `featureReleaseChecks[].evidence`：逐项列出交付材料、业务版本、真实运行、验收门禁或旧 Coze 巡检证据。
- `featureReleaseChecks[].blockers`：缺验收、缺运行、缺结果、缺业务版本等阻断项。
- `featureReleaseChecks[].warnings`：旧 Coze 巡检、第三方模型成本跳过等复核项。

当前审计先覆盖四类：

- GPT Image 2 + VL 受控裂变
- ComfyUI 颜色锁定裂变
- 裂变生成图评估
- 旧四方连续裂变

后续新增业务能力时，必须同步补充后端审计规格、管理端展示、交付样例和 smoke 结构测试。
