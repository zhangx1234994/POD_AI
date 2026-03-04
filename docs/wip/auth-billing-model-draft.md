# 认证与计费字段模型草案（WIP）

> 对应待办：`docs/strategy/todo-master-2026q2.md`（本周执行单 2/3）。  
> 目标：先对齐最小可用字段，再进入接口与数据库迁移开发。

## 1. 账号与认证（MVP）

## 1.1 用户主表（users）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| user_code | varchar(32) | 是 | 对外展示 ID |
| login_type | enum(email, phone, invite) | 是 | 注册方式 |
| email | varchar(128) | 否 | 邮箱登录时必填 |
| phone | varchar(32) | 否 | 手机登录时必填 |
| password_hash | varchar(255) | 否 | 密码模式启用时必填 |
| status | enum(active, disabled, deleted) | 是 | 账号状态 |
| created_at / updated_at | datetime | 是 | 审计字段 |

## 1.2 会话表（user_sessions）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 关联用户 |
| session_key | varchar(96) | 是 | 当前会话标识 |
| token_hash | varchar(255) | 是 | 访问令牌摘要 |
| expires_at | datetime | 是 | 过期时间 |
| ip | varchar(64) | 否 | 登录 IP |
| user_agent | varchar(255) | 否 | 设备信息 |
| status | enum(active, revoked, expired) | 是 | 会话状态 |
| created_at / updated_at | datetime | 是 | 审计字段 |

## 1.3 角色与授权（user_roles）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 |
| role | enum(owner, member, admin) | 是 | 角色 |
| scope | varchar(64) | 是 | 作用域（个人/团队/系统） |
| status | enum(active, inactive) | 是 | 状态 |
| created_at / updated_at | datetime | 是 | 审计字段 |

## 2. 计费与账单（MVP）

## 2.1 钱包主表（wallet_accounts）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 |
| balance | decimal(18,4) | 是 | 可用余额 |
| frozen_balance | decimal(18,4) | 是 | 冻结余额 |
| currency | varchar(8) | 是 | 币种（默认 CNY） |
| status | enum(active, frozen, closed) | 是 | 钱包状态 |
| created_at / updated_at | datetime | 是 | 审计字段 |

## 2.2 资金流水（wallet_ledger）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| user_id | bigint | 是 | 用户 |
| wallet_id | bigint | 是 | 钱包 |
| biz_type | enum(recharge, consume, refund, adjust) | 是 | 流水类型 |
| direction | enum(in, out) | 是 | 收入/支出 |
| amount | decimal(18,4) | 是 | 变动金额 |
| balance_after | decimal(18,4) | 是 | 变动后余额 |
| related_task_id | varchar(64) | 否 | 对应任务 |
| trace_id | varchar(64) | 否 | 链路追踪 |
| remark | varchar(255) | 否 | 备注 |
| created_at | datetime | 是 | 发生时间 |

## 2.3 任务成本快照（task_cost_snapshots）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| task_id | varchar(64) | 是 | 任务 ID |
| provider | varchar(32) | 是 | 平台（comfyui/kie/volc 等） |
| model_key | varchar(64) | 是 | 模型标识 |
| input_count | int | 是 | 输入数量（图/视频帧） |
| output_count | int | 是 | 输出数量 |
| unit_cost | decimal(18,6) | 是 | 单位成本 |
| total_cost | decimal(18,4) | 是 | 总成本 |
| pricing_version | varchar(32) | 是 | 成本规则版本 |
| created_at | datetime | 是 | 快照时间 |

## 2.4 充值订单（recharge_orders）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | bigint | 是 | 主键 |
| order_no | varchar(64) | 是 | 订单号 |
| user_id | bigint | 是 | 用户 |
| amount | decimal(18,4) | 是 | 充值金额 |
| channel | varchar(32) | 是 | 渠道（后续扩展） |
| status | enum(pending, paid, failed, canceled) | 是 | 订单状态 |
| paid_at | datetime | 否 | 支付时间 |
| created_at / updated_at | datetime | 是 | 审计字段 |

## 3. 关键约束（上线前必须确认）

1. 成本结算必须有版本号（`pricing_version`），防止历史账单漂移。
2. 余额扣减必须与任务最终状态绑定，禁止“失败任务仍扣费”。
3. 账单导出必须保留 `task_id/trace_id/provider/model_key`。
4. 所有金额字段统一 `decimal`，禁止浮点数。

## 4. 下一步

1. 补接口草案：登录注册、会话续期、充值下单、账单查询、成本查询。
2. 补迁移草案：按 `users -> sessions -> wallet -> ledger -> cost` 顺序。
3. 补风险清单：重复回调、并发扣费、退款幂等。

*最后更新: 2026-03-04*
