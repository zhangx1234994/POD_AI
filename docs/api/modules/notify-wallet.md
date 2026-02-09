# 通知 / 钱包 / 积分接口

## 用途

- 提供任务状态通知（WebSocket/SSE）。
- 临时积分与钱包扣费接口（占位实现，便于联调）。

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

## 3) 临时积分接口（/api/op/v1 与 /api/os/v1）

> 这是一组临时积分接口，后续会被正式服务替换。

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
