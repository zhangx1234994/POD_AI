# 认证与计费实施清单（2026Q2）

> 目标：把 `auth-billing-model-draft` 从“文档方案”推进到“可执行开发任务”。  
> 输入文档：  
> - `docs/wip/auth-billing-model-draft.md`  
> - `docs/strategy/auth-scheme-decision-2026q2.md`

## 1) 实施顺序（必须按阶段推进）

## 阶段 A：认证基础（先做）

### A1. 数据库迁移
- [ ] 新增表：`users`
- [ ] 新增表：`user_sessions`
- [ ] 新增表：`user_roles`
- [ ] 新增表：`invite_codes`
- [ ] 初始化管理员脚本（仅内部）

### A2. 后端接口
- [ ] `POST /api/auth/register`（邮箱 + 邀请码）
- [ ] `POST /api/auth/login`（邮箱 + 密码）
- [ ] `POST /api/auth/refresh`
- [ ] `POST /api/auth/logout`
- [ ] `GET /api/auth/sessions`
- [ ] `POST /api/auth/invite-codes`（管理员）

### A3. 回归检查
- [ ] 邀请码失效/重复使用可返回明确错误码
- [ ] 登录失败触发限流策略
- [ ] 刷新 token 过期/吊销路径正确

---

## 阶段 B：钱包基础

### B1. 数据库迁移
- [ ] 新增表：`wallet_accounts`
- [ ] 新增表：`wallet_ledger`
- [ ] 新增表：`recharge_orders`
- [ ] 存量用户钱包初始化脚本

### B2. 后端接口
- [x] `GET /api/wallet/v1/balance`（内存版，待数据库持久化）
- [x] `POST /api/wallet/v1/recharge-orders`（内存版，待支付状态机）
- [x] `GET /api/wallet/v1/recharge-orders/{order_no}`（内存版）
- [x] `GET /api/wallet/v1/ledger`（内存版）

### B3. 回归检查
- [ ] 充值订单状态流转：pending -> paid/failed/canceled
- [ ] 流水与余额变动一致
- [ ] 导出字段包含 `trace_id/related_task_id`

---

## 阶段 C：任务成本入账

### C1. 数据库迁移
- [ ] 新增表：`task_cost_snapshots`
- [ ] 成本规则版本字段：`pricing_version`

### C2. 后端逻辑
- [ ] 任务完成后写成本快照
- [ ] 成功任务扣费，失败/取消任务不扣费
- [ ] 重复回调幂等防重

### C3. 对外接口
- [x] `GET /api/wallet/v1/bills`（内存版）
- [x] `GET /api/wallet/v1/cost-snapshots`（内存版）

### C4. 回归检查
- [ ] 同一任务重复回调不会重复扣费
- [ ] 账单汇总与流水可对齐
- [ ] 成本字段可追溯到 provider/model/task

---

## 阶段 D：前端与管理端接入

### D1. 管理端
- [ ] 会话管理页（查看/踢出）
- [ ] 邀请码管理页（生成/失效）
- [ ] 钱包账单页（流水/导出）

### D2. 评测端
- [ ] 统一错误文案与状态词（引用 `copywriting-system-v1`）
- [ ] 关键调用列表展示成本字段（只读）

---

## 2) 联调顺序（避免返工）

1. 先完成阶段 A 并灰度。  
2. 再落阶段 B（只打通余额/流水，不先做复杂支付）。  
3. 最后落阶段 C（成本快照 + 扣费规则）。  
4. 前端接入放在每阶段末尾做最小变更联调。

---

## 3) 发布门槛（硬性）

- [ ] 新增接口文档已同步到 `docs/api/modules/auth.md` / `docs/api/modules/notify-wallet.md`
- [x] 错误码已同步到 `docs/standards/error-catalog.md`
- [ ] 回归报告包含：成功路径 + 至少 5 条失败路径
- [ ] `release-preflight` 补充认证/计费检查项

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

*最后更新: 2026-03-04*
