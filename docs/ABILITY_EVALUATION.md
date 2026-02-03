# AI 能力评测（内部回归平台）

> 版本：2026-02-03  
> 定位：**评测链路与生产链路解耦**。评测平台只负责“验证与回归”，不直接替代生产能力。

目标：给内部同学一个极简页面，用 Coze 工作流跑图/跑任务，并对输出结果做 1-5 评分 + 备注，数据落到 MySQL 便于复盘与迭代提示词/LoRA。

## 启动条件（必备）

- 后端需要可连上 MySQL，并完成迁移：`cd backend && alembic upgrade head`
- 后端需要配置 Coze OpenAPI（评测调用 Coze 的前提）：
  - `COZE_BASE_URL`：例如 `http://114.55.0.56:8888`
  - `COZE_API_TOKEN`：Coze 的 PAT（Bearer Token）
  - 也可复用 `SERVICE_API_TOKEN` 作为兜底 token（不建议线上长期依赖兜底）
- 若评测人员“无需登录”使用独立页面（公开评测接口）：
  - `EVAL_PUBLIC_ENABLED=true`
  - （可选）`EVAL_PUBLIC_TOKEN=...`：前端请求需带 `X-Eval-Token` 或 `?token=...`
  - （可选）`EVAL_ADMIN_TOKEN=...`：用于 `/api/evals/admin/*` 管理接口（编辑 workflow 备注/状态）
  - （可选）`COZE_COMFYUI_CALLBACK_WORKFLOW_ID=...`：当工作流输出的是原始 ComfyUI taskid 时用于兜底解析图片

## 边界与契约（请先确认）

- **图片参数统一用 `url`**（字符串）。
- **像素参数必须是纯数字**（禁止 `px`）。
- **回调类输出为 `taskId`**，必须能通过 `/api/coze/podi/tasks/get` 查询。
- 评测只记录结果，不参与生产任务调度。

## 后端接口

### A. 管理端鉴权（JWT）

> 适用于 Admin Web（已登录）调用。

均在管理端鉴权下使用（Admin Web 会自动带上 Bearer JWT）：

- `GET /api/admin/evals/workflow-versions`
- `POST /api/admin/evals/workflow-versions`
- `GET /api/admin/evals/datasets`
- `POST /api/admin/evals/datasets`
- `POST /api/admin/evals/runs`
- `GET /api/admin/evals/runs`
- `GET /api/admin/evals/runs/{run_id}`
- `POST /api/admin/evals/runs/{run_id}/annotations`
- `DELETE /api/admin/evals/runs?confirm=true&workflow_version_id=...`（清空评测历史，可选按 workflow 过滤）

### B. 评测公开接口（无需登录）

> 适用于内部评测页面（`EVAL_PUBLIC_ENABLED=true`）。

- `GET /api/evals/workflow-versions`
- `POST /api/evals/runs`
- `GET /api/evals/runs`
- `GET /api/evals/runs/{run_id}`
- `POST /api/evals/runs/{run_id}/annotations`
- `POST /api/evals/uploads`（评测页上传图片，返回 OSS URL）
- `GET /api/evals/docs/workflows`（自动生成的“评测工作流文档”）

### C. 评测管理接口（无登录，仅 token）

> 用 `EVAL_ADMIN_TOKEN` 鉴权（`X-Eval-Admin-Token` 或 `?admin_token=`）。

- `GET /api/evals/admin/workflow-versions`
- `PUT /api/evals/admin/workflow-versions/{workflow_version_id}`

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

## 运行与回调（评测侧）

- 页面点击“试运行”会创建一条 `eval_run` 记录，并后台执行 Coze `/v1/workflow/run`。
- 如果工作流输出是 PODI 的 task_id（例如 ComfyUI 回调 ID），后端会自动轮询 `ability_tasks` 直到完成，并把图片 URL 写入 `result_image_urls_json`。
- 对于 ComfyUI “submit-only” 类任务（先提交，任务保持 `running`），评测服务会在轮询阶段主动拉取对应 ComfyUI `/history/{promptId}`
  并 finalize 任务（写回 OSS 结果），避免出现“ComfyUI 已生成但页面不刷新”。
- 评分与备注写入 `eval_annotation`。

## 常见问题 & 排查

- **401 / INTERNAL_ONLY**：Coze 调用 PODI 工具箱不在内网，需配置 `COZE_TRUSTED_IPS` 或使用 `SERVICE_API_TOKEN`。
- **Missing required parameters**：workflow 必填项未传（常见 `url/width/height/prompt`）。
- **回调 taskId 查不到**：检查 task 是否入库、以及 Coze/后端是否同一环境（DB/URL）。
- **图片无预览**：检查 OSS URL 是否可访问，或回调是否落盘成功。

## 对接前校验清单（必做）

这份清单用于“业务系统对接前”的参数与回调验收，避免出现 **px/枚举/回调类型不一致** 的隐患。

1) **输出类型确认**
   - 明确该工作流 `output` 是 **图片 URL** 还是 **回调 task id**。
   - 若是回调 task id：评测平台应能自动轮询出图；业务侧也必须接入回调解析链路。

2) **必填参数验证**
   - 在评测平台用“最小参数”跑通一次（只填 required 字段）。
   - 记录真实接受的参数名（尤其是 `url/Url/URL`、`prompt`、`width/height`）。

3) **像素参数格式**
   - 所有像素类字段（`width/height/expand_* / bianchang`）**必须传纯数字，不带 px**。
   - 评测平台与后端已做自动去 `px` 兜底，但业务系统也应做同样处理。

4) **枚举值一致性**
   - 所有 `select` 参数必须传 **枚举值**，不要传 label。
   - 如 `resolution` 只能是 `1K/2K/4K`，`aspect_ratio` 只能是 `1:1/4:3/...`。

5) **回调链路验证**
   - 回调类工作流至少验证 1 次：输出 task id → 回调/轮询 → 图片可访问（OSS URL）。

6) **错误可读性**
   - 故意传错一个参数，确认错误能读懂（例如 “Missing required parameters”）。

> 经验教训：先在评测平台 **跑通 + 固化参数合同**，再接入业务系统。

## 上线前回归清单

见：`docs/release-preflight.md`
