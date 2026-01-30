# AI 能力评测（内部打分）

目标：给内部同学一个极简页面，用 Coze 工作流跑图/跑任务，并对输出结果做 1-5 评分 + 备注，数据落到 MySQL 便于复盘与迭代提示词/Lora。

## 启动条件

- 后端需要可连上 MySQL，并完成迁移：`cd backend && alembic upgrade head`
- 后端需要配置 Coze OpenAPI：
  - `COZE_BASE_URL`：例如 `http://114.55.0.56:8888`
  - `COZE_API_TOKEN`：Coze 的 PAT（Bearer Token）
  - 也可复用 `SERVICE_API_TOKEN` 作为兜底 token（不建议线上长期依赖兜底）
- 若评测人员“无需登录”使用独立页面：
  - `EVAL_PUBLIC_ENABLED=true`
  - （可选）`EVAL_PUBLIC_TOKEN=...`：前端请求需带 `X-Eval-Token` 或 `?token=...`
  - （可选）`COZE_COMFYUI_CALLBACK_WORKFLOW_ID=...`：当工作流输出的是原始 ComfyUI taskid（不在 PODI ability_tasks）时用于兜底解析图片

## 后端接口

均在管理端鉴权下使用（Admin Web 会自动带上 Bearer JWT）：

- `GET /api/admin/evals/workflow-versions`
- `POST /api/admin/evals/workflow-versions`
- `GET /api/admin/evals/datasets`
- `POST /api/admin/evals/datasets`
- `POST /api/admin/evals/runs`
- `GET /api/admin/evals/runs`
- `POST /api/admin/evals/runs/{run_id}/annotations`
- `DELETE /api/admin/evals/runs?confirm=true&workflow_version_id=...`（清空评测历史，默认可选按 workflow 过滤）

另提供“无需登录”的评测 API（给独立评测页面用）：

- `GET /api/evals/workflow-versions`
- `POST /api/evals/runs`
- `GET /api/evals/runs`
- `GET /api/evals/runs/{run_id}`
- `POST /api/evals/runs/{run_id}/annotations`

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
- 对于 ComfyUI “submit-only” 类任务（先提交，任务保持 `running`），评测服务会在轮询阶段主动拉取对应 ComfyUI `/history/{promptId}`
  并 finalize 任务（写回 OSS 结果），避免出现“ComfyUI 已生成但页面不刷新”。
- 评分与备注写入 `eval_annotation`。

## 上线前回归清单

见：`docs/release-preflight.md`
