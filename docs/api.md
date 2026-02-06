# POD AI Studio API 文档

## 目录

1. [API概述](#api概述)
2. [认证机制](#认证机制)
3. [API基础信息](#api基础信息)
4. [用户管理API](#用户管理api)
5. [媒体服务API](#媒体服务api)
6. [钱包服务API](#钱包服务api)
7. [任务管理API](#任务管理api)
8. [数据统计API](#数据统计api)
9. [错误处理](#错误处理)
10. [API使用示例](#api使用示例)
11. [更新日志](#更新日志)

## API概述

POD AI Studio 提供了一套完整的RESTful API，用于用户认证、图像处理、任务管理和数据统计等功能。所有API都基于HTTP协议，使用JSON格式进行数据交换。

### 基础URL

- **统一 Host（后台服务）**: `http://127.0.0.1:8099`（本地开发建议使用 `127.0.0.1`，避免 `localhost` Cookie/代理差异）
- **开放 API 前缀**: `http://127.0.0.1:8099/api`
  - `auth`：认证登录/刷新
  - `media`：媒资上传凭证
  - `abilities`：统一能力接口（详见下文）
  - `ability-tasks`：异步/批量任务
  - `admin/*`：管理端专用接口（执行节点、能力日志、ComfyUI 管理等）
  - `agent/*`：ComfyUI Agent 管理（清单/任务回执/心跳）
  - `coze/podi/*`：Coze Studio 插件（内部集成用，OpenAPI + Tools）

### Coze 插件（内部集成）

用于把 PODI 的“原子能力”以 Coze Studio Tools 形式暴露（一个能力一个 tool）。

- OpenAPI（给 Coze 导入用）：
  - `GET /api/coze/podi/openapi.json`
- 调用某个能力（tool）：
  - `POST /api/coze/podi/tools/{provider}/{capability_key}`
- 查询异步任务（用于 ComfyUI 等长耗时能力）：
  - `POST /api/coze/podi/tasks/get`

### 数据格式

所有API请求和响应都使用JSON格式，字符编码为UTF-8。

## 认证机制

### Token认证

API使用Bearer Token进行认证。用户登录成功后，服务器会返回一个访问令牌，后续请求需要在HTTP头部中包含此令牌。

```http
Authorization: Bearer <your_token>
```

### 获取Token

```http
POST /api/os/v1/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "user123",
      "username": "your_username",
      "email": "user@example.com",
      "role": "user"
    },
    "expiresIn": 86400
  }
}
```

## API基础信息

### 通用响应格式

所有API响应都遵循统一的格式：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {},
  "timestamp": "2023-07-20T12:00:00Z"
}
```

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 分页参数

列表类API支持分页，使用以下参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码，从1开始，默认1 |
| pageSize | number | 否 | 每页数量，默认20，最大100 |

## 用户管理API

### 用户注册

```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "newuser",
  "password": "password123",
  "email": "newuser@example.com"
}
```

**响应示例**:
```json
{
  "code": 201,
  "message": "注册成功",
  "data": {
    "user": {
      "id": "user456",
      "username": "newuser",
      "email": "newuser@example.com",
      "role": "user",
      "createdAt": "2023-07-20T12:00:00Z"
    }
  }
}
```

### 用户登录

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "existinguser",
  "password": "password123"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": "user123",
      "username": "existinguser",
      "email": "user@example.com",
      "role": "user"
    },
    "expiresIn": 86400
  }
}
```

### 获取当前用户信息

```http
GET /api/auth/me
Authorization: Bearer <token>
```

**响应示例**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "id": "user123",
    "username": "existinguser",
    "email": "user@example.com",
    "role": "user",
    "createdAt": "2023-07-20T12:00:00Z",
    "lastLoginAt": "2023-07-20T14:30:00Z"
  }
}
```

### 更新用户信息

```http
PUT /api/auth/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "newemail@example.com",
  "profile": {
    "firstName": "John",
    "lastName": "Doe"
  }
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "更新成功",
  "data": {
    "id": "user123",
    "username": "existinguser",
    "email": "newemail@example.com",
    "profile": {
      "firstName": "John",
      "lastName": "Doe"
    }
  }
}
```

### 修改密码

```http
PUT /api/os/v1/auth/password
Authorization: Bearer <token>
Content-Type: application/json

{
  "currentPassword": "oldpassword123",
  "newPassword": "newpassword456"
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "密码修改成功"
}
```

## 媒体服务API

Media Service 由 Python（FastAPI + boto3）实现，负责 STS、OSS 回调与下载签名，供前端上传组件与任务结果查看使用。

### 获取上传凭证

```http
POST /api/media/v1/sts
Authorization: Bearer <token>
Content-Type: application/json

{
  "taskId": "tsk_123",
  "action": "hires",
  "fileName": "origin.png",
  "mimeType": "image/png",
  "fileSize": 5242880,
  "channel": "local"
}
```

**响应**

```json
{
  "code": 200,
  "data": {
    "bucket": "pod-oss-private",
    "objectKey": "uploads/tsk_123/origin.png",
    "policy": "...",
    "signature": "...",
    "accessKeyId": "STS...",
    "host": "https://oss-xx.aliyuncs.com",
    "expireIn": 600
  }
}
```

### OSS 回调

```http
POST /api/media/v1/oss-callback
x-oss-signature: ...
x-oss-pub-key-url: ...
Content-Type: application/json

{
  "bucket": "pod-oss-private",
  "object": "uploads/tsk_123/origin.png",
  "size": 5242880,
  "mimeType": "image/png",
  "meta": {
    "taskId": "tsk_123",
    "action": "hires",
    "userId": "u_001"
  }
}
```

服务端校验签名并记录 `media_objects`，必要时触发 Task Orchestrator。

### 下载签名

```http
POST /api/media/v1/signed-download
Authorization: Bearer <token>

{
  "objectKey": "results/tsk_123/result.png",
  "ttl": 300
}
```

返回短期签名 URL，仅限任务所有者或有权限的管理员使用。

### 错误码

| code | message | 说明 |
|------|---------|------|
| MEDIA_STS_INVALID_PARAM | 参数非法 |
| MEDIA_UPLOAD_UNAUTHORIZED | 无上传权限 |
| MEDIA_CALLBACK_INVALID | 回调签名失败 |
| MEDIA_DOWNLOAD_DENIED | 无下载权限 |

## 钱包服务API

Wallet Service 由 Python（FastAPI + SQLAlchemy）提供积分冻结/扣减、流水与统计能力。

### 冻结积分

```http
POST /api/wallet/v1/freeze
Authorization: Bearer <token>

{
  "userId": "u_001",
  "taskId": "tsk_123",
  "action": "hires",
  "points": 50,
  "channel": "local"
}
```

响应：`{"code":200,"data":{"holdId":"hold_abc","balance":450}}`。

### 确认或释放

```http
POST /api/wallet/v1/confirm
Authorization: Bearer <token>

{
  "holdId": "hold_abc"
}
```

失败任务调用 `POST /api/wallet/v1/release`。

### 流水与统计

```http
GET /api/wallet/v1/transactions?userId=u_001&page=1&pageSize=20
Authorization: Bearer <token>
```

```http
GET /api/wallet/v1/statistics?userId=u_001
Authorization: Bearer <token>
```

### 错误码

| code | message | 说明 |
|------|---------|------|
| WALLET_INSUFFICIENT | 积分不足 |
| WALLET_HOLD_CONFLICT | 冻结冲突 |
| WALLET_HOLD_NOT_FOUND | holdId 不存在 |
| WALLET_SERVICE_UNAVAILABLE | 服务不可用 |

## 能力与任务 API

能力调用、AbilityTask 队列、日志/成本详见 `docs/api/abilities.md`，本文仅保留钱包/统计等接口。
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "tasks": [
      {
        "id": "task_789",
        "action": "upscale",
        "status": "completed",
        "createdAt": "2023-07-20T12:00:00Z",
        "completedAt": "2023-07-20T12:05:00Z",
        "params": {
          "scale": 2,
          "model": "esrgan"
        }
      }
    ],
    "pagination": {
      "page": 1,
      "pageSize": 20,
      "total": 100,
      "totalPages": 5
    }
  }
}
```

### 获取任务详情

```http
GET /api/ability-tasks/{taskId}/details
Authorization: Bearer <token>
```

**响应示例**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "id": "task_789",
    "action": "upscale",
    "status": "completed",
    "progress": 100,
    "createdAt": "2023-07-20T12:00:00Z",
    "startedAt": "2023-07-20T12:01:00Z",
    "completedAt": "2023-07-20T12:05:00Z",
    "params": {
      "scale": 2,
      "model": "esrgan"
    },
    "inputImages": [
      {
        "filename": "input_image.jpg",
        "size": 1024576,
        "url": "https://example.com/input/input_image.jpg"
      }
    ],
    "result": {
      "outputImages": [
        {
          "url": "https://example.com/result/image1.jpg",
          "filename": "upscaled_image1.jpg",
          "size": 2048576,
          "width": 2048,
          "height": 2048
        }
      ],
      "metadata": {
        "processingTime": 240,
        "model": "esrgan",
        "scale": 2
      }
    },
    "logs": [
      {
        "timestamp": "2023-07-20T12:01:00Z",
        "level": "info",
        "message": "开始处理图像"
      },
      {
        "timestamp": "2023-07-20T12:05:00Z",
        "level": "info",
        "message": "图像处理完成"
      }
    ]
  }
}
```

### 重试任务

```http
POST /api/ability-tasks/{taskId}/retry
Authorization: Bearer <token>
```

**响应示例**:
```json
{
  "code": 200,
  "message": "任务已重新提交",
  "data": {
    "taskId": "task_790",
    "originalTaskId": "task_789",
    "status": "pending",
    "createdAt": "2023-07-20T13:00:00Z"
  }
}
```

## 数据统计API

### 获取用户统计信息

```http
GET /api/admin/abilities/{abilityId}/logs?limit=12
Authorization: Bearer <token>
```

**响应示例**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "totalTasks": 50,
    "completedTasks": 45,
    "failedTasks": 3,
    "pendingTasks": 2,
    "totalProcessingTime": 7200,
    "storageUsed": 1073741824,
    "actions": {
      "upscale": 20,
      "cutout": 15,
      "denoise": 10,
      "colorize": 5
    },
    "monthlyStats": [
      {
        "month": "2023-06",
        "tasks": 15,
        "processingTime": 1800
      },
      {
        "month": "2023-07",
        "tasks": 35,
        "processingTime": 5400
      }
    ]
  }
}
```

### 获取系统统计信息 (管理员)

```http
GET /api/admin/abilities?status=active
Authorization: Bearer <admin_token>
```

**响应示例**:
```json
{
  "code": 200,
  "message": "获取成功",
  "data": {
    "totalUsers": 1000,
    "activeUsers": 750,
    "totalTasks": 10000,
    "completedTasks": 9500,
    "failedTasks": 300,
    "pendingTasks": 200,
    "totalProcessingTime": 720000,
    "totalStorageUsed": 107374182400,
    "actions": {
      "upscale": 4000,
      "cutout": 3000,
      "denoise": 2000,
      "colorize": 1000
    },
    "monthlyStats": [
      {
        "month": "2023-06",
        "users": 800,
        "tasks": 3000,
        "processingTime": 180000
      },
      {
        "month": "2023-07",
        "users": 900,
        "tasks": 4000,
        "processingTime": 240000
      }
    ]
  }
}
```

## 错误处理

### 错误响应格式

当API请求失败时，服务器会返回详细的错误信息：

```json
{
  "code": 400,
  "message": "请求参数错误",
  "error": {
    "type": "ValidationError",
    "details": [
      {
        "field": "scale",
        "message": "缩放倍数必须是2、4或8"
      }
    ]
  },
  "timestamp": "2023-07-20T12:00:00Z"
}
```

### 常见错误码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| 1001 | 用户名或密码错误 | 检查用户名和密码是否正确 |
| 1002 | Token已过期 | 重新登录获取新Token |
| 1003 | Token无效 | 检查Token格式是否正确 |
| 2001 | 图片格式不支持 | 使用支持的图片格式(JPG, PNG等) |
| 2002 | 图片大小超出限制 | 压缩图片或减小图片尺寸 |
| 2003 | 处理参数错误 | 检查参数是否符合API要求 |
| 3001 | 任务不存在 | 检查任务ID是否正确 |
| 3002 | 任务状态不允许此操作 | 检查任务当前状态 |
| 4001 | 存储空间不足 | 删除不需要的文件或联系管理员 |
| 5001 | 系统内部错误 | 稍后重试或联系技术支持 |

## API使用示例

### JavaScript/TypeScript示例

```typescript
// API客户端示例
class ApiClient {
  private baseUrl: string;
  private token: string | null = null;
  
  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }
  
  // 设置认证Token
  setToken(token: string) {
    this.token = token;
  }
  
  // 通用请求方法
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(this.token && { Authorization: `Bearer ${this.token}` }),
      ...options.headers,
    };
    
    const response = await fetch(url, {
      ...options,
      headers,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || '请求失败');
    }
    
    return response.json();
  }
  
  // 用户登录
  async login(username: string, password: string) {
    const response = await this.request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    
    this.setToken(response.data.token);
    return response.data;
  }
  
}

// 使用示例
// 登录
await apiClient.login('username', 'password');
```

### React Hook示例

```typescript
// hooks/useImageProcessing.ts
import { useState, useCallback } from 'react';
import { apiClient } from '../services/apiClient';

export const useImageProcessing = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const submitTask = useCallback(async (
    abilityId: string,
    payload: AbilityInvokePayload
  ) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await abilityService.invokeAbility(abilityId, payload);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  const getTaskStatus = useCallback(async (taskId: string) => {
    try {
      const { data } = await http.get(`/ability-tasks/${taskId}`);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取任务状态失败');
      throw err;
    }
  }, []);
  
  return {
    submitTask,
    getTaskStatus,
    isLoading,
    error,
  };
};
```

## 更新日志

### v1.2.0 (2023-07-20)

- 新增图像降噪API
- 优化任务状态查询性能
- 修复批量处理时的内存泄漏问题

### v1.1.0 (2023-06-15)

- 新增图像上色API
- 支持批量图像处理
- 添加任务重试功能

### v1.0.0 (2023-05-01)

- 初始版本发布
- 支持图像无损放大
- 支持印花提取
- 用户认证和任务管理

---

这份API文档提供了POD AI Studio所有API接口的详细说明，包括请求参数、响应格式和错误处理。如有任何疑问或建议，请联系开发团队。
## 统一能力 API（Atomic Capabilities）

> 详尽字段、回调/并发策略请参见 [docs/api/abilities.md](./api/abilities.md)。本节给出高层概要，方便与其他业务接口串联。

### 1. 能力清单

- `GET /api/abilities`：列出当前激活的原子能力，字段包含 `provider/abilityType/metadata.pricing/requiresImage/maxOutputImages/health metrics` 等。
- `GET /api/abilities/{abilityId}`：返回单个能力细节，可直接喂给客户端表单（`inputSchema` 即 UI 模型）。

### 2. 同步调用

- `POST /api/abilities/{abilityId}/invoke`
  - 请求：`inputs`（能力参数）、`imageUrl/imageBase64/images[]`、`executorId`（可选覆盖默认节点）、`metadata`、`callbackUrl`（可选 webhook）。
  - 响应：统一 `AbilityInvokeResponse`，含 `images/videos/texts/assets`, `logId`, `durationMs`, `metadata.taskId`, `raw`.
  - 所有请求都会写入 `ability_invocation_logs`（含成本/耗时/traceId/输出 URL），`logId` 可在管理端“调用记录”中检索。
  - 若未在管理端为能力绑定 `executor_id`，接口将返回 `400 ABILITY_EXECUTOR_NOT_CONFIGURED`。

### 3. 异步 / 批量任务

- `POST /api/ability-tasks`：与同步调用体一致，额外包含 `abilityId`，返回 `task_id` 与 `status=queued`。
- `GET /api/ability-tasks/{taskId}`：查询任务状态；`resultPayload` 会在完成后附上 `AbilityInvokeResponse`。
- `GET /api/ability-tasks`：分页查询当前账号的任务历史。
- 同样支持 `callbackUrl`（任务完成后 POST，payload 中附 `taskId/result/error/logId`）。
- 并发控制：后端线程池大小由 `ABILITY_TASK_MAX_WORKERS` 决定（默认 4），单能力/节点再受 `executors.max_concurrency` 限制；ComfyUI 节点为串行 worker，需留意 `/api/admin/comfyui/queue-status`。

### 4. 调用日志 & 成本

- `ability_invocation_logs` 记录每次调用：`ability_id/provider/executor_id/status/duration_ms/billing_unit/list_price/discount_price/cost_amount`.
- `GET /api/admin/abilities/{abilityId}/logs?limit=12`（管理端）会返回日志记录，包含请求/响应摘要、OSS 输出、失败原因。
- 成本策略：每个能力在 `metadata.pricing` 中声明币种、单位、对外价、折扣价；如未设置，默认回退为 ComfyUI ¥0.30/张。日志将记录本次调用的实际成本，便于生成报表。
- 常见错误：若能力缺少执行节点、参数不合法、队列阻塞等，将返回 ABILITY 模块错误码（详见 `docs/standards/error-catalog.md` 与 `docs/standards/error-contract.md`）；前端可根据 `code` 显示更友好的提示，管理端也会在“调用记录”中高亮失败条目。

### 5. ComfyUI 辅助接口（管理端）

- `GET /api/admin/comfyui/models?executorId=...`：代理 ComfyUI `/object_info`，返回可选 `unet/clip/vae/lora` 清单，管理端测试面板自动渲染为下拉框。
- `GET /api/admin/comfyui/loras?executorId=...`：LoRA 目录（DB）+ 节点实装合并，返回 `items` 与 `untrackedFiles`。
- `POST /api/admin/comfyui/loras` / `PUT /api/admin/comfyui/loras/{id}` / `DELETE /api/admin/comfyui/loras/{id}`：维护 LoRA 元信息。
- `GET /api/admin/comfyui/model-catalog`：模型资源清单（UNET/CLIP/VAE/其他）。
- `POST /api/admin/comfyui/model-catalog` / `PUT /api/admin/comfyui/model-catalog/{id}` / `DELETE /api/admin/comfyui/model-catalog/{id}`：维护模型资源条目。
- `GET /api/admin/comfyui/plugin-catalog`：插件资源清单（节点名/包名/版本）。
- `POST /api/admin/comfyui/plugin-catalog` / `PUT /api/admin/comfyui/plugin-catalog/{id}` / `DELETE /api/admin/comfyui/plugin-catalog/{id}`：维护插件资源条目。
- `GET /api/admin/comfyui/queue-status?executorId=...`：代理 `/queue/status`，展示 `running/pending/max`。异常时返回 `COMFYUI_QUEUE_STATUS_ERROR`，通常表示目标节点离线或无响应。
- `GET /api/admin/comfyui/queue-summary?executorIds=...`：跨节点汇总 ComfyUI 队列状态，返回 `totalRunning/totalPending/servers[]`，用于调度监控看板与集中排障。
- `GET /api/admin/comfyui/system-stats?executorId=...`：代理 `/system_stats`，返回 ComfyUI 版本与设备信息。
- `POST /api/admin/comfyui/server-diff` / `GET /api/admin/comfyui/server-diff`：保存/读取服务器对齐快照。
- `GET/POST /api/admin/comfyui/agents` / `PUT/DELETE /api/admin/comfyui/agents/{agent_id}`：管理 Agent 基础信息。
- `POST /api/admin/comfyui/agents/{agent_id}/token`：签发 Agent 心跳/告警 token。
- `GET/POST /api/admin/comfyui/manifests` / `GET/PUT /api/admin/comfyui/manifests/{id}`：管理清单与版本。
- `GET/POST /api/admin/comfyui/tasks` / `GET /api/admin/comfyui/tasks/{task_id}` / `POST /api/admin/comfyui/tasks/{task_id}/push` / `GET /api/admin/comfyui/tasks/{task_id}/events`：任务下发、推送与事件回执。
- `GET /api/admin/comfyui/alerts`：查看 Agent 告警列表。
- `GET /api/agent/docs/agent-protocol`：获取中台侧 Agent 协议 Markdown（用于双方同步）。

> **建议**：客户端只需了解 `/api/abilities` + `/invoke` + `/ability-tasks` + `/auth`。其余 `/api/admin/*` 接口为后台/管理端占用，用于维护执行节点、工作流、API Key 仓库与调用日志。
