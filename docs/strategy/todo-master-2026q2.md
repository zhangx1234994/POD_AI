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

---

## P0（先做，2-3 周）

1. `todo` 战略指标面板落地
- 产物：北极星与 5 个 KPI 的数据定义、口径说明、查询来源
- 验收：每周可自动出一次指标快照

2. `todo` 用户分层与主路径图
- 产物：三类用户 Top3 路径图
- 验收：评审通过后作为 IA 设计输入

3. `doing` 信息架构 V1
- 产物：一级导航、二级页面、主工作区定义
- 验收：侧边栏与页面框架统一
 - 进展（2026-03-04）：已完成 strategy 文档骨架与管理端响应式第一轮改造；ComfyUI 管理已落地“分类 + 模块”二级导航，并完成“同步发布”三步面板、单主 CTA、次级面板折叠、失败后建议文案；已补超窄屏自适配与状态列命名统一，下一步做 IA 评审与模块拆分图
 - 进展（2026-03-05）：已完成“能力详情/测试并入能力目录”迭代1：能力目录内新增统一工作区，旧 `ability-tests` 入口保留兼容提示，路由可回退不影响联调。
 - 进展（2026-03-05）：已完成“能力详情/测试并入能力目录”迭代2：旧侧栏入口下线，保留 `#nav=ability-tests` 兼容跳转到能力目录测试 Tab，并同步迁移文档说明。

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

## P1（商用骨架，3-5 周）

1. `todo` 统一认证与角色模型
- 注册登录、基础角色、会话策略

2. `todo` 充值与账单 MVP
- 余额、充值、扣费明细、账单导出

3. `todo` 成本核算规则
- 按模型、任务、输出类型计算成本并落库

4. `todo` 关键页面 UX 重构
- 任务页、结果页、工作台首页

5. `todo` 文案系统 V1
- 错误文案、空状态文案、操作提示文案统一

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

1. `doing` 完成 IA V1 草图并评审
- 进展（2026-03-04）：已输出 IA 评审包（`docs/wip/admin-ia-draft.md`），待评审会确认“保留/调整/延期”结论。
2. `doing` 确认充值与计费字段模型
- 进展（2026-03-04）：已输出字段草案 + 接口草案 + 迁移顺序（`docs/wip/auth-billing-model-draft.md`），并新增实施清单（`docs/strategy/auth-billing-implementation-checklist-2026q2.md`）与回归计划（`docs/testing/AUTH_BILLING_TEST_PLAN.md`）；`/api/wallet/v1/balance|expenses|usage-summary|recharge-orders|ledger|bills|cost-snapshots` 已落地，当前为“DB 优先 + 未迁移环境回退内存”模式；充值状态机（`pending->paid/failed/canceled`）已接入，回调 token + 签名校验、`taskId/traceId/provider/modelKey` 流水追踪已补齐；已新增 `task_cost_snapshots + pricing_version`，并将能力任务成功后的自动结算接入钱包幂等扣费。当前业务口径调整为“以支出流水与使用量统计为主，充值链路仅内部运维使用”，支付网关对接延期。
3. `done` 制定认证方案选型结论（手机号/邮箱/邀请码）
- 结论（2026-03-04）：已定稿（`docs/strategy/auth-scheme-decision-2026q2.md`），Q2 先落地“邮箱+邀请码”，手机号延期到 Q3。
4. `doing` 完成文案规范初稿（至少覆盖任务、结果、错误三块）
- 进展（2026-03-04）：已新增 `docs/standards/copywriting-system-v1.md` 与 `docs/standards/error-message-map-v1.md` 初稿，并已在管理端/评测端部分页面接入映射。

## 下周前可执行拆分（2026-03-04 版）

1. **IA V1（进行中）**
- 输出管理端 IA 模块拆分图（含一级导航、二级模块、主工作区）
- 组织一次评审并记录“保留/调整/延期”三类结论
- 将通过项写回 `docs/wip/admin-ia-draft.md`

2. **状态与错误口径（进行中）**
- 按 `docs/strategy/status-error-audit-2026q2.md` 补齐 6 个领域缺口
- 产出“错误码 -> 前端提示文案”映射首版（高频 20 条）
- 在发版检查中新增状态/错误核对项

3. **认证与计费（待开始）**
- 明确账号体系最小字段（用户、会话、角色）
- 明确计费模型最小字段（任务、成本、账单）
- 输出 DB 字段草案与接口草案（先文档后开发）

4. **文案规范（待开始）**
- 统一任务状态文案模板（提交/回调/最终）
- 统一错误文案模板（原因 + 建议动作 + 保留错误码）
- 统一空状态文案模板（无数据/筛选无结果/功能未配置）

*最后更新: 2026-03-04*
