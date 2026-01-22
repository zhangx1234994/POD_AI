# AI 能力评测（内部打分）

目标：给内部同学一个极简页面，用 Coze 工作流跑图/跑任务，并对输出结果做 1-5 评分 + 备注，数据落到 MySQL 便于复盘与迭代提示词/Lora。

## 启动条件

- 后端需要可连上 MySQL，并完成迁移：`cd backend && alembic upgrade head`
- 后端需要配置 Coze OpenAPI：
  - `COZE_BASE_URL`：例如 `http://114.55.0.56:8888`
  - `COZE_API_TOKEN`：Coze 的 PAT（Bearer Token）
  - 也可复用 `SERVICE_API_TOKEN` 作为兜底 token（不建议线上长期依赖兜底）

## 后端接口

均在管理端鉴权下使用（Admin Web 会自动带上 Bearer JWT）：

- `GET /api/admin/evals/workflow-versions`
- `POST /api/admin/evals/workflow-versions`
- `GET /api/admin/evals/datasets`
- `POST /api/admin/evals/datasets`
- `POST /api/admin/evals/runs`
- `GET /api/admin/evals/runs`
- `POST /api/admin/evals/runs/{run_id}/annotations`

## 工作流版本录入（Workflow Version）

工作流版本需要先录入数据库（目前前端页面只做选择与打分，不提供录入表单）。

示例：

```bash
curl -X POST "$API_BASE/api/admin/evals/workflow-versions" \
  -H "Authorization: Bearer $PODI_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "image-extend",
    "name": "图延伸 · v1",
    "version": "v1",
    "workflow_id": "7597530887256801280",
    "status": "active",
    "parameters_schema": {
      "fields": [
        { "name": "url", "label": "图片 URL", "type": "text", "required": true },
        { "name": "width", "label": "宽度", "type": "text", "required": false, "defaultValue": "1200" },
        { "name": "height", "label": "高度", "type": "text", "required": false, "defaultValue": "1200" }
      ]
    }
  }'
```

约定：图片输入字段优先用 `url`（字符串）。

## 运行与回调

- 页面点击“试运行”会创建一条 `eval_run` 记录，并后台执行 Coze `/v1/workflow/run`。
- 如果工作流输出是 PODI 的 task_id（例如 ComfyUI 回调 ID），后端会自动轮询 `ability_tasks` 直到完成，并把图片 URL 写入 `result_image_urls_json`。
- 评分与备注写入 `eval_annotation`。

