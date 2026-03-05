# 异步任务（AbilityTask）

## 用途

- 统一的异步任务提交与状态查询（能力调用长耗时场景）。
- 适用于批量任务、ComfyUI/KIE 等需要轮询的能力。

## 鉴权

- 需要 `Authorization: Bearer <accessToken>`。

---

## 1) 提交任务（异步）

### POST /api/ability-tasks

**请求体**（示例）

```json
{
  "abilityId": "comfyui_yinhua_tiqu",
  "inputs": { "prompt": "提取印花" },
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png"
}
```

**响应体**

```json
{ "id": "task_20260209_0001", "status": "queued", "createdAt": "2026-02-13T12:00:00Z" }
```

**说明**

- 任务进入后台执行队列，前端需轮询查询状态。

**错误（常见）**

- `ABILITY_NOT_FOUND` / `ABILITY_INACTIVE`
- `EXECUTOR_NOT_FOUND` / `EXECUTOR_NOT_AVAILABLE`
- `QUEUE_FULL` / `COMFYUI_QUEUE_FULL`
- `TASK_CREATE_FAILED`

---

## 2) 查询任务状态

### GET /api/ability-tasks/{task_id}

**响应体**

```json
{
  "id": "task_20260209_0001",
  "status": "running",
  "resultAssets": [],
  "errorMessage": null
}
```

**状态约束**

- 仅允许：`queued` / `running` / `succeeded` / `failed` / `cancelled`
- 若为 `failed`，应返回 `errorMessage`（推荐）
- 展示层若出现 `success/completed` 等历史值，必须按一致性准则做兼容映射（见 `docs/standards/interface-consistency.md`）

**错误（常见）**

- `TASK_NOT_FOUND`
- `TASK_STATUS_UNKNOWN`

---

## 3) 任务列表

### GET /api/ability-tasks

**参数**

- `limit`（1-200）

**响应体**

```json
{
  "items": [],
  "total": 0
}
```

**错误（常见）**

- `INVALID_PAGINATION`
- `UNAUTHORIZED`

---

## 4) 说明（旧链路）

- `/api/tasks/v1/*` 仍保留为历史任务中心链路（内部兼容），状态口径为 `pending/running/completed/failed`。
- 新需求一律使用 `/api/ability-tasks`（统一能力异步入口），状态口径为 `queued/running/succeeded/failed/cancelled`。
- 同一页面若同时展示两类任务，必须先做状态映射再渲染，避免用户误解。
