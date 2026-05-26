# 评测平台接口

## 用途

- 评测平台（podi-eval-web）用于内部回归验证与打分。
- 支持公开评测（无登录）与管理端评测（需管理员）。

## 鉴权

- **公开评测**：`EVAL_PUBLIC_TOKEN`（`X-Eval-Token` 或 `?token=`）
- **评测管理**：`EVAL_ADMIN_TOKEN`（`X-Eval-Admin-Token` 或 `?admin_token=`），服务器必须显式配置该环境变量，代码不提供默认口令。
- **管理端评测**：管理员 Bearer Token（`/api/admin/evals/*`）

---

## 0) 管理端健康接口

### GET /api/admin/evals/operations-health
### GET /api/evals/admin/operations-health

用途：发现 `/health` 看不到的评测链路问题，例如长期运行、提交后没有执行 ID、成功但没有结果、近期失败。

入口差异：

- `/api/admin/evals/operations-health`：管理后台使用，走管理员 Bearer Token。
- `/api/evals/admin/operations-health`：评测端首页使用，走 `EVAL_ADMIN_TOKEN`。

常用查询参数：

- `staleMinutes`：运行超过多少分钟视为长期未收口，默认 `30`
- `submitGraceMinutes`：运行中但没有 Coze 执行 ID/中台任务 ID 的宽限时间，默认 `5`
- `recentHours`：近期失败与成功无结果的统计窗口，默认 `24`
- `limit`：每类问题最多返回条数，默认 `20`

响应核心字段：

- `status`：`healthy / warning / critical`
- `issues[]`：问题列表，包含中文标题、说明、数量
- `staleRunning[]`：长期未收口任务
- `submitStalled[]`：提交阶段卡住任务
- `succeededWithoutOutput[]`：成功但没有图片或结构化结果的记录
- `recentFailures[]`：近期失败记录
- `recentRunTotal`：最近窗口内评测运行总数
- `recentSuccessCount`：最近窗口内成功数量
- `recentFailureCount`：最近窗口内有效失败数量
- `concurrency`：当前后端评测并发与 ComfyUI 队列容量快照，例如 `evalComfyuiRunMaxWorkers`、`evalFanoutMaxWorkers`、`comfyuiQueueCapacity`、`comfyuiQueueTotal`
- `errorCounts`：近期失败错误码分布

配套命令行：

```bash
python3 backend/scripts/check_eval_operations_health.py
```

发版门禁：出现 `critical` 时禁止继续发版或验收，必须先收口。

补充规则：

- `COMFYUI_EXECUTOR_UNREACHABLE`：存在 active ComfyUI 节点队列不可读，发版前必须恢复服务或明确下线该节点。
- `COMFYUI_NO_AVAILABLE_EXECUTOR`：所有 active ComfyUI 节点不可用，视为阻断级事故。
- `COMFYUI_QUEUE_HEALTH_UNAVAILABLE`：队列健康检查整体失败，不能只看 `/health` 放行。
- `EVAL_NO_RECENT_RUNS`：最近窗口内没有任何评测运行，说明巡检可能没有跑，不能只看服务存活。
- `EVAL_SUCCEEDED_WITHOUT_OUTPUT`：运行状态显示成功，但没有图片或结构化结果，视为回填事故。
- `EVAL_NO_RECENT_SUCCESS`：最近窗口内有有效失败但没有成功记录，视为主链路不可用。

### GET /api/evals/admin/comfyui-queue-summary

用途：评测端首页展示 ComfyUI 执行节点队列，辅助判断 GPU 是否吃满、是否存在排队断档。

鉴权：`EVAL_ADMIN_TOKEN`（`X-Eval-Admin-Token` 或 `?admin_token=`）

响应核心字段：

- `totalRunning`：所有 ComfyUI 节点当前运行数
- `totalPending`：所有 ComfyUI 节点当前排队数
- `totalCount`：`running + pending`
- `servers[]`：单节点明细，包含 `executorId/baseUrl/runningCount/pendingCount/queueMaxSize`

---

## 1) 公共评测接口（无需登录）

### GET /api/evals/workflow-versions

返回可评测的工作流列表（`status=active`）。

新增字段（用于中台资源单一真源联动）：

- `resourceBindings[]`
  - `field`：参数字段名
  - `resourceType`：`lora/model/plugin`
  - `source`：资源目录接口（如 `/api/admin/comfyui/resources/options?...`）
- `routingGovernance`
  - `executionLabel`：当前能力实际执行面，例如 ComfyUI、第三方 API、image-ops
  - `currentTrackingLabel`：当前追踪方式，帮助判断是否已经沉淀中台任务 ID
  - `governanceLabel`：链路治理结论，例如“追踪基本达标”“需要统一任务化”
  - 注意：`governance` 仍表示目录角色（生产主入口、灰度版本等），`routingGovernance` 只表示执行面与追踪治理。

重点工作流参数补充：

- `7602916576198656000`（多模型生图 · shengtu_shangye）
  - `moxing`：`1=Banana Pro`、`2=Flux2 Pro`、`3=Seedream 4.5`、`4=Banana 2`
  - `cankaotu`：参考图 URLs（每行/逗号分隔），仅 `1/2/4` 生效
  - `aspect_ratio`（按模型枚举）：
    - `原图比例（默认）` 仅是前端展示文案；实际调用应传空字符串或直接不传，不能把中文文案本身传给模型。
    - Banana Pro（`moxing=1`）：`auto, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9`
    - Flux2 Pro（`moxing=2`）：`auto, 1:1, 4:3, 3:4, 16:9, 9:16, 3:2, 2:3`
    - Seedream 4.5（`moxing=3`）：忽略该参数（仅保留空值）
    - Banana 2（`moxing=4`）：`auto, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9`
  - `resolution`（按模型枚举）：
    - `跟随原图（默认）` 仅是前端展示文案；实际调用应传空字符串或直接不传，不能把中文文案本身传给模型。
    - Banana Pro（`moxing=1`）：`1K, 2K, 4K`
    - Flux2 Pro（`moxing=2`）：`1K, 2K`
    - Seedream 4.5（`moxing=3`）：忽略该参数（仅保留空值）
    - Banana 2（`moxing=4`）：`1K, 2K, 4K`
  - `output` 仍为统一回调 task id（使用 `/api/coze/podi/tasks/get` 查询结果）

- `7615600173695107072`（多图融合 · duotu_ronghe）
  - 主图：`url`（图1）
  - 辅图：`image_url_2`、`image_url_3`（可选，分别映射图2/图3）
  - 可选：`width`、`height`、`negative_prompt`、`prompt`、`seed`
  - 评测页留空时会自动补主图尺寸；绕过前端直调时沿用 workflow 默认 `1024x1024`
  - 无 `lora` 入参
  - 出参：`output`（回调 task id）、`prompt`（提示词反馈字符串）

- `7612002440056930304`（LoRA 查询 · lora_catalog_query）
  - 无入参
  - 出参：
    - `items`：LoRA 详情
    - `lora_names`：可直接作为 LoRA 入参
  - 评测页点击任务后直接展示结构化 JSON（不走图片回填）

- 新增 ComfyUI 工作流（2026-04-16）
  - `7629023903431524352`（背景抠图 · beijing_koutu）
    - 分类：`通用类`
    - 入参：`url`
    - 出参：`output`、`ip`
  - `7629023041988591616`（头部抠像 · toubu_kouxiang）
    - 分类：`通用类`
    - 入参：`url`
    - 出参：`output`、`ip`
  - `7629024620879806464`（文字增强 · qwen2512_print_shape_text_enhance）
    - 分类：`图裂变`
    - 入参：`url`、`prompt`、`bili`、`count`
    - 说明：
      - `bili`：重绘幅度百分比，默认 `50%`，数值越大变化越大
      - `count`：fan-out 子任务数，默认 `4`
    - 出参：`output`、`prompt`、`ip`
  - `7629026792103215104`（四方连续裂变 · flux2_9b_liebian_sifang）
    - 分类：同时展示在 `图裂变` 与 `四方/两方连续图类`
    - 入参：`url`、`prompt`、`count`
    - 出参：`output`、`prompt`、`ip`
  - 验证结论：
    - 评测 API 可正常创建 run，OSS 图片 URL 能正确进入执行链路。
    - 当前主要待优化点在上游 prompt 生成质量，而非评测执行接口本身。

### GET /api/evals/business/quality-samples

测评端读取固定质量样例库。写入、停用、归档仍只允许管理端通过 `/api/admin/business/quality-samples` 操作；该接口只给内部测评页提供“用同一张图复跑”的样例入口。

**请求**

```http
GET /api/evals/business/quality-samples?business_key=fission&status=active&limit=50
```

查询参数：

- `business_key`：可选，按业务过滤，例如 `fission`、`image_edit`、`outpaint`、`pattern_extract`、`text_fission`。
- `status`：默认 `active`；测评端只允许 `active` / `inactive`，不暴露 `archived`。
- `limit`：默认 200，范围 1-500。

**响应**

```json
{
  "total": 1,
  "items": [
    {
      "id": "bizsample_xxx",
      "businessKey": "fission",
      "sampleKey": "dense-pattern-a",
      "label": "满版图案 A",
      "description": "结构稳定性回归样例",
      "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/quality/fission/a.png",
      "prompt": "保持主体结构",
      "generatedImageUrl": null,
      "inputTags": ["满版图案"],
      "defaultParams": {"quality": "preview"},
      "status": "active",
      "sortOrder": 1,
      "createdByUserId": null,
      "createdByUsername": "admin",
      "createdAt": "2026-05-26T10:00:00",
      "updatedAt": "2026-05-26T10:00:00"
    }
  ]
}
```

**错误**

- `NOT_FOUND`：`EVAL_PUBLIC_ENABLED=false` 时隐藏公共测评接口。
- `UNAUTHORIZED`：配置了 `EVAL_PUBLIC_TOKEN` 但未传或传错。
- `BUSINESS_QUALITY_SAMPLE_STATUS_INVALID`：`status` 不是 `active` / `inactive`，或试图读取 `archived`。

### GET /api/evals/metrics/workflows

返回每个评测工作流的评分汇总和近期运行概况，测评端首页卡片用它判断“最近可用 / 最近失败 / 生成未回填 / 暂无运行”。

常用查询参数：

- `recent_hours`：近期运行统计窗口，默认 `72`，范围 `1~720` 小时。

响应核心字段：

- `metrics.{workflowVersionId}.ratingCount`：评分票数。
- `metrics.{workflowVersionId}.avgRating`：平均评分，无评分时为 `null`。
- `metrics.{workflowVersionId}.runCount`：该工作流累计评测运行数。
- `metrics.{workflowVersionId}.recentRunCount`：近期评测运行数。
- `metrics.{workflowVersionId}.recentSuccessCount`：近期成功并有结果的运行数。
- `metrics.{workflowVersionId}.recentFailureCount`：近期失败运行数。
- `metrics.{workflowVersionId}.recentRunningCount`：近期仍未收口的运行数。
- `metrics.{workflowVersionId}.recentNoOutputCount`：近期状态成功但无图片、视频、文字或结构化结果的运行数。
- `metrics.{workflowVersionId}.recentOutputKindCounts`：近期结果类型分布，固定包含 `image/video/text/structured/none`，用于测评端区分生图、生视频、VL/文字和结构化能力。
- `metrics.{workflowVersionId}.lastRunStatus`：最近一次运行的统一终态，常见为 `success / running / failed`。
- `metrics.{workflowVersionId}.lastRunOutputKind`：最近一次运行的结果类型，取值同上。
- `metrics.{workflowVersionId}.lastErrorCode`：最近一次失败的错误码，不返回敏感内部信息。

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

统一状态字段（新增）：

- `submit_status`：`pending/submitting/submit_failed/submitted`
- `callback_status`：`waiting/running/success/failed/not_configured`
- `final_status`：`pending/running/success/failed/canceled`
- `error_code`：标准错误码（可为空）

只读成本字段：

- `cost_amount` / `currency`：如果该评测 run 关联了中台能力任务，并且能力调用日志已记录成本，则返回本次估算成本。
- `billing_unit` / `unit_price`：返回成本计价单位和单位成本，用于评测端任务追踪页展示，方便判断批量评测大概消耗。
- 成本字段仅用于内部评测复核，不代表对业务方正式收费；字段缺失时前端显示“成本未记录”。

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
- `run_output_reviews_json`（逐张结果图标注，含 `output_index/verdict/reason/note/updated_at`）

### GET /api/evals/batches/{batch_id}/review-groups

结果标注页专用分页接口（固定每页 20 组，组=原图素材）。

请求参数：

- `page`：页码（从 1 开始）
- `page_size`：固定 20（后端会归一为 20）

返回字段（核心）：

- `batch_id / page / page_size / total_groups / total_pages`
- `review_progress.current_page / completed_page`
- `items[]`（每组包含）
  - `asset_id/source_key/file_name/input_url`
  - `group_status`：`has_output/no_output/failed`
  - `run_total/completed/failed/waiting`
  - `outputs[]`：结果图列表（含 `run_item_id/run_id/output_index/url/review`）
  - `last_error`

约束：

- 批次未结束（非 `succeeded/failed/stopped`）返回 `409 BATCH_REVIEW_NOT_READY`
- `page > total_pages` 返回 `400 BATCH_REVIEW_PAGE_INVALID`

### POST /api/evals/batches/{batch_id}/review-progress

保存“断点续标”进度（页码），落库到 `eval_batch_session.metadata.review_state`。

请求体示例：

```json
{
  "current_page": 6,
  "completed_page": 5,
  "page_size": 20
}
```

规则：

- `completed_page <= current_page`
- `page_size` 固定 20（传其他值也会按 20 存）

返回字段：

- `batch_id`
- `review_progress`（`page_size/current_page/completed_page/updated_at`）

### POST /api/evals/batches/{batch_id}/reviews

批量写入“结果图逐张标注”（仅不满意 + 原因/备注，默认满意），用于页面刷新后回显。

请求体示例：

```json
{
  "items": [
    {
      "run_item_id": "b4f7d0a5d0d4460ea36a4c66dcd9f6a0",
      "output_index": 1,
      "verdict": "unsatisfied",
      "reason": "细节结构错误",
      "note": "耳朵轮廓偏差明显"
    }
  ]
}
```

约束：

- `run_item_id` 必须属于当前批次
- `output_index` 从 1 开始
- `verdict` 仅允许 `pending/satisfied/unsatisfied`
- 当 `verdict=pending` 且 `reason/note` 为空时，后端会删除该条标注

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

响应同列表项，包含统一状态字段和只读成本字段。

### POST /api/evals/runs/{run_id}/annotations

提交评分/备注。

### POST /api/evals/uploads

上传评测图片（返回 OSS URL，兼容旧链路）。

说明：

- 当前评测端默认链路为：`/api/media/v1/upload-key` + `/api/media/v1/sts` 获取凭证，浏览器直传 OSS（不再经过中台文件中转）。
- `/api/evals/uploads` 保留为兼容接口。
- 评测端前端已接入上传进度显示（文件级 + 字节级），便于排查大批量上传慢/失败场景。
- 批测明细中的上传失败提示会分段透出：`上传准备失败（身份）` / `上传凭证失败（upload-key|sts）` / `直传OSS失败` / `任务登记失败`。

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
- `BATCH_REVIEWS_EMPTY` / `BATCH_REVIEWS_LIMIT_EXCEEDED`
- `BATCH_REVIEW_RUN_ITEM_REQUIRED` / `BATCH_REVIEW_RUN_ITEM_INVALID`
- `BATCH_REVIEW_VERDICT_INVALID`
- `BATCH_REVIEW_NOT_READY` / `BATCH_REVIEW_PAGE_INVALID`

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
