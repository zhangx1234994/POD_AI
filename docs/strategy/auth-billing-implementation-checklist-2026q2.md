# 认证与计费实施清单（2026Q2）

> 目标：把认证与计费能力推进到可执行开发任务。
> 输入文档：`docs/strategy/auth-scheme-decision-2026q2.md`。旧 WIP 草稿已删除，避免和当前实现重复。

## 1) 实施顺序（必须按阶段推进）

## 阶段 A：认证基础（先做）

### A1. 数据库迁移
- [x] 补齐表：`users`（display_name/tenant_id/client_id）
- [x] 新增表：`user_sessions`
- [ ] 新增表：`user_roles`
- [x] 新增表：`invite_codes`
- [ ] 初始化管理员脚本（仅内部）

> 2026-04-25 进展：第一阶段继续使用 `users.role`，暂不拆 `user_roles` 表；等租户、业务方和客户端边界稳定后再补多角色模型。

### A2. 后端接口
- [x] `POST /api/auth/register`（邮箱 + 邀请码）
- [x] `POST /api/auth/login`（邮箱 + 密码）
- [x] `POST /api/auth/refresh`
- [x] `POST /api/auth/logout`
- [x] `GET /api/auth/sessions`
- [x] `GET /api/auth/sessions/all`（管理员）
- [x] `POST /api/auth/sessions/{sessionId}/revoke`（管理员）
- [x] `POST /api/auth/invite-codes`（管理员）
- [x] `GET /api/auth/invite-codes`（管理员）
- [x] `POST /api/auth/invite-codes/{inviteId}/disable`（管理员）
- [x] `GET /api/auth/users`（管理员）
- [x] `PATCH /api/auth/users/{userId}`（管理员调整角色、状态、业务方范围）
- [x] `GET /api/auth/scope-summary`（账号范围与风险摘要）

### A3. 回归检查
- [x] 邀请码失效/重复使用可返回明确错误码
- [x] 登录失败触发限流策略
- [x] 刷新 token 过期/吊销路径正确
- [x] 管理员不能停用或降权自己
- [x] 停用用户会踢出该用户 active 会话
- [x] 管理端账号权限页依赖的 scope-summary 有后端接口闭环
- [x] 角色边界上线验收：管理员、业务方账号、服务 Token、Coze 工具箱四类调用方均有允许/禁止范围，并纳入发布 smoke

---

## 阶段 B：钱包基础

### B1. 数据库迁移
- [x] 新增表：`wallet_accounts`
- [x] 新增表：`wallet_ledger`
- [x] 新增表：`recharge_orders`
- [x] 存量用户钱包初始化脚本（`python3 backend/scripts/init_wallet_accounts.py --apply`）

### B2. 后端接口
- [x] `GET /api/wallet/v1/balance`（内存版，待数据库持久化）
- [x] `POST /api/wallet/v1/expenses`（直接支出记账，支持 traceId 幂等）
- [x] `POST /api/wallet/v1/adjustments`（人工调账/退回，支持 traceId/taskId 幂等）
- [x] `GET /api/wallet/v1/usage-summary`（使用量统计：日趋势 + provider/model）
- [x] `POST /api/wallet/v1/recharge-orders`（内存版，待支付状态机；当前仅内部运维使用）
- [x] `GET /api/wallet/v1/recharge-orders/{order_no}`（内存版；当前仅内部运维使用）
- [x] `GET /api/wallet/v1/ledger`（内存版）

### B3. 回归检查
- [x] 充值订单状态流转：pending -> paid/failed/canceled（含幂等与冲突保护）
- [x] 充值回调接口支持可选 token 鉴权（`WALLET_CALLBACK_TOKEN`）
- [x] 流水与余额变动一致
- [x] 流水字段包含 `traceId/taskId/provider/modelKey`（状态回调可传入）
- [x] 直接支出接口强制 `traceId/taskId` 幂等键，避免无标识重复扣费
- [x] 人工调账/退回接口支持幂等防重和流水审计
- [x] 业务侧口径：当前阶段只消费“支出流水”能力，充值链路归运维内控

---

## 阶段 C：任务成本入账

### C1. 数据库迁移
- [x] 新增表：`task_cost_snapshots`
- [x] 成本规则版本字段：`pricing_version`

### C2. 后端逻辑
- [x] 任务完成后写成本快照（能力任务成功后按 task_id 幂等）
- [x] 成功任务扣费，失败/取消任务不扣费（能力任务自动结算）
- [x] 重复回调幂等防重
- [x] 业务运行成本回填支持模型目录 `costPolicy` 与能力元数据 `pricing/costPolicy`，厂商不返回成本时仍可按规则估算

### C3. 对外接口
- [x] `GET /api/wallet/v1/bills`（内存版）
- [x] `GET /api/wallet/v1/cost-snapshots`（内存版）

### C4. 回归检查
- [x] 同一任务重复回调不会重复扣费（`traceId=ability_task:{task_id}`）
- [x] 业务运行扣费重试和退款退回均幂等（`business_run:{runId}` / `business_run_refund:{runId}`）
- [x] 账单汇总与流水可对齐
- [x] 成本字段可追溯到 provider/model/task

---

## 阶段 D：前端与管理端接入

### D1. 管理端
- [x] 会话管理页（查看/踢出）
- [x] 邀请码管理页（生成/失效）
- [x] 钱包账单页（流水/导出）
- [x] 套餐发放、套餐订单、月结、发票申请和通知记录的运营骨架
- [x] 业务任务自动结算：套餐优先扣减，套餐不足时钱包兜底，退款按原扣减方式回补
- [x] 套餐目录和定价规则：订单/人工发放可按套餐标识自动套用默认额度、金额和有效期
- [x] 模型成本规则：模型目录可维护计费单位、单价、币种、套餐消耗和定价版本
- [x] 商业化报表雏形：账期内汇总订单收入、任务成本、套餐消耗、扣费完成度和计费风险
- [x] 商业化报表导出：按摘要、业务明细、风险任务三段导出 CSV
- [x] 账单页业务话术：统一“收费”口径，问题样本显示中文处理建议，不直接展示原始状态值

> 2026-05-04 进展：管理端“账号权限”第一阶段闭环已补齐，可查看用户、全部会话、邀请码、账号范围摘要，并可生成/失效邀请码、踢出指定会话、调整用户角色/状态/业务方范围。
> 2026-05-04 进展：管理端“账单”后端闭环已补齐，接口真源见 `docs/api/modules/admin-billing.md`；当前只做运营骨架，不代表真实支付/开票网关已上线。
> 2026-05-04 进展：业务运行结算已从“人工修复扣费”为主，推进到“终态自动尝试结算 + 后台可重试/退回”；统一结算结果写入 `billingSettlement`。
> 2026-05-04 进展：新增套餐目录和定价规则，减少运营创建订单/发放套餐时重复手填。
> 2026-05-04 进展：模型成本规则增加中文表单和后端校验，减少“成功任务未定价”的配置风险。
> 2026-05-04 进展：新增商业化报表接口和管理端卡片，先服务内部运营复核，不代表正式财务报表已上线。
> 2026-05-04 进展：新增商业化报表 CSV 导出，便于上线前和运营复核留档。
> 2026-05-04 进展：账单页第一轮业务化文案完成，运营优先看到“该处理什么”，原始状态值保留在接口和日志，不作为主提示。

### D2. 评测端
- [x] 统一错误文案与状态词第一轮（引用 `copywriting-system-v1`）
- [x] 关键调用列表展示成本字段（只读）

> 2026-05-04 进展：评测 run 响应补齐 `cost_amount/currency/billing_unit/unit_price` 只读字段，来源于中台能力任务关联的调用日志；评测端任务追踪和单功能历史记录会显示“成本：xxx”，缺失时显示“成本未记录”。
> 2026-05-04 进展：评测端任务追踪页的提交、回填、最终状态改为中文阶段状态；历史筛选和批量标注状态去掉 raw 状态词，错误提示继续走 `errorMessageMap`。

---

## 2) 联调顺序（避免返工）

1. 先完成阶段 A 并灰度。
2. 再落阶段 B（只打通余额/流水，不先做复杂支付）。
3. 最后落阶段 C（成本快照 + 扣费规则）。
4. 前端接入放在每阶段末尾做最小变更联调。

---

## 3) 发布门槛（硬性）

- [x] 新增接口文档已同步到 `docs/api/modules/auth.md` / `docs/api/modules/notify-wallet.md` / `docs/api/modules/admin-billing.md`
- [x] 错误码已同步到 `docs/standards/error-catalog.md`
- [x] 回归报告包含：成功路径 + 至少 5 条失败路径（见 `backend/tests/test_auth_sessions_invites.py`）
- [x] `release-preflight` 补充认证检查项（账号范围摘要、active admin、阻断风险）
- [x] `release-preflight` 补充计费检查项（商业化报表默认阻断未定价和计费异常）

---

## 4) 风险与回滚

### 主要风险
1. 并发回调导致重复扣费
2. 会话失效策略不一致导致误踢用户
3. 旧积分接口与新钱包接口并存期间口径不一致

### 回滚策略
1. 保留旧钱包占位接口作为 fallback（只读）
2. 新扣费逻辑挂 feature flag，异常可快速关闭
3. 账单导出保留双写对账窗口（至少 1 周）

*最后更新: 2026-04-25*
