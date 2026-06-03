# PODI 版本记录

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
- 对话改图 ChatBot 交互从图编辑工作台中拆成独立能力入口：先上传或粘贴主图，再用自然语言表达意图，确认建议后执行；不再要求用户选择四种硬分类。
- 对话改图改为“图片 Codex”线程交互：左侧保留最近任务，中间承载对话、建议、错误和执行结果，右侧固定展示主图、最新结果和当前状态。
- 对话改图支持“新建改图”开启独立线程，避免多轮改图污染新任务；刷新页面后可从最近任务恢复主图、历史消息和最新建议。
- 对话改图执行轮询从约 180 秒扩展到约 10 分钟，并在界面显示“正在理解图片 / 正在提交任务 / 正在出图”与等待时长，避免长耗时出图被误认为无响应。
- 对话改图执行中/成功后隐藏大建议卡，保留状态和结果作为主视线；失败时保留建议卡用于重试。
- 对话改图结果图片按聊天消息回填，不再放到独立结果区；执行失败也会进入聊天流，不只依赖临时 toast。
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
- 线上对话改图真实执行：生成建议、确认执行、轮询 runId、输出图片在 ChatBot 消息内展示。

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
- 新增对话改图 ChatBot 独立入口 `/api/business/image-edit-chat/*`，与直接图编辑 `/api/business/image-edit/runs` 拆分。
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
