# 通知 / 钱包 / 积分接口

## 用途

- 提供任务状态通知（WebSocket/SSE）。
- 临时积分与钱包扣费接口（占位实现，便于联调）。

> 当前状态：`/api/wallet/v1/*` 仍以占位能力为主；Q2 将逐步替换为真实充值/账单/成本快照能力（见 `docs/wip/auth-billing-model-draft.md`）。

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
{ "userId": "u_123", "taskId": "task_001", "points": 50 }
```

### POST /api/wallet/v1/confirm

**用途**：确认扣费。

**请求体**

```json
{ "holdId": "hold_001" }
```

### POST /api/wallet/v1/release

**用途**：释放冻结积分。

**请求体**

```json
{ "holdId": "hold_001" }
```

### GET /api/wallet/v1/transactions

**用途**：查询流水（占位实现）。

**参数**：`userId`

### GET /api/wallet/v1/statistics

**用途**：查询用户统计（占位实现）。

**参数**：`userId`

---

## 4) Q2 规划接口（未上线）

### GET /api/wallet/v1/balance
- 用途：查询用户钱包余额（可用/冻结）。

### POST /api/wallet/v1/recharge-orders
- 用途：创建充值订单。
- 预计错误：`RECHARGE_AMOUNT_INVALID`

### GET /api/wallet/v1/recharge-orders/{order_no}
- 用途：查询充值订单状态。

### GET /api/wallet/v1/ledger
- 用途：查询流水分页（支持按类型/时间筛选）。

### GET /api/wallet/v1/bills
- 用途：查询月账单汇总。

### GET /api/wallet/v1/cost-snapshots
- 用途：查询任务成本快照（按平台/模型）。

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
