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

