# PODI 评测平台 · Coze 工作流调用文档

线上/开发人员通过 Coze OpenAPI 直接调用工作流时，建议以评测平台的“文档”页面为准：

- 评测平台内置入口：`/api/evals/docs/workflows`
  - 内容为后端自动生成（读取数据库中 `status=active` 的工作流版本 + schema）
  - 方便与后台实时一致，避免手工文档过期

本文件仅作为仓库内的简要说明与入口索引。

## 调用方式（Coze OpenAPI）

环境变量：
- `COZE_BASE_URL`：例如 `https://api.coze.cn`（以实际为准）
- `COZE_API_TOKEN`：Coze 平台生成的 token

示例：

```bash
curl -X POST "$COZE_BASE_URL/v1/workflow/run" \
  -H "Authorization: Bearer $COZE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"<WORKFLOW_ID>","parameters":{}}'
```

## 输出约定

- Coze 返回结构中的 `data` 可能是 JSON 字符串或对象
- 我们的工作流约定：核心输出字段名为 `output`
  - `output=image_url`：直接是一张图片 URL
  - `output=callback_task_id`：回调任务 id（需要再走回调/轮询才能拿到图片）
  - 注意：历史工作流曾把 `dpi` 写成 `pdi`，现已统一为 `dpi`

### ComfyUI 回调型注意事项

- 对于 ComfyUI（以及部分长耗时能力），常见模式是先返回 `output=taskId`，再通过轮询接口拿到最终图片。
- 多台 ComfyUI 服务器场景下，轮询端需要按 `executorId -> executor.baseUrl` 定位到正确的 ComfyUI `/history/{promptId}`。
  评测平台与插件的 `/api/coze/podi/tasks/get` 均已按此策略兼容多节点。

## 裂变类工作流（Fan-out）

评测平台内部支持“裂变数量”控制（`count`）：
- `count` **不是** Coze workflow 的入参，也不会转发给 Coze
- 仅用于评测端批量触发/聚合结果，业务接入文档会自动隐藏该字段
- 外部调用 Coze OpenAPI 时 **不要** 传 `count`

## 示例：DPI 增分（图片输出）

- workflow_id：`7598589746561941504`
- parameters：`url`（图片地址）、`dpi`（建议 300）
- output：图片 URL
