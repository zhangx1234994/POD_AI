# 战略待办池（唯一入口，2026Q2）

说明：

- 本文档是战略执行唯一任务池。
- 旧任务如未迁移，不进入本轮实施。

状态字段：

- `todo`：待开始
- `doing`：进行中
- `blocked`：阻塞
- `done`：已完成
- `archived`：归档

当前执行焦点（2026-04-27）：

- 当前先暂停新增中台功能和大前端改造，优先处理 2026-04-27 事故暴露的问题。
- 优先级固定为：业务链路自动巡检 -> ComfyUI 队列/并发可观测 -> 工作流目录治理 -> 再回到业务能力层和前端优化。
- Coze 保留为业务接入与快速实验入口，但高并发业务调度、默认版本、灰度、统计和回滚逐步收归中台。

---

## P0（先做，2-3 周）

0. `doing` 2026-04-27 事故整改优先包
- 背景：Coze 工具箱因 `INTERNAL_ONLY` 不可用，服务健康但业务链路停摆；同时暴露出 ComfyUI 队列利用率不可见、工作流目录难分辨、ComfyUI 成功但无图回填等问题。
- 产物：
  - 事故复盘：`docs/retrospectives/2026-04-27-coze-toolbox-internal-only-incident.md`
  - 发布后 smoke 脚本：`backend/scripts/podi_release_smoke.py`
  - 全量测评巡检脚本：`backend/scripts/patrol_eval_workflows.py`
  - ComfyUI 队列压测脚本：`backend/scripts/comfyui_capacity_probe.py`
  - 发布前门禁升级：`docs/release-preflight.md`
- 验收：
  - 每次发版后能跑完整 active 工作流巡检，并输出成功/失败/中台任务 ID/Coze 执行 ID。
  - 能验证 ComfyUI 单机 10、双机 20 的实际队列承载，不再只看理论配置。
  - ComfyUI `success` 但无图时不能长期 `running`，必须明确失败并给出 `COMFYUI_IMAGES_EMPTY`。
  - 任何 `INTERNAL_ONLY`、工具箱导入失败、主工作流失败都必须阻断发版。
- 进展（2026-04-27）：已修复 Coze 同机调用、ComfyUI 空输出无限 running、背景抠图缓存空 history；114 上 smoke 通过，背景抠图 4 任务分流到两台 ComfyUI 且全部成功。
- 进展（2026-04-27）：评测端首页已接入链路健康卡片、失败原因汇总、最近失败样本、ComfyUI 队列汇总；`check_eval_operations_health.py` 已纳入 ComfyUI 执行节点健康，能识别 `COMFYUI_EXECUTOR_UNREACHABLE` / `COMFYUI_NO_AVAILABLE_EXECUTOR` 并进入发版门禁。
- 当前未收口（2026-04-27）：KIE 商业模型余额不足导致 2 条图裂变失败；`executor_comfyui_seamless_117` 队列不可读，需要确认是临时恢复服务还是正式下线/替换。

1. `doing` 战略指标面板落地
- 产物：北极星与 5 个 KPI 的数据定义、口径说明、查询来源
- 验收：每周可自动出一次指标快照
- 进展（2026-04-25）：业务调用、vendor-api 调用、能力健康、业务版本调用统计已具备数据基础；还缺统一战略指标面板与每周快照导出。

2. `todo` 用户分层与主路径图
- 产物：三类用户 Top3 路径图
- 验收：评审通过后作为 IA 设计输入
- 说明（2026-04-25）：当前先按“业务方 / 管理员 / 开发接入方”三类推进；正式主路径图仍需补文档和页面验证。

3. `doing` 信息架构 V1
- 产物：一级导航、二级页面、主工作区定义
- 验收：侧边栏与页面框架统一
- 进展（2026-03-04）：已完成 strategy 文档骨架与管理端响应式第一轮改造；ComfyUI 管理已落地“分类 + 模块”二级导航，并完成“同步发布”三步面板、单主 CTA、次级面板折叠、失败后建议文案；已补超窄屏自适配与状态列命名统一，下一步做 IA 评审与模块拆分图
- 进展（2026-03-05）：已完成“能力详情/测试并入能力目录”迭代1：能力目录内新增统一工作区，旧 `ability-tests` 入口保留兼容提示，路由可回退不影响联调。
- 进展（2026-03-05）：已完成“能力详情/测试并入能力目录”迭代2：旧侧栏入口下线，保留 `#nav=ability-tests` 兼容跳转到能力目录测试 Tab，并同步迁移文档说明。
- 进展（2026-04-25）：管理端已新增“业务能力”“模型弹药库”“能力健康/调用统计”等视角，正在从底层执行器配置页转向业务可理解的管理入口；下一步要继续降低概念密度。

4. `doing` 状态与错误口径统一落地检查
- 产物：状态映射核对表 + 缺口清单
- 验收：不存在“上游失败标成功”
- 进展（2026-03-04）：已新增 `docs/strategy/status-error-audit-2026q2.md`，完成第一版核对矩阵与缺口优先级；已补 `docs/testing/COMFYUI_TASK_STATE_REGRESSION_PLAN.md` 与错误映射在管理端/评测端的首轮落地。
- 进展（2026-03-05）：已新增 `backend/tests/test_eval_review_progress_contract.py`，补齐批量评测标注进度的关键契约单测（页码归一、默认值、403/404 错误码）。
- 进展（2026-03-05）：已补齐错误码总表缺口（`ABILITY_TASK_FAILED/CANCELLED`、`RUN_CREATE_FAILED`、`KIE_ABILITY_NOT_CONFIGURED`、`KIE_TASK_FAILED`），并通过 `scripts/check_error_catalog.py` 校验。
- 进展（2026-03-05）：已产出状态/错误回归报告 `docs/testing/STATUS_ERROR_REGRESSION_REPORT_2026-03-05.md`，明确已覆盖项与剩余线上风险。
- 进展（2026-03-05）：已补 API 层契约回归 `backend/tests/test_eval_review_api_contract.py`，覆盖 `review-groups/review-progress` 的 400/409 关键错误场景与分页归一逻辑。
- 进展（2026-03-05）：已新增线上冒烟清单 `docs/testing/STATUS_ERROR_ONLINE_SMOKE_CHECKLIST.md`，用于发布后快速核对状态/错误语义一致性。
- 进展（2026-03-05）：已新增 `scripts/status_error_regression.sh`，并接入 `scripts/deploy_preflight.sh`（可通过 `RUN_STATUS_ERROR_CHECKS=1` 打开专项回归）。
- 进展（2026-03-05）：已补“失败兜底错误码”映射（`ABILITY_TASK_FAILED/ABILITY_TASK_CANCELLED/CALLBACK_FAILED`）与 Coze 查询接口 snake_case 兼容字段，降低联调歧义。

5. `doing` 文档治理上线
- 产物：归档目录、文档 owner、每周回顾机制
- 验收：新增任务全部进入本待办池
- 进展（2026-03-04）：已新增 owner 清单（`docs/strategy/doc-governance-owners-2026q2.md`）与每周回顾模板（`docs/strategy/weekly-review-template.md`）。
- 进展（2026-04-25）：`docs/README.md`、`docs/architecture.md`、`docs/api/modules/business.md`、`docs/plans/2026-04-24-vendor-api-ops-mvp.md` 已同步当前中台/Coze/执行面边界；仍需持续清理旧待办入口。

## P1（商用骨架，3-5 周）

1. `todo` 统一认证与角色模型
- 注册登录、基础角色、会话策略
- 下一步：先落账号、会话、角色、租户/业务方字段，为 API 对外、统计隔离、收费和权限控制打基础。

2. `doing` 充值与账单 MVP
- 余额、充值、扣费明细、账单导出
- 进展（2026-03-04）：钱包余额、支出流水、使用量统计、充值订单、账单和成本快照已有基础接口；支付网关和面向用户的完整账单体验延期。
- 当前缺口（2026-04-25）：缺租户/用户体系承接，缺管理端账单页，缺发布前回归报告。

3. `doing` 成本核算规则
- 按模型、任务、输出类型计算成本并落库
- 进展（2026-04-25）：vendor-api-ops 与业务运行记录已预留并回填耗时、成本、额度字段；还需要把模型成本规则、套餐消耗和业务账单口径统一成正式规则。

4. `todo` 关键页面 UX 重构
- 任务页、结果页、工作台首页
- 说明：客户端当前不是本轮主线，待业务 API、认证、计费骨架稳定后再推进。

5. `doing` 文案系统 V1
- 错误文案、空状态文案、操作提示文案统一
- 进展（2026-03-04）：已新增 `docs/standards/copywriting-system-v1.md` 与 `docs/standards/error-message-map-v1.md` 初稿，并已在管理端/评测端部分页面接入映射。
- 当前缺口（2026-04-25）：业务能力、模型弹药库、能力健康、评测端仍需继续减少技术术语，优先使用“业务能看懂”的描述。

6. `doing` 第三方 API 原子能力执行面
- 产物：`vendor-api-ops` MVP、OpenAI 类特殊网络能力接入准则、API Key 托管/轮换边界
- 验收：backend 通过 executor 调用 vendor-api-ops，Coze 工具箱仍只指向 backend，OpenAI 出网能力不依赖 Coze 主机
- 进展（2026-04-24）：已确认 Coze 主机直连 `api.openai.com` 超时；已定稿原子能力分类准则（`docs/standards/atomic-ability-boundary.md`）与 `vendor-api-ops` v2 方案（`docs/plans/2026-04-24-vendor-api-ops-mvp.md`）。代码侧已接入 `POST/GET /v1/invocations`、Key 隐藏读取、SQLite 持久化、KIE 真实 submit/poll adapter、OpenAI/OpenAI-compatible Images adapter、`vendor_api` executor、OpenAI 图片编辑能力 seed，以及 backend 对 Baidu/Volcengine/KIE/OpenAI 的 vendor-api 优先路由。
- 进展（2026-04-25）：已补 vendor-api-ops Key 级并发保护、最近调用统计、KIE 临时失败轻量重试；管理端“模型弹药库”展示 24h 调用数/成功率/错误分布，backend 代理新增 `/api/admin/vendor-api/usage/summary`。
- 进展（2026-04-25）：已补能力健康汇总与手动刷新接口，管理端“能力目录”展示正常/需关注/异常/未测试/需要复测；业务 OpenAPI 增加错误响应枚举，便于 Coze/业务方按错误码处理。
- 进展（2026-04-25）：能力健康清单增加筛选和 CSV 导出，可按需要复测、异常、未测试、超时未测等口径生成上线前验证清单。
- 进展（2026-04-25）：业务 API 支持图裂变/扩图常用参数顶层传入，同时保留 `inputs` 旧格式兼容，降低业务方接入理解成本。
- 进展（2026-04-25）：业务 API 运行记录补齐 `traceId/requestId/tenantId/clientId/channel/source`、耗时和成本/配额预留字段；底层能力日志的成本信息会回填到业务任务与步骤，为后续收费、灰度和对外 API 报表打基础。
- 进展（2026-04-25）：管理端业务能力页新增调用统计视角，后端提供 `/api/admin/business/usage-summary`，可按业务、版本、来源、业务方、客户端和追踪 ID 查看调用量、成功率、失败样本、平均耗时、成本和额度。
- 进展（2026-04-27）：模型弹药库新增 Key 池交互说明与 Secret Key 输入；`vendor-api-ops` 敏感接口支持服务 token 保护；“验证 Key”会优先使用 Key 池 active Key 访问厂商检查接口，并区分网络可达、缺 Key、鉴权失败。单条 Key 支持独立验证，结果写入 `metadata.lastCheck` 并在 Key 池列表展示最近验证状态。
- 进展（2026-04-27）：根据最新边界调整，第三方 Key 权威回收到中台 `api_keys` 表；`vendor-api-ops` 改为白名单保护的干净执行通道，支持中台随请求传入本次选中的 Key，并避免把请求级凭证写入明文调用记录。`vendor-api-ops` 本地 Key 加密能力仅作为历史兼容，不作为新能力接入路径。

7. `doing` 业务能力层与版本治理
- 产物：`/api/business/*` 稳定入口、业务版本/配方、默认版本切换、灰度、回滚、业务运行记录。
- 验收：图裂变和扩图可以不改业务方入参，通过中台切换底层版本；管理端能看到发布时间、默认版本、最近调用、失败样本和成本字段。
- 进展（2026-04-25）：图裂变、扩图样板业务已落地，业务运行统计已接入管理端；下一步是补认证/租户后，把业务方隔离、额度和对外 API 契约接上。

## P2（增长与扩端，4-8 周）

1. `todo` 模板与复用机制
- 收藏模板、历史复跑、一键复用

2. `todo` 留存机制
- 结果对比、进度提示、回访提醒

3. `todo` 移动端/小程序 IA
- 先做 IA 与关键路径，不直接开发全功能

4. `todo` API 商业化策略
- 接口套餐、限流策略、配额展示

---

## 本周执行单（滚动）

1. `doing` 业务能力层稳定化
- 目标：图裂变/扩图业务 API、版本治理、业务运行统计和管理端展示形成可发版闭环。
- 当前进展：业务运行观测字段、统计接口、管理端统计卡片、文档已完成；待服务器迁移执行 `alembic upgrade head` 后上线验证。

2. `doing` 统一认证与角色模型第一阶段
- 目标：账号、会话、角色、租户/业务方最小模型落地。
- 验收：业务 API、管理端、后续收费统计都能识别调用方，不再只靠松散的 `source/tenantId/clientId` 字段。
- 当前进展（2026-04-25）：后端已补用户归属字段、登录会话、邀请码注册、刷新 token 会话轮换、管理员查询/踢出会话、禁用邀请码和登录失败限流；管理端“账号权限”第一阶段闭环已补齐；待上线迁移验证。

3. `doing` 第三方 API 执行面生产化
- 目标：vendor-api-ops 的 Key 并发、错误、统计、OpenAI/KIE 等 provider 接入继续稳定。
- 当前进展：MVP 已可用；下一步要补 provider/model 管理、Key 状态治理和线上失败样本面板。

4. `doing` 管理端易用性降噪
- 目标：业务人员先看到“业务能力、版本、发布时间、最近状态、失败原因”，底层 executor/workflow/vendor 细节默认降权。
- 当前进展：业务能力页已有基础；模型弹药库和能力目录仍需继续减少技术术语。

## 下周前可执行拆分（2026-04-25 版）

1. **认证与角色第一阶段**
- 已完成后端用户归属字段、会话表、邀请码表、注册/登录/刷新/登出/查询接口、会话踢出、邀请码失效、登录失败限流、错误码、目标回归测试和管理端第一阶段入口。
- 下一步上线迁移验证，再进入更细的角色权限和业务方隔离策略。
- `user_roles` 暂不拆表，第一阶段继续使用 `users.role`，避免提前复杂化。

2. **业务 API 对外化准备**
- 梳理图裂变/扩图对外字段，形成“业务方只看得懂”的接口说明。
- 把业务运行统计接到租户/调用方维度。
- 明确灰度、默认版本、回滚的操作流程。

3. **成本核算规则收敛**
- 把 vendor-api-ops 成本、Ability 日志成本、业务运行成本三层口径对齐。
- 明确哪些字段进入正式账单，哪些字段只做排查。
- 补充重复回调、防重扣、失败不扣费的回归路径。

4. **管理端易用性第二轮**
- 优先改业务能力、模型弹药库、能力目录三个页面。
- 减少英文和底层概念，把“接下来该做什么”放在主位置。
- 保留高级配置，但默认折叠或放到详情里。

*最后更新: 2026-04-25*
