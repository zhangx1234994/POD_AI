# 任务提交与调度接口

## 用途

- 旧任务链路（tasks/task_events）的提交与状态查询。
- 与钱包冻结/扣费、通知系统联动。

## 鉴权

- 当前接口未强制 Bearer（内部使用），生产建议通过网关限制。

---

## 1) 提交任务

### POST /api/tasks/v1/submit

**请求体**（示例）

```json
{
  "taskId": "task_20260209_0001",
  "userId": "u_123",
  "action": "comfyui.yinhua_tiqu",
  "points": 50,
  "channel": "admin",
  "inputPayload": {
    "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png"
  }
}
```

**响应体**

```json
{ "taskId": "task_20260209_0001", "status": "pending" }
```

**说明**

- 会调用钱包冻结积分，并广播通知事件。

---

## 2) 查询任务状态

### GET /api/tasks/v1/{task_id}

**响应体**

```json
{
  "taskId": "task_20260209_0001",
  "status": "running",
  "progress": 30,
  "resultUrl": null
}
```

---

## 3) 任务完成回执

### POST /api/tasks/v1/{task_id}/complete

**参数**：`success=true/false`

**说明**

- 成功：确认扣费并广播通知
- 失败：释放冻结并广播通知

**错误**

- `TASK_NOT_FOUND`
- `HOLD_NOT_FOUND`

---

## 4) 任务列表

### GET /api/tasks/v1

**参数**

- `userId`（必填）
- `action` / `status` / `page` / `size`

**响应体**

```json
{
  "items": [],
  "total": 0,
  "page": 0,
  "size": 10
}
```

---

## 5) 调度

### POST /api/tasks/v1/dispatch

**用途**：批量调度待处理任务（内部使用）。

**参数**：`limit`（1-20）
