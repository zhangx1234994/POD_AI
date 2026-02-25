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

### POST /api/evals/batches

创建 LoRA 批测批次（新两阶段流程：先素材，后提交）。

约束：

- 同一浏览器身份（rater）若已有进行中批次（`uploading/ready/submitting/running`），将返回 `409 BATCH_ACTIVE_EXISTS:<batch_id>`，需先完成或停止当前批次。

### GET /api/evals/batches

查询批次列表（支持 `mine_only/status/workflow_version_id`）。

### GET /api/evals/batches/{batch_id}

查询批次详情（含汇总计数）。

### POST /api/evals/batches/{batch_id}/assets

批量登记素材（前端上传 OSS 成功后调用）。

### GET /api/evals/batches/{batch_id}/assets

分页查询素材列表。

### POST /api/evals/batches/{batch_id}/submit

启动批次提交（后端统一展开素材 × 重复次数并创建 run）。

尺寸策略由后端在提交阶段按每张素材执行：

- `__batch_size_mode=original`：清空尺寸相关入参，按原图语义执行
- `__batch_size_mode=preset_1k`：优先写入 `resolution=1K`；若工作流无 `resolution` 字段，则按原图比例换算最长边 1024
- `__batch_size_mode=custom`：按提交参数写入分辨率/宽高

### GET /api/evals/batches/{batch_id}/items

分页查询执行项（run item）状态。

返回中包含执行快照字段，前端可直接渲染对照列表：

- `asset_source_key / asset_file_name / asset_oss_url`
- `run_status / run_prompt / run_output_urls_json / run_error_message`

### POST /api/evals/batches/{batch_id}/stop

停止批次（后端强约束：停止后不允许新增执行项）。

### GET /api/evals/runs/batches

查询批次汇总（按 `__batch_session_id` 聚合）。

返回字段（关键）：

- `batchId`
- `workflowVersionId/workflowName`
- `total/completed/queued/running/succeeded/failed`
- `expectedTotal/expectedImages/expectedRepeat`（批次声明的期望值；其中 `expectedTotal=uploaded_count * repeat_count`，仅统计可执行素材）
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

说明：评测端前端已接入上传进度显示（文件级 + 字节级），便于排查大批量上传慢/失败场景。

### GET /api/evals/docs/workflows

获取评测工作流文档（结构化 + Markdown）。

文档内容必须与统一准则一致：

- 状态词口径（任务状态 / 日志状态 / Coze taskStatus）
- 错误码与强约束错误格式（`ERR|<CODE>|<message>`）
- 成功但无预览时的展示策略（结果回填中）

**错误（常见）**

- `UNAUTHORIZED` / `INVALID_TOKEN`
- `WORKFLOW_VERSION_NOT_FOUND`
- `RUN_NOT_FOUND`
- `BATCH_NOT_FOUND` / `BATCH_FORBIDDEN`
- `BATCH_ACTIVE_EXISTS`
- `BATCH_STOPPED` / `BATCH_NOT_READY`
- `BATCH_ASSETS_EMPTY` / `BATCH_ASSET_LIMIT_EXCEEDED`
- `BATCH_ASSET_UPLOAD_STATUS_INVALID` / `BATCH_ASSET_URL_REQUIRED`
- `BATCH_ITEM_SUBMIT_FAILED`

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
