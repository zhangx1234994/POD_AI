# Coze 工具箱契约（PODI 插件）

> 版本：2026-02-03  
> 目标：明确 **Coze 调用 PODI 工具箱** 的统一输入/输出与回调契约，避免参数不一致。

## 1. OpenAPI 导入入口

- `GET /api/coze/podi/openapi.json`
- Coze 仅展示 OpenAPI 声明过的字段，未声明的字段不会出现在节点输出。

## 2. 工具路径约定

单个能力一个 Tool：

```
POST /api/coze/podi/tools/{provider}/{capability_key}
```

额外工具：

- `POST /api/coze/podi/tasks/get`：查询异步任务结果  
- `POST /api/coze/podi/comfyui/queue-summary`：查询 ComfyUI 队列汇总

## 3. 输入契约（统一）

- **图片输入统一 `url`**（字符串）
- 数值参数必须为纯数字（禁止 `px`）
- 枚举参数必须传 value（不要传 label）

说明：
- Coze 工具箱在 OpenAPI 中展示 `url`，后端会自动映射为能力的 `imageUrl/image_urls` 等字段。
- 多图能力（KIE）可填写多行 URL，后端会拆成数组。
- 后端对 `url/imageUrl/image_urls/input_urls` 做兼容解析（以第一个有效 URL 为主图）。

约束建议：
- 业务侧 **只使用 `url`**，其他字段为历史兼容，不作为对外契约。

## 4. 输出契约（统一）

所有工具返回统一结构（Coze 节点可用字段）：

- `text` / `texts`
- `imageUrl` / `imageUrls`
- `videoUrl` / `videoUrls`
- `taskId` / `taskStatus`（异步能力）
- `executorId` / `executorName` / `executorBaseUrl`
- `debugRequest` / `debugResponse`

> 注意：Coze 只展示 OpenAPI schema 声明的字段，若需要输出新字段必须更新插件。

输出字段说明（与后端一致）：
- `imageUrl`：首张图片（优先 OSS）
- `imageUrls`：全部图片列表
- `taskId`：异步任务 ID（回调或轮询使用）
- `taskStatus`：任务状态（queued/running/succeeded/failed）
- `executorBaseUrl`：最终执行节点地址（便于排查）

## 5. 异步流程（ComfyUI / 商业模型）

1) 调用能力工具 → 返回 `taskId`  
2) 调用 `POST /api/coze/podi/tasks/get` 轮询结果  

`taskId` 推荐格式：`t1.<provider>.<executorId>.<raw>`

回调/轮询时序（建议）：
1. Tool 提交 → 立即返回 `taskId`
2. 业务侧等待 2~5 秒后开始轮询
3. `/tasks/get` 返回 `taskStatus`：
   - `queued/running`：继续轮询
   - `succeeded`：读取 `imageUrl/imageUrls`
   - `failed`：读取 `debugResponse` 与错误码

## 6. 队列与错误

队列满时，工具返回：

```
taskId = ERR|Q1001|COMFYUI_QUEUE_FULL(...)
taskStatus = failed
```

错误码详见：`docs/standards/queue-and-error-standards.md`

错误分层（业务理解）：
- **客户端输入错误**：参数缺失/格式错误（直接报错）
- **队列错误**：Q1001/Q2001，任务未提交
- **执行错误**：第三方/执行节点异常（可重试）

## 7. 内部鉴权

默认仅允许内网调用（否则 `401 INTERNAL_ONLY`）：

- 配置 `COZE_TRUSTED_IPS`
- 或请求头 `Authorization: Bearer <SERVICE_API_TOKEN>`

## 8. 常见问题

- **schema 未更新**：删除 Coze 节点重新拖入
- **Missing required parameters**：检查 `url/width/height` 必填字段
- **TASK_NOT_FOUND**：确认 taskId 对应同一后端/数据库

## 9. 工具链路说明（按 provider）

### 9.1 ComfyUI
- 工具调用会立刻返回 `taskId`（异步）
- 由 `/api/coze/podi/tasks/get` 轮询结果
- 队列满时直接返回错误码（Q1001）

### 9.2 KIE / Volcengine（商业模型）
- 部分模型走异步并返回 `taskId`
- 队列满时返回错误码（Q2001）

### 9.3 Baidu
- 多为同步返回图片
- 若请求失败会返回 `debugResponse` 供排查
