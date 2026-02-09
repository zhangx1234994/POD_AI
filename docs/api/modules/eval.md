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
