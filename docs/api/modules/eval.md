# 评测平台接口

## 用途

- 评测平台（podi-eval-web）用于内部回归验证与打分。
- 支持公开评测（无登录）与管理端评测（需管理员）。

## 鉴权

- **公开评测**：`EVAL_PUBLIC_TOKEN`（`X-Eval-Token` 或 `?token=`）
- **评测管理**：`EVAL_ADMIN_TOKEN`（`X-Eval-Admin-Token` 或 `?admin_token=`）
- **管理端评测**：管理员 Bearer Token（`/api/admin/evals/*`）

---

## 1) 公共评测接口（无需登录）

### GET /api/evals/workflow-versions

返回可评测的工作流列表（`status=active`）。

### POST /api/evals/runs

创建评测 run。

**请求体**

```json
{
  "workflowVersionId": "wf_001",
  "inputs": {
    "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/test/input.png",
    "prompt": "印花提取"
  }
}
```

### GET /api/evals/runs

查询评测 run 列表。

常用查询参数：

- `workflow_version_id`：按工作流版本过滤
- `status`：按状态过滤（`queued/running/succeeded/failed`）
- `batch_mode=true`：仅查询批测任务（`__eval_batch_mode=1`）
- `batch_session_id`：按批次 ID 过滤（`__batch_session_id`）
- `mine_only=true`：仅查询当前浏览器 rater 的任务

### GET /api/evals/runs/batches

查询批次汇总（按 `__batch_session_id` 聚合）。

返回字段（关键）：

- `batchId`
- `workflowVersionId/workflowName`
- `total/completed/queued/running/succeeded/failed`
- `latestCreatedAt/latestUpdatedAt`

### POST /api/evals/runs/batches/{batch_id}/stop

停止一个批次中尚未完成的任务（`queued/running -> failed`），并同步停止关联能力任务。

返回字段（关键）：

- `batchId`
- `stoppedRuns`：本次停止的评测任务数
- `stoppedTasks`：本次停止的能力任务数

### GET /api/evals/runs/{run_id}

查询单个 run。

### POST /api/evals/runs/{run_id}/annotations

提交评分/备注。

### POST /api/evals/uploads

上传评测图片（返回 OSS URL）。

### GET /api/evals/docs/workflows

获取评测工作流文档（结构化 + Markdown）。

**错误（常见）**

- `UNAUTHORIZED` / `INVALID_TOKEN`
- `WORKFLOW_VERSION_NOT_FOUND`
- `RUN_NOT_FOUND`

---

## 2) 评测管理接口（无登录，仅 token）

### GET /api/evals/admin/workflow-versions
### PUT /api/evals/admin/workflow-versions/{workflow_version_id}

**用途**：编辑名称、备注、状态、分类等。

---

## 3) 管理端评测接口（管理员 Bearer）

### GET /api/admin/evals/workflow-versions
### POST /api/admin/evals/workflow-versions
### GET /api/admin/evals/datasets
### POST /api/admin/evals/datasets
### POST /api/admin/evals/runs
### GET /api/admin/evals/runs
### GET /api/admin/evals/runs/{run_id}
### POST /api/admin/evals/runs/{run_id}/annotations
### DELETE /api/admin/evals/runs?confirm=true&workflow_version_id=...

**说明**

- 评测端参数契约详见 `docs/ABILITY_EVALUATION.md`。
- 图片输入统一字段 `url`，像素参数必须为纯数字。
