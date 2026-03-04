# 通知 / 钱包 / 积分接口

## 用途

- 提供任务状态通知（WebSocket/SSE）。
- 提供钱包冻结、释放、充值、流水、账单、成本快照能力（DB 优先；若钱包表未迁移则自动回退内存模式）。

> 当前状态：`/api/wallet/v1/*` 已可联调完整钱包流程；`wallet_accounts/wallet_holds/wallet_ledger/recharge_orders` 迁移完成后自动进入持久化模式。

**迁移与初始化建议**

1. `cd backend && python3 -m alembic upgrade head`
2. `python3 backend/scripts/init_wallet_accounts.py --apply`

---

## 1) 通知

### WS /api/notify/v1/stream

**用途**：建立 WebSocket 连接，接收任务/钱包事件。

**事件示例**

```json
{
  "type": "task.status",
  "payload": { "taskId": "task_001", "status": "running", "progress": 30 }
}
```

### POST /api/notify/v1/event

**用途**：服务端推送事件（内部调用）。

**请求体**

```json
{ "type": "echo", "payload": { "message": "hello" } }
```

---

## 2) 钱包服务（/api/wallet/v1）

### POST /api/wallet/v1/freeze

**用途**：冻结积分（任务提交时）。

**请求体**

```json
{ "userId": "u_123", "taskId": "task_001", "action": "comfyui.yinhua_tiqu", "channel": "eval", "points": 50 }
```

**响应体**

```json
{ "holdId": "hold_9fc0a3f7f8df8e", "balance": 450 }
```

**错误码**

- `WALLET_INSUFFICIENT`（402）

### POST /api/wallet/v1/confirm

**用途**：任务成功后确认扣费（扣除冻结积分）。

**请求体**

```json
{ "holdId": "hold_9fc0a3f7f8df8e" }
```

**响应体**

```json
{ "success": true, "deducted": 50 }
```

**错误码**

- `WALLET_HOLD_NOT_FOUND`（404）

### POST /api/wallet/v1/release

**用途**：任务失败/取消后释放冻结积分。

**请求体**

```json
{ "holdId": "hold_9fc0a3f7f8df8e" }
```

**响应体**

```json
{ "success": true, "released": "hold_9fc0a3f7f8df8e", "userId": "u_123", "balance": 500 }
```

**错误码**

- `WALLET_HOLD_NOT_FOUND`（404）

### GET /api/wallet/v1/statistics

**用途**：查询用户积分统计。

**参数**：`userId`

**响应体**

```json
{ "totalPoints": 500, "tempPoints": 0, "frozenPoints": 0, "grantedToday": 0 }
```

### GET /api/wallet/v1/balance

**用途**：查询钱包余额（可用 + 冻结）。

**参数**：`userId`

**响应体**

```json
{ "userId": "u_123", "balance": 500, "frozenBalance": 0, "currency": "CNY" }
```

### POST /api/wallet/v1/recharge-orders

**用途**：创建充值订单（初始状态 `pending`，不立即入账）。

**请求体**

```json
{ "userId": "u_123", "amount": 1000, "channel": "manual" }
```

**响应体**

```json
{
  "orderNo": "rc_20260304163030_9af812",
  "userId": "u_123",
  "amount": 1000,
  "channel": "manual",
  "status": "pending",
  "createdAt": "2026-03-04T08:30:30.123456+00:00",
  "paidAt": null,
  "failReason": null,
  "transactionId": null,
  "updatedAt": "2026-03-04T08:30:30.123456+00:00"
}
```

**错误码**

- `RECHARGE_AMOUNT_INVALID`（400）

### GET /api/wallet/v1/recharge-orders/{order_no}

**用途**：查询充值订单状态。

**错误码**

- `RECHARGE_ORDER_NOT_FOUND`（404）

### POST /api/wallet/v1/recharge-orders/{order_no}/status

**用途**：支付回调/人工处理订单状态（`pending -> paid|failed|canceled`）。

**鉴权（可选）**

- 当后端配置 `WALLET_CALLBACK_TOKEN` 时，请求必须携带以下任一方式：
  - Header：`X-Wallet-Callback-Token: <token>`
  - Header：`Authorization: Bearer <token>`
  - Query：`?callback_token=<token>`
- 未配置 `WALLET_CALLBACK_TOKEN` 时保持兼容，不强制校验。

**请求体**

```json
{ "status": "paid", "transactionId": "txn_20260304_001" }
```

或

```json
{ "status": "failed", "failReason": "payment_timeout" }
```

**规则**

- `paid` 首次成功会入账并写 `wallet_ledger`，重复 `paid` 幂等不重复入账。
- 终态订单（`paid/failed/canceled`）不可逆，跨终态更新返回冲突。

**错误码**

- `RECHARGE_STATUS_INVALID`（400）
- `RECHARGE_ORDER_NOT_FOUND`（404）
- `RECHARGE_ORDER_STATUS_CONFLICT`（409）
- `RECHARGE_CALLBACK_UNAUTHORIZED`（401，启用回调 token 且校验失败）

### GET /api/wallet/v1/transactions

**用途**：兼容旧接口，返回流水列表（不含分页字段）。

**参数**：`userId`、`page`、`pageSize`

### GET /api/wallet/v1/ledger

**用途**：查询流水分页（推荐）。

**参数**：`userId`、`page`、`pageSize`

**响应体**

```json
{
  "userId": "u_123",
  "total": 2,
  "page": 1,
  "pageSize": 20,
  "items": [
    {
      "id": "txn_1",
      "changeType": "INCREASE",
      "points": 1000,
      "beforeBalance": 500,
      "afterBalance": 1500,
      "taskId": null,
      "description": "recharge:rc_...",
      "provider": null,
      "modelKey": null,
      "createdAt": "2026-03-04T08:30:30.123456+00:00"
    }
  ]
}
```

### GET /api/wallet/v1/bills

**用途**：查询月账单汇总。

**参数**：`userId`、`month`（可选，格式 `YYYY-MM`，默认当月）

**错误码**

- `BILL_MONTH_INVALID`（400）

### GET /api/wallet/v1/cost-snapshots

**用途**：查询成本快照（当前从负向流水聚合）。

**参数**：`userId`、`provider`（可选）、`modelKey`（可选）

**响应体**

```json
{
  "userId": "u_123",
  "provider": null,
  "modelKey": null,
  "count": 1,
  "totalPoints": 50,
  "items": [{ "date": "2026-03-04", "provider": "unknown", "modelKey": "unknown", "points": 50, "taskId": "task_001" }]
}
```

---

## 3) 临时积分接口（/api/op/v1 与 /api/os/v1）

> 历史接口（已下线，仅保留文档记录），当前后端未启用。  
> 实际积分/钱包以 `/api/wallet/v1/*` 与 AbilityTask 结果为准。

### POST /api/op/v1/img/points-cost
### POST /api/os/v1/img/points-cost

**用途**：计算本次任务消耗积分。

**请求体**

```json
{ "userId": "u_123", "action": "comfyui.yinhua_tiqu", "imagesCount": 1 }
```

### GET /api/op/v1/points/statistics
### GET /api/os/v1/points/statistics

**参数**：`userId`

### GET /api/op/v1/points/transactions
### GET /api/os/v1/points/transactions

**参数**：`userId`、`page`、`size`
