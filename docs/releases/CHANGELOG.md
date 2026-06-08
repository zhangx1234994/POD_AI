# PODI 版本记录

## v0.6.4 - 2026-06-08

基线 commit：

- 本地候选提交：以本节所在提交为准。
- 线上最终提交：以 114 `/srv/pod/DEPLOYED_COMMIT` 和发布脚本 `released_commit` 为准。
- 上一封版基线：`524a9bfa`。

发布范围：

- 114 控制面 backend。
- 测评端静态站点。
- `docs/`、错误码、接口契约和 Agent Runtime 回归矩阵。

主要变更：

- AI 图片助手路由策略调整为“质量优先”：普通单张图片任务默认 `GPT-5.5 planner + GPT Image 2`，创建 `business.image_edit` run。
- 明确批量、快速、低成本或固定 SOP 的花纹提取诉求才分流到 `business.pattern_extract`，避免普通用户自然语言任务误走专项小模型。
- 后端 planner schema 增加 `routeType`、`targetAbility`、`targetBusinessKey`；控制面会覆盖模型误判，确保最终工具调用由后端白名单和规则兜底。
- `routeEvidence` 增加 `primaryExecutionEngine` 与 `specializedAbilityCandidate`，用于解释“为什么普通花纹提取仍走 GPT Image 2 质量路径”。
- 测评端 AI 图片助手继续按图片版 Codex 心智收口：无“执行这版”按钮，满足条件后自动进入后端执行边界，结果回到聊天消息流，二轮默认基于上一轮成功输出。
- Agent Runtime 回归矩阵从 6 组升级为 7 组 golden cases，新增普通花纹提取质量优先路由与专项加速路由两条断言。

本地验证结果：

- 业务流程审查通过：用户消息、planner、后端归一化、confirm 执行边界、业务 run payload、结果消息流、接口文档逐段核对。
- 后端 Agent/业务契约回归通过：`93 passed`。
- 新增单测覆盖普通花纹提取确认后创建 `image_edit` run，并确认 payload 不混入 `prompt/batch` 专项字段。
- `scripts/check_doc_entry_references.py`、`git diff --check`、Python 编译检查通过。
- 测评端 `npm run lint`、`npm run build` 通过。
- Playwright AI 图片助手回归通过：聊天流结果回填、二轮续改基于上一轮输出、新任务隔离。

线上验证计划：

- 运行标准 114 控制面发布脚本，完成源门禁、后端关键测试、管理端/测评端 lint/build、远端迁移、种子刷新、服务重启、deploy preflight 和 release smoke。
- 发布后确认 114 `/health`、`DEPLOYED_COMMIT`、`podi-backend/podi-admin-web/podi-eval-web` 状态。
- 真实全链路验收重点覆盖 AI 图片助手：普通单张花纹提取应返回 `routeType=image2_quality_first` 并创建 `image_edit` run；明确批量/快速/专项诉求应返回 `routeType=ability_accelerated` 并创建 `pattern_extract` run。

已知保留风险：

- GPT-5.5 / GPT Image 2 的真实效果和成本需要在线上真实任务中继续观察；本地回归只证明路由、契约和交互链路正确。
- `confirm` 仍是历史接口名；产品和文档已解释为“后端幂等执行边界”，后续如做新 Agent Runtime API，可再提供更贴近语义的执行接口。
- Pydantic v2 / FastAPI deprecation warning 仍为历史技术债，当前不阻断发布。

## v0.6.3 - 2026-06-04

基线 commit：

- 控制面代码提交：`2654efb4`
- Agent/控制面验收提交：`88d48dce`
- 最终线上收口提交：以 114 `/srv/pod/DEPLOYED_COMMIT` 和发布脚本 `released_commit` 为准。
- 上一封版基线：`c638c269`

发布范围：

- 114 控制面 backend。
- `docs/` 与发布/基准脚本。
- 管理端、测评端静态站点随标准控制面发布包重新构建部署；最终收口补丁包含测评端能力首页/版本列表/辅助导航交互调整。

主要变更：

- 新增 v0.6.3 中台能力控制面硬化方案，明确本版验收标准：响应速度、20 并发、真实业务回归、错误路径、文档门禁和回滚线。
- 接口调用中心 `/api/admin/business/api-key-usage` 加 12 秒管理端短 TTL 缓存；导出接口仍保持实时查询。
- `BusinessRunService` 原有 dashboard cache 与接口调用中心新缓存均收窄锁范围，缓存未命中时不再持全局锁执行数据库查询。
- ComfyUI 队列摘要 `get_comfyui_queue_summary` 加 8 秒短 TTL 与同 key 在途请求合并，避免管理端、Coze 插件、测评端高频刷新时同时打所有 ComfyUI 节点。
- 新增 `backend/scripts/control_plane_read_benchmark.py`，固定覆盖 `/health`、业务能力列表、usage summary、api usage 和 ComfyUI queue summary 的顺序/并发 p95。
- 文档入口切换到 v0.6.3 主线，继续强调中台主语是能力，客户端业务组装不进入本仓库实现。
- 最终收口补丁将测评端能力分类页继续降噪：推荐入口保持主注意力，版本列表常显，辅助工具导航保留，并补齐产品设计固定质量样例、能力交互状态模型、v0.6 收口清单、线上验证报告和发布脚本失败即阻断保护。

本地验证结果：

- Python 语法检查通过：`py_compile` 覆盖本次变更后端文件和基准脚本。
- 后端组合回归通过：`152 passed`。
- `git diff --check` 通过。
- `scripts/check_doc_entry_references.py` 通过。

线上验证计划：

- 发布后确认 114 `/srv/pod/DEPLOYED_COMMIT` 与本节基线一致。
- 运行标准发布脚本自带的远端迁移、种子刷新、服务重启、deploy preflight 和 release smoke。
- 使用 `backend/scripts/control_plane_read_benchmark.py` 在 114 本机 loopback 与公网各跑 20 并发，对比 `queue-summary` 是否从当前线上基线回落。

线上验证结果：

- 2026-06-07 最终收口确认 114 `released_commit=524a9bfa`，`/health` 正常；发布脚本源门禁、后端测试、管理端/测评端 lint 与 build、远端 deploy preflight 和 release smoke 全部通过。额外公网点检确认 114 `/health` 返回 ok，测评端 active 工作流目录返回 30 条。
- 2026-06-07 候选包验证确认 114 `DEPLOYED_COMMIT=6ba720e3`，`/health` 正常，`podi-backend/podi-admin-web/podi-eval-web` 均为 active；候选包随后已由 `524a9bfa` 正式干净提交覆盖发布。
- 2026-06-07 线上浏览器走查确认测评端图编辑与花纹提取分类页已加载新静态包：两个图编辑入口拆分、推荐版本区清晰、版本列表常显、辅助工具导航独立。截图见 `output/playwright/20260605-release-6ba720e3-eval-image-edit.png`、`output/playwright/20260605-release-6ba720e3-eval-pattern.png`。
- 2026-06-07 线上运行状态复核：最近 24 小时核心业务无 failed/running/queued 残留，接口调用中心无新增集中 4xx/5xx，114 到 158/233 ComfyUI `/queue` 可达且队列为空，backend 近窗口无 `QueuePool`、`OperationalError`、死锁、锁等待超时或 traceback。
- 2026-06-05 补充验收确认 114 `DEPLOYED_COMMIT=88d48dce`，`/health` 正常，`podi-backend/podi-admin-web/podi-eval-web` 均为 active，三项服务 `NRestarts=0`。
- AI 改图助手 5 组 Agent 验收全部通过，报告 `/srv/pod/reports/agent-v063-88d48dce-20260605.json`：首轮改图 run `7ccd14fbb18e41a59074ba3ffac3bbc9` 成功，二轮续改 run `2a2d7485d77f4cc2a3dd59de3542edd4` 成功且 `baseImageRole=previous_result`，新任务隔离 run `1f19a38de09543c2a30b429f464f40d4` 成功，模糊意图按预期返回 `409 AGENT_PLAN_REQUIRES_CLARIFICATION`，消息 `requestId` 幂等返回同一 plan。
- `88d48dce` 控制面 loopback 20 并发报告 `/srv/pod/reports/control-plane-88d48dce-loopback-20260605.json` 全部通过：`/health` p95 57.47ms，`business_capabilities` p95 447.98ms，`business_usage_summary` p95 120.57ms，`business_api_usage` p95 101.55ms，`comfyui_queue_summary` p95 63.28ms。
- `88d48dce` 公网 20 并发报告 `/srv/pod/reports/control-plane-88d48dce-public-20260605.json` 中业务读接口全部通过：`business_capabilities` p95 1019.91ms，`business_usage_summary` p95 522.34ms，`business_api_usage` p95 605.03ms，`comfyui_queue_summary` p95 390.14ms；公网 `/health` p95 392.00ms 超 300ms，重试报告 `/srv/pod/reports/control-plane-88d48dce-public-health-retry-20260605.json` p95 501.11ms，因 loopback p95 57.47ms，归因为公网 RTT/链路波动，不作为服务端阻断。
- 2026-06-05 业务 usage summary 最近 24 小时 `total=38/failed=1/running=0/queued=0/unresolvedIssues=[]`；唯一失败 run `e041ffe3617f4aa99544c4ffc80dea0b` 已归因为受控测试使用的 OSS 样例图 404。接口调用中心 `total=1003/successCount=1002/errorCount=1`，唯一 4xx 是模糊意图验收的预期 `409 AGENT_PLAN_REQUIRES_CLARIFICATION`。
- 114 `DEPLOYED_COMMIT=2654efb4`，`/health` 正常，`podi-backend/podi-admin-web/podi-eval-web` 均为 active。
- 标准发布脚本通过：源门禁、后端发布测试、管理端/测评端 lint 与 build、远端迁移、种子刷新、服务重启、deploy preflight 和 release smoke 全部通过。
- release smoke 关键控制面通过：ComfyUI 队列 `servers=2/capacity=20/idle=20/feedGapServers=0`，业务 usage summary `total=31/failed=0/running=0/queued=0/unresolved=0`，工作流兼容 `total=17/ok=17/failed=0`。
- 114 本机 loopback 20 并发基准通过，报告：`/srv/pod/reports/control-plane-2654efb4-loopback-20260604214139.json`；`/health` p95 85.51ms，`business_capabilities` p95 272.25ms，`business_usage_summary` p95 75.68ms，`business_api_usage` p95 95.58ms，`comfyui_queue_summary` p95 70.49ms。
- 公网 20 并发基准报告：`output/benchmarks/control-plane-114-20c-2654efb4-public-20260604214348.json`；`comfyui_queue_summary` p95 459.63ms，已从发布前约 5.9 秒回落到阈值内；`/health` p95 403.86ms 仍高于公网 300ms 阈值，但 loopback p95 85.51ms，判断为公网链路 RTT/波动，不是服务端健康接口耗时。
- 发布后复核：业务 usage summary 最近 24 小时 `failed=0/running=0/queued=0`；ComfyUI queue summary `totalCount=0/feedGapServers=0/backendBlockedServers=0/backendRunningSettlingServers=0`；backend 最近 10 分钟关键错误日志匹配数为 0。

当前线上基线证据：

- 公网 20 并发基线：`output/benchmarks/control-plane-114-20c-20260604203805.json`。
- 重试证据：`output/benchmarks/control-plane-114-20c-retry-health-queue-20260604203853.json`。
- 现象：请求成功率 100%，但当前线上 `c638c269` 的 `/health` p95 约 451ms、`comfyui_queue_summary` p95 约 5941ms；重试后仍超阈值，queue summary 是当前控制面瓶颈。

已知保留风险：

- 这次是短 TTL 与并发折叠的控制面保护，不等于完成后台预聚合；能力版本指标、质量样例统计和更完整的业务运行预聚合进入 v0.6 收口版继续盘点和标准化。
- `Q1002 / COMFYUI_EXECUTOR_UNAVAILABLE` 与 `Q1001 / COMFYUI_QUEUE_FULL` 的业务方判断口径仍需在 v0.6 收口版继续硬化，避免外部系统把 `ERR|...` 误判为提交成功。
- Agent Runtime MVP 已满足 v0.6.3 验收，但多能力路由、方法论流水线和上下文压缩增强暂不作为当前开发扩张；先在 v0.6 收口版补齐边界、文档、交互和回归标准。
- `/health` 公网 p95 超过 300ms，但 114 本机 loopback p95 正常；继续按公网 RTT/链路波动观察，不作为服务端封版阻断。
- Pydantic v2 / FastAPI deprecation warning 仍为历史技术债，当前不阻断发布。

证据记录：

- `docs/testing/2026-06-05-v0.6.3-88d48dce-agent-control-plane-validation.md`

## v0.6.2 - 2026-06-04

基线 commit：

- 线上已封版基线：`55a40167`
- 历史基线：`d384966f`

发布范围：

- 114 控制面 backend。
- 测评端静态站点。
- `docs/` 与发布脚本。

主要变更：

- 用户可见入口统一为“AI 改图助手”，不再在测评端、OpenAPI、业务文档和能力种子里使用旧产品名；`image-edit-chat` 接口路径和 `image_edit_chat` 业务 key 保持兼容。
- 进一步明确 AI 改图助手是 Agent Runtime 样板：对话式入口、后端会话和方案确认、白名单能力调用、结果仍回到标准 `image_edit` run。
- `scripts/release_114_control_plane.sh` 增加远端 SSH、上传、远端部署、远端预检、release smoke 和 live patrol 的有限重试，降低网络/SSH 握手偶发波动对发布判断的影响。
- AI 改图助手多轮续改已改为以上一轮成功输出作为基准图，并保留 `parentRunId/baseImageRole=previous_result` 证据。
- 管理端业务能力指标查询修复 MySQL `Out of sort memory` 500；进一步补充看板读接口短 TTL 缓存、防并发打穿和流程证据样本上限，避免页面轮询或多人同时打开打穿数据库。
- 接口调用中心分组视图改为轻量读取业务任务摘要字段，避免为了展示 runId 聚合而加载完整业务任务大 JSON 载荷。
- 发布 SOP 新增“版本启动前验收标准”和“封版文档维护”门禁，默认覆盖响应速度、并发能力、真实业务全链路、错误路径和文档清理。

本地验证结果：

- 测评端 `npm run lint` / `npm run build` 通过。
- 后端发布相关测试通过：`139 passed`。
- 后端相关 Python 文件 `py_compile` 通过。
- 发布脚本 `bash -n` 通过。
- `git diff --check` 通过。
- 主线代码、文档和脚本内已无旧产品名残留。
- 看板性能修复后，业务能力管理相关测试通过：`test_business_capability_admin.py` 71 passed；`test_business_usage_summary_includes_flow_evidence` 和 release smoke 业务摘要校验用例通过。
- 接口调用中心分组视图性能修复后，`test_business_admin_api_usage_supports_filters_summary_and_run_groups` 通过。

线上验证结果：

- 114 `DEPLOYED_COMMIT=d384966f` 时，`/health` 正常，`podi-backend/podi-admin-web/podi-eval-web` 均为 active。
- 远端发布源门禁、迁移、种子刷新、服务重启、deploy preflight 和 release smoke 通过。
- 核心业务真实全链路通过：花纹提取 `c52b3083b2124ed5bf0506719e4ea2c8`、图裂变 `1965ed64d1e84709a283e4ecb39a83d4`、扩图 `798f3504b3c2487d9c4379c9c3ec0cb6` 均成功；报告 `/srv/pod/reports/live-core-business-3ea9fc73-20260604150724.json`。
- 产品设计真实全链路通过：`75a394ceab324e029d93cf29026281fa` 成功；报告 `/srv/pod/reports/live-agent-product-3ea9fc73-20260604072132.json`。
- AI 改图助手真实多轮通过：session `ags_47f3e35232144ad2bd3004f8c1987ed1`，一轮 run `9bb4f5176c214acbaddc776cf8311f3e` 成功，二轮 run `0af058656520420bb0a88bc4665d380b` 成功，二轮证据为 `baseImageRole=previous_result`。
- 直接图编辑 8 个模式全部成功；报告 `/srv/pod/reports/live-image-edit-3ea9fc73/20260604_072451/summary.json`。
- `d384966f` 发布后复核：`/api/admin/business/capabilities` 200；`/api/admin/business/usage-summary?window_hours=24` 返回 `failed=0/running=0/queued=0/unresolvedIssues=[]`；发布后 backend 关键错误日志为空。
- `55a40167` 发布后复核：`/health` 正常，`podi-backend/podi-admin-web/podi-eval-web` 均为 active，发布后 backend 关键错误日志为空。
- 控制面性能复核：`/api/business/capabilities` 20 并发 20/20 成功，p95 363.3ms；`/api/admin/business/usage-summary?window_hours=24` 顺序 p95 278.5ms、20 并发 p95 77.6ms；`/api/admin/business/api-key-usage` 顺序 p95 72.8ms、20 并发 p95 509.6ms；`/api/admin/comfyui/queue-summary` 顺序 p95 784.7ms。

已知保留风险：

- 看板读接口当前用短 TTL 缓存和样本边界保护线上；中期仍需要把业务运行摘要、能力版本近 24h 指标和接口调用中心做后台预聚合。
- Pydantic v2 弃用 warning 仍为历史技术债，当前不阻断发布。

## v0.6.1 - 2026-06-03

基线 commit：以 114 发布脚本输出的 `DEPLOYED_COMMIT` 为准。

发布范围：

- 114 控制面 backend。
- 测评端静态站点。
- 管理端静态站点随控制面发布包重新打包，但本次无管理端业务改动。
- `docs/` 发布与验收记录。

主要变更：

- 测评端图编辑分类页移除“业务方验收入口”大板块，回到“能力分类”视角；首页只保留当前能力分类、两个独立图编辑入口和默认展开的版本列表。
- 发布复核后调整测评端信息架构：图编辑版本列表默认展开；左侧导航恢复辅助工具分类，但主能力仍优先排序。
- AI 改图助手交互从图编辑工作台中拆成独立能力入口：先上传或粘贴主图，再用自然语言表达意图，确认建议后执行；不再要求用户选择四种硬分类。
- 对话改图改为“图片 Codex”线程交互：左侧保留最近任务，中间承载对话、建议、错误和执行结果，右侧固定展示主图、最新结果和当前状态。
- 对话改图支持“新建改图”开启独立线程，避免多轮改图污染新任务；刷新页面后可从最近任务恢复主图、历史消息和最新建议。
- 对话改图执行轮询从约 180 秒扩展到约 10 分钟，并在界面显示“正在理解图片 / 正在提交任务 / 正在出图”与等待时长，避免长耗时出图被误认为无响应。
- 对话改图执行中/成功后隐藏大建议卡，保留状态和结果作为主视线；失败时保留建议卡用于重试。
- 对话改图结果图片按聊天消息回填，不再放到独立结果区；执行失败也会进入聊天流，不只依赖临时 toast。
- 对话改图多轮续改默认使用上一轮成功输出作为当前基准图；只有点击新建或更换基准图才开启新的图片上下文，避免继续对话仍改原始上传图。
- 测评端 502/503/504 错误展示优先读取后端错误明细，避免 `BACKGROUND_WORKERS_DISABLED` 等明确错误被泛化为“服务异常”。
- 后端业务 API 使用日志写入增加字段截断和防御性捕获，避免诊断日志字段过长把真实业务错误二次放大为 500。
- GPT Image 2 实时图片编辑能力的 vendor-api 同步等待上限从通用 180 秒提升为能力级 420 秒，避免对话改图/直接图编辑在真实模型慢响应时被固定超时误伤。

本地验证结果：

- 后端发布关键测试通过：`139 passed`。
- 管理端 `npm run lint` / `npm run build` 通过。
- 测评端 `npm run lint` / `npm run build` 通过。
- `git diff --check` 通过。
- 测评端静态包浏览器检查通过：图编辑分类页无“业务方验收入口”，版本列表默认展开，无 Vite dev 注入，对话改图页无四种硬分类卡。
- 对话改图本地流程通过：上传样图到 OSS、粘贴主图 URL 后右侧可见主图，发送自然语言需求后立即显示工作态并生成建议；刷新后最近任务可恢复会话；本地确认执行因后台线程关闭返回 `BACKGROUND_WORKERS_DISABLED`，错误进入聊天流。
- 管理端静态入口检查通过：未登录状态正常进入登录页，无生产运行时报错。
- GPT Image 2 图片编辑超时策略补充单测：metadata 能覆盖全局默认，请求级 override 会被限制在 15~900 秒内。

待线上验证：

- 114 发布源门禁、远端迁移、种子刷新、服务重启和 `/health`。
- 远端 deploy preflight、release smoke、接口调用中心、业务运行和 backend journal。
- 线上 AI 改图助手真实执行：生成建议、确认执行、轮询 runId、输出图片在对话消息内展示。

证据记录：

- `docs/testing/2026-06-03-v0.6.1-image-edit-chatbot-polish.md`

## v0.6.0 - 2026-06-03

基线 commit：以 114 发布脚本输出的 `DEPLOYED_COMMIT` 为准。

发布范围：

- 114 控制面 backend。
- 管理端静态站点。
- 测评端静态站点。
- `docs/`、`scripts/` 发布与巡检材料。

主要变更：

- 中台主线切换为能力治理：明确能力、能力版本、路由、调用、结果、质量、成本和错误是 v0.6 主对象；调用上下文只作为证据索引。
- 新增产品设计业务能力 `POST /api/business/product-design/runs`，底层首版复用 GPT Image 2 图片编辑能力，但以独立业务能力暴露。
- 新增 AI 改图助手独立入口 `/api/business/image-edit-chat/*`，与直接图编辑 `/api/business/image-edit/runs` 拆分。
- 新增业务 Agent Runtime 试点：会话、消息、建议方案、确认执行和工具调用证据落库，确认后仍调用标准业务能力。
- 补齐兼容调用上下文、资产证据、候选选择和交付包 API；文档明确它不是中台主视角，新接入优先使用 `clientContextId/inputAssetIds/clientRequestId`。
- 管理端业务能力页和 API 暴露页补充 v0.6 能力、上下文和上线检查信息；测评端图编辑分类拆分“直接图编辑”和“对话改图”。
- 修复测评版本 seed 在历史脏数据下的重复键问题，避免 `产品设计` 等能力默认入口被重复分类写入阻断。

本地验证结果：

- 后端全量测试通过：`679 passed`。
- 管理端生产构建通过：`npm run build`。
- 测评端生产构建通过：`npm run build`。
- `git diff --check` 通过。

待线上验证：

- 114 发布源门禁、远端 `alembic upgrade head`、种子刷新、服务重启和 `/health`。
- 远端 deploy preflight、release smoke、Coze OpenAPI、接口调用中心和业务 API 回归。
- 核心业务真实巡检：花纹提取、图裂变、扩图、图编辑、产品设计、对话改图，以及必要的并发和数据库连接池观察。

已知保留风险：

- `/api/business/projects/*` 作为兼容调用上下文保留，后续不再作为中台主线扩展。
- `podi-studio-preview/` 是并行客户端本地目录，不纳入本次中台控制面发布包。
- Pydantic v2 弃用 warning 仍为历史技术债，当前不阻断发布。

## v0.4.1 - 2026-05-26

基线 commit：`cd2b8964`

发布范围：

- 114 控制面 backend。
- 管理端静态站点。
- 测评端静态站点。
- `docs/`、`scripts/` 发布与巡检材料。

主要变更：

- 数据库连接池改为显式配置，默认 `20+20`，降低 backend 连接池耗尽复发风险。
- 发布 smoke 增加 backend journal 回归扫描，检查 `QueuePool` 和业务 finalize loop 错误。
- ComfyUI 队列汇总区分“短时回填观察中”和“疑似卡住”，并在管理端给出下一步动作。
- 管理端概览页新增“线上稳定性与封版判断”，收敛自检守护、后端连接池、业务运行、ComfyUI 队列四个信号。
- 管理端 ComfyUI 资源页和执行节点页完成一轮稳定性文案降噪。

验证结果：

- 114 发布源门禁通过：`HEAD == origin/main == cd2b8964`。
- 后端关键测试通过：134 passed。
- 管理端/测评端 `npm run lint` 与 `npm run build` 通过。
- 远端 deploy preflight 通过：PASS=5 FAIL=0。
- 远端 release smoke 通过，`backend_log_regression` 实际扫描 `matches=0 max=0`。
- 三条主业务真实巡检通过：图裂变、扩图、花纹提取均 `succeeded` 且有执行节点证据。
- 测评端 production 巡检通过：6 个 production 工作流全部成功，输出类型 `image=6`。
- 发布后即时观察通过：health-watch issues=[]，业务运行 failed/running/queued/unresolved 均为 0，ComfyUI blocked/settling 均为 0。
- 30 分钟观察复查通过：backend 最近 30 分钟关键错误日志匹配数为 0，接口调用中心近 1 小时 success=49/error=0，无集中 4xx/5xx。

证据记录：

- `docs/testing/2026-05-26-v0.4.1-114-seal-validation.md`
- 线上报告：`/srv/pod/reports/eval_patrol_20260526_135036.json`

已知保留风险：

- 商业账单历史 `wallet_missing` 当前仍按 observed-only 处理。
- `legacy-seamless-fission` 仍为历史 attention 项。
- Pydantic v2 弃用 warning 后续集中治理。

## v0.4.1 - 规划记录

目标：稳定性监控与管理端降噪。

当前规划：

- 稳定性监控：固定观察 114 `/health`、健康看板、业务运行、ComfyUI 队列、接口调用中心、OSS 回填和 backend 日志。
- 连接池治理：数据库连接池改为显式配置，发布 smoke 扫描近期 `QueuePool` 和业务 finalize loop 错误。
- ComfyUI 状态收敛：治理“中台 running 但 ComfyUI 队列为空”的残留诊断。
- 页面降噪：首页、业务能力、接口调用、ComfyUI 资源页优先展示可用性结论、异常位置和下一步动作。

方案：`docs/strategy/business-stability-observability-v0.4.1-plan.md`

## v0.4.0 - 2026-05-25

基线 commit：`8033c843`

Git tag：`v0.4.0`

发布范围：

- 114 控制面 backend。
- 管理端静态站点。
- 测评端静态站点。
- `docs/`、`scripts/` 发布与巡检材料。

未更新范围：

- 不更新 4090/5090/ComfyUI 能力机。
- 不调整扩图路由，不把扩图固定到 4090。

主要变更：

- 业务编排工作台产品化版本完成阶段封版：业务命名与版本族、编排图证据、接口调用中心、runId 排障、控制点去重继续收敛。
- 图编辑组件型业务能力完成 114 版本封版验证，`canvas_outpaint` 纳入真实巡检与交付包。
- 发布门禁修正历史失败判断：封版阻断使用未恢复失败，不再因后续已成功覆盖的历史失败误阻断。
- ComfyUI 158 扩图节点完成线上兼容复核，当前按节点侧修复结果继续参与中台路由。

验证结果：

- 封版验证时已确认发布基线与 `origin/main` 一致：`8033c843`。
- 线上真实业务巡检通过：花纹提取、图裂变、扩图均 `succeeded`。
- 图编辑真实样例通过：`canvas_outpaint_all_sides`，runId `759f0310c01c4eaf9787aaec4ff93f95`。
- 158 扩图指定节点验证通过：`flux2_klein_9b_outpaint`，logId `46261`。
- ComfyUI 兼容检查通过：`total=17 ok=17 warnings=0 failed=0 servers=2`。
- 发布 smoke 通过：队列容量 `20`、业务使用中心 `unresolved=0`、评测运维健康。
- systemd 真实巡检重新执行成功：`podi-business-live-patrol.service` 最近一次执行成功，6 个生产评测工作流全部成功。
- 管理端主要页面走查通过：业务能力、ComfyUI 资源、API 暴露、能力评测无浏览器侧 4xx/5xx 或明显运行时报错。

证据记录：

- `docs/testing/2026-05-25-v0.4.0-114-seal-validation.md`
- `docs/testing/2026-05-25-image-edit-release-candidate-114.md`
- 线上报告：`/srv/pod/deliverables/release_patrol/core_business_8033c843.json`
- 线上报告：`/srv/pod/deliverables/image_edit_patrol_seal/`
- 线上报告：`/srv/pod/reports/health-watch/eval_production_20260525T123505Z.json`

已知保留风险：

- 商业报表历史账单问题当前仍按 observed-only 观察，不作为本版本阻断。
- `legacy-seamless-fission` 仍为历史 attention 项，不影响本轮核心业务封版。
- 权限治理类风险后续继续按 auth/billing 路线处理，本版本未扩大鉴权面。

下个版本方向：

- v0.4.1 优先处理稳定性监控、连接池/线程治理、发版门禁补强和页面视觉降噪。
- 业务方组件更新方式、第三方能力治理和计费治理后续继续排期。

## v0.4.0 - 规划记录

目标：业务编排工作台产品化。

当前规划：

- 业务命名与版本族：按业务入口组织版本、继承关系、发布时间、更新时间和更新说明。
- 编排图交互闭环：节点可查看、默认版本只读、草稿版本可编辑受控字段。
- 接口调用中心与 runId 排障：一次业务调用聚合入口、版本、处理步骤、子能力、回填、回调和计费。
- 控制点继续去重：字段、枚举、默认值、状态词优先从后端业务版本和组件目录派生。
- 页面文案与视觉降噪：减少说明型大段文案，主提示使用业务语言。

方案：`docs/strategy/business-orchestration-workbench-v0.4-plan.md`

## v0.3.0 - 本地完成，待上线窗口

目标：业务编排工作台与控制点去重。

当前状态：

- 业务组件目录已落地。
- 受控编排草稿已落地。
- 草稿校验、发布门禁和切默认已落地。
- runId 父子步骤排障视图已落地。
- 后端测试、管理端类型检查和构建已通过；等待后续统一上线窗口。

方案：`docs/strategy/business-orchestration-workbench-v0.3-plan.md`

## v0.2.0 - 待发布

目标：业务控制面收敛。

当前状态：

- 本地开发和验证已完成，等待统一上线窗口。
- 业务配方、版本族、接口调用中心、测评端关键问题和逐功能上线门禁已收敛。
- 发布前仍需按 SOP 跑 114 控制面更新、线上 smoke、业务接口、Coze 工具箱和测评端回归。

方案：`docs/strategy/business-control-plane-v0.2-plan.md`

## v0.1.0 - 2026-05-16

基线 commit：`904f9a2a`

Git tag：`v0.1.0`

发布范围：

- 114 控制面 backend。
- 管理端静态站点。
- 测评端静态站点。

验证结果：

- 发布源检查通过：`PASS=6 WARN=0 FAIL=0`。
- 后端发布测试通过：`86 passed`。
- 管理端、测评端类型检查和构建通过。
- 远端健康检查通过。
- 发布 smoke 通过。
- ComfyUI 工作流兼容检查通过：`total=16 ok=16 warnings=0 failed=0 servers=2`。
- 158/233 双节点健康检查通过，队列总容量 20。

主要能力：

- 中台控制面稳定部署。
- 业务 API、Coze 工具箱、管理端、测评端基础闭环可用。
- ComfyUI 158/233 双节点路由恢复。
- 业务运行、能力调用、接口调用中心具备基础可观测能力。

已知保留问题：

- 业务链路仍存在多个控制单元重复管理的问题。
- 业务编排目前主要是 JSON/recipe，缺少可视化只读图和草稿编辑。
- 测评端和管理端仍需继续做业务化表达和视觉降噪。
- 账单、套餐、正式收费仍处于后续阶段。

下个版本方向：

- `v0.2.0`：控制权收敛、业务编排可视化、runId 全链路排障。
