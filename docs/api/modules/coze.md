# Coze 插件接口

## 用途

- 将 PODI 能力以 Coze Studio Tools 形式暴露。
- 提供统一的“提交 + 回调查询 + 队列状态”能力。

## 鉴权

- **内网访问优先**：由 `COZE_TRUSTED_IPS` 放行。
- **或使用服务 Token**：`Authorization: Bearer <SERVICE_API_TOKEN>`。
- 未命中内网/Token 时返回 `INTERNAL_ONLY`。

---

## 1) OpenAPI 文档

### GET /api/coze/podi/openapi.json

**用途**：Coze 插件导入的 OpenAPI 地址。

**示例**

```bash
curl http://127.0.0.1:8099/api/coze/podi/openapi.json
```

---

## 2) 能力列表（可选）

### GET /api/coze/podi/abilities

**用途**：返回可导入 Coze 的能力列表（等同能力清单）。

---

## 3) 调用能力（Tool）

### POST /api/coze/podi/tools/{provider}/{capability_key}

**用途**：执行指定能力（Coze 工具调用）。

**请求体（示例）**

```json
{
  "prompt": "印花提取",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png",
  "output": "callback"
}
```

**响应体（示例）**

```json
{
  "text": null,
  "imageUrl": null,
  "imageUrls": [],
  "taskId": "t1.comfyui.executor_xxx.0e860bd7681542dda28fcc001b2cf372",
  "taskStatus": "running",
  "executorId": "executor_comfyui_xxx",
  "executorName": "ComfyUI-主节点"
}
```

**错误（常见）**

- `INTERNAL_ONLY`
- `ABILITY_NOT_FOUND` / `ABILITY_INACTIVE`
- `EXECUTOR_NOT_FOUND` / `EXECUTOR_TYPE_NOT_*`
- `Q1001` / `Q2001`（队列满）

---

## 4) 查询任务结果

### POST /api/coze/podi/tasks/get

**用途**：轮询异步任务结果（回调 id）。

**请求体**

```json
{ "taskId": "t1.comfyui.executor_xxx.0e860bd7681542dda28fcc001b2cf372" }
```

**响应体（示例）**

```json
{
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png",
  "imageUrls": ["https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png"],
  "taskId": "t1.comfyui.executor_xxx.0e860bd7681542dda28fcc001b2cf372",
  "taskStatus": "succeeded",
  "executorId": "executor_comfyui_xxx",
  "executorName": "ComfyUI-主节点",
  "logId": 12345,
  "requestId": "req_7d0f...",
  "debugResponse": null
}
```

**说明**

- `taskId` 兼容新旧格式：`t1.<provider>.<executor>.<hex>` 或 `<hex>`。
- 若任务仍在运行，`taskStatus=running` 且 `imageUrls` 为空。
- KIE 长耗时任务会先返回 `running`，后续轮询直至有结果或 `KIE_TIMEOUT`。

**错误**

- `TASK_ID_REQUIRED` / `TASK_NOT_FOUND`
- `TASK_FAILED` / `TASK_TIMEOUT` / `KIE_TIMEOUT`

---

## 5) ComfyUI 队列汇总

### POST /api/coze/podi/comfyui/queue-summary

**用途**：返回多节点队列状态，用于 Coze 工作流路由。

**响应体（示例）**

```json
{
  "totalRunning": 2,
  "totalPending": 4,
  "servers": [
    { "executorId": "executor_comfyui_xxx", "running": 1, "pending": 2 }
  ]
}
```

**错误**

- `COMFYUI_QUEUE_STATUS_ERROR` / `COMFYUI_QUEUE_STATUS_INVALID`
