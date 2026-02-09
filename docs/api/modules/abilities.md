# 统一能力调用接口

## 用途

- 对外统一暴露“能力清单 + 调用 + 异步任务”。
- 前端/业务系统仅需对接这一套接口。

## 鉴权

- **读取清单**：`GET /api/abilities` 无需登录。
- **调用/任务**：需 `Authorization: Bearer <accessToken>`。

---

## 1) 能力清单

### GET /api/abilities

**用途**：返回所有已激活能力的基础信息、默认参数与输入 schema。

**响应示例**

```json
{
  "items": [
    {
      "id": "comfyui_yinhua_tiqu",
      "provider": "comfyui",
      "category": "image_generation",
      "capabilityKey": "yinhua_tiqu",
      "version": "v1",
      "displayName": "ComfyUI · 印花提取",
      "description": "Qwen Image Edit + 印花 LoRA",
      "status": "active",
      "abilityType": "comfyui",
      "workflowId": "workflow_comfyui_pattern_extract_v1",
      "executorId": "executor_comfyui_pattern_extract_158",
      "defaultParams": {
        "workflow_key": "yinhua_tiqu",
        "timeout": 420,
        "output_width": 1800,
        "output_height": 1800,
        "lora_name": "杯子1124.safetensors"
      },
      "inputSchema": { "fields": [] },
      "metadata": {
        "api_type": "comfyui_workflow",
        "requires_image_input": true
      },
      "requiresImage": true,
      "supportsMultipleImages": false,
      "maxOutputImages": null
    }
  ]
}
```

### GET /api/abilities/{abilityId}

**用途**：获取单个能力详情。

---

## 2) 能力调用

### POST /api/abilities/{abilityId}/invoke

**用途**：调用指定能力并返回结果（同步）。

**请求体**

```json
{
  "executorId": "可选，覆盖能力默认节点",
  "inputs": {
    "prompt": "春日田野风景，布面油画风格",
    "output_width": 1024,
    "output_height": 1024
  },
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png",
  "imageBase64": null,
  "images": [
    { "name": "ref-1", "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/ref1.png" }
  ],
  "metadata": {
    "requestFrom": "podi-eval-web",
    "traceId": "trace-001"
  },
  "callbackUrl": "https://example.com/webhook",
  "callbackHeaders": { "Authorization": "Bearer xxx" }
}
```

**响应体**

```json
{
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "status": "succeeded",
  "requestId": "req_7d0f...",
  "logId": 12345,
  "durationMs": 842,
  "images": [
    { "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png", "type": "image" }
  ],
  "assets": [
    { "ossUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/output.png", "tag": "comfyui-image" }
  ],
  "metadata": {
    "taskId": "prompt-87c5c0..."
  },
  "raw": {
    "...": "原始返回（已脱敏）"
  }
}
```

**错误（常见）**

- `ABILITY_NOT_FOUND` / `ABILITY_INACTIVE`
- `ABILITY_EXECUTOR_NOT_CONFIGURED`
- `EXECUTOR_NOT_FOUND` / `EXECUTOR_TYPE_NOT_*`
- `IMAGE_REQUIRED` / `COMFYUI_IMAGE_REQUIRED`
- `COMFYUI_TIMEOUT` / `KIE_TIMEOUT`

---

## 3) 能力选项（公共）

### GET /api/abilities/options

**用途**：获取能力选项（供前端动态表单使用）。

**请求参数**

- `status`：默认 `active`
- `provider`：可选（如 `comfyui` / `volcengine` / `kie`）

---

## 4) 异步任务

### POST /api/ability-tasks

**用途**：提交异步任务（与 invoke 参数一致，额外带 abilityId）。

**请求体**

```json
{
  "abilityId": "comfyui_yinhua_tiqu",
  "inputs": { "prompt": "印花提取" },
  "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png"
}
```

**响应体**

```json
{
  "id": "f61f2dd0f7dd4f479e7d97f6b0fa0f8b",
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "status": "queued",
  "logId": 12345,
  "createdAt": "2026-02-09T10:00:00Z"
}
```

### GET /api/ability-tasks

**用途**：查询最近任务列表（默认 20 条）。

**参数**：`limit`（1-200）

### GET /api/ability-tasks/{taskId}

**用途**：查询单个任务状态与结果。

**响应体**（状态字段）

- `status`：`queued` / `running` / `succeeded` / `failed`
- `resultPayload`：成功结果（含图片/视频/文本）
- `errorMessage`：失败原因

**错误**

- `TASK_NOT_FOUND`

---

## 5) 回调（可选）

当 `callbackUrl` 被提供时，服务端会在任务完成/失败后 POST 回调。示例：

```json
{
  "status": "success",
  "abilityId": "comfyui_yinhua_tiqu",
  "provider": "comfyui",
  "requestId": "req_7d0f...",
  "logId": 12345,
  "durationMs": 842,
  "result": { "images": ["..."] },
  "error": null,
  "timestamp": "2026-02-09T10:02:01Z"
}
```
