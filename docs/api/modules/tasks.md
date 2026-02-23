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

---

## 4) 说明（旧链路）

- 旧的 `/api/tasks/v1/*` 已下线，不再维护。
- 统一使用 `/api/ability-tasks` 作为异步任务入口。
