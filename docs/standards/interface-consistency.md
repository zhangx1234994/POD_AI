# 接口一致性统一准则（必须遵守）

> 目标：避免“前后端状态词不一致、错误处理风格不一致、文档口径不一致”。
> 适用范围：`/api/*`（管理端、评测端、Coze 工具、Agent 协议）与所有对外文档。
> 业务分类和接口形态归属必须同时遵循：`docs/standards/business-interface-taxonomy.md`。
> 业务任务、子任务和页面动线必须同时遵循：`docs/standards/business-mainline-contract.md`。

---

## 1. 状态词统一（按领域）

### 1.0 双阶段状态契约（统一新增）

所有“异步任务查询接口”推荐同时返回以下字段（兼容增量，不替换原 `status`）：

- `submit_status`：`pending/submitting/submit_failed/submitted`
- `callback_status`：`waiting/running/success/failed/not_configured`
- `final_status`：`pending/running/success/failed/canceled`
- `error_code`：标准错误码（可为空）

目的：

- `status` 保持领域兼容（历史字段不破坏）
- 新字段解决“提交成功 ≠ 回调成功”的歧义
- 前端展示统一依据 `final_status`，排障细分看 `submit_status/callback_status`

### 1.1 能力异步任务（`/api/ability-tasks`）

- 允许状态：`queued` / `running` / `succeeded` / `failed` / `cancelled`
- 约束：
  - 不得返回 `success/completed/done` 作为任务状态
  - 失败必须同时提供 `errorMessage`（可空但推荐）
  - **上游失败不可标成功**：若原始响应明确失败（如 KIE `state=fail` / `status=failed`），必须落库为 `failed`。

### 1.2 能力调用日志（`/api/admin/abilities/logs*`）

- 允许状态：`pending` / `success` / `failed`
- 说明：日志是“调用记录”维度，不等价于任务状态；继续使用 `success/failed`。
- 前端展示层必须做统一映射：
  - `success/succeeded/completed` → 成功
  - `failed/error/timeout/rejected` → 失败
  - `running/processing` → 执行中
  - `queued/pending/created` → 排队中
  - `cancelled/canceled/stopped/aborted` → 已取消

### 1.3 Coze 任务查询（`/api/coze/podi/tasks/get`）

- `taskStatus` 对外统一为：`queued` / `running` / `succeeded` / `failed`
- 队列强约束错误（如并发满）：
  - `taskId = ERR|Qxxxx|...`
  - `taskStatus = failed`

### 1.3.1 业务任务查询（`/api/business/runs/*`）

- `status` 对外统一为：`queued` / `running` / `succeeded` / `failed`；历史 `cancelled` 进入业务展示层时按失败处理，避免业务方再分支。
- 对外主键使用 `runId`；底层 `taskId` 只用于排查关联，不要求业务方理解。
- 默认查询结果字段统一为 `status/taskStatus/imageUrl/imageUrls/videoUrl/videoUrls/text/texts/error/errorMessage/debugResponse/debugUrl`，不得把底层 ComfyUI 节点名作为主错误文案。
- `/api/business/runs/get` 默认轻量返回；需要 `routeInfo/steps/flowSummary/requestPayload/resultPayload/costBreakdown` 时，必须显式传 `detail=full` 或 `includeDebug=true`。
- 业务版本切换由 `businessKey/version/isDefault/releaseTime` 表达，旧版本保留用于回滚。
- 灰度路由结果统一放在完整模式的 `routeInfo`，包含 `selectedBy/version/businessVersionId/routeKeyHash`；不得返回客户原始灰度标识。
- 业务调用明确传 `version` 时必须优先使用指定版本，不再参与灰度比例。

### 1.4 Agent 同步任务（`/api/agent/*` + `/api/admin/comfyui/tasks*`）

- 允许状态：`pending` / `running` / `success` / `failed` / `rejected`
- 说明：Agent 协议历史上使用 `success`，中台文档必须明确这不是 AbilityTask 的 `succeeded`。
- 桌面端 bootstrap 接口（`/api/agent/bootstrap/*`）不返回任务状态，仅返回接入凭证与 keyset；
  其失败语义统一落在 `AGENT_ENROLL_CODE_*` 和 `AGENT_TOKEN_*`。

### 1.6 清单修复任务（`/api/admin/comfyui/repair-jobs*`）

- `repair-jobs` 必须沿用双阶段字段：
  - `submitStatus` / `callbackStatus` / `finalStatus`
- 聚合任务 `status` 仅用于总览：
  - `pending` / `running` / `succeeded` / `failed` / `partial`
- 行项目 `status` 必须可追溯到实际任务：
  - 有 `taskId` 时以任务状态推导
  - 无 `taskId` 时仅允许 `skipped/failed`（禁止“假成功”）

### 1.5 历史任务中心（`/api/tasks/v1/*`，兼容链路）

- 允许状态：`pending` / `running` / `completed` / `failed`
- 约束：
  - 该链路仅做兼容，不作为新功能入口
  - 与 `AbilityTask` 混用展示时必须做映射

---

## 2. 错误处理统一

### 2.1 错误码优先，错误文案可读

- 返回体中的机器可读错误必须优先使用错误关键字（如 `TASK_NOT_FOUND`）。
- 面向运维/业务页面可展示中文解释，但不得丢失原错误码。

### 2.2 三层错误结构

1) **HTTP 层**：状态码正确（4xx 客户端、5xx 服务端）
2) **业务层**：`detail/errorMessage/debugResponse` 中出现标准错误码
3) **展示层**：人类可读中文（可附原始码）

### 2.3 强约束错误格式

- 队列/并发类必须使用：`ERR|<CODE>|<message>`
- 错误码总表维护于：`docs/standards/error-catalog.md`

---

## 3. 结果回填与“完成”定义

- “任务完成”与“预览可见”是两个状态：
  - 任务完成：`status` 到达终态（如 `succeeded/success/failed`）
  - 预览可见：`stored_url/result_assets` 已回填
- 展示层必须区分：
  - 成功但无预览：显示“结果回填中”，禁止直接显示 `—`
  - **JSON 能力不走图片回填**：若输出类型为 `json_output`，直接渲染结构化 JSON。
- 能力调用日志必须输出 `output_summary`，至少包含图片、视频、文字、结构化结果和普通资源数量，展示层优先使用该摘要，不再只靠 URL 后缀猜测。

---

## 4. 预览字段解析统一顺序

所有列表/详情页、导出逻辑统一按以下顺序取预览 URL：

1. `stored_url`
2. `result_assets[*].ossUrl/url/sourceUrl`
3. `response_payload.assets[*]`
4. `response_payload.images[*]`
5. `response_payload.videos[*]`
6. `response_payload.resultUrls[] / imageUrls[] / videoUrls[] / imageUrl / videoUrl`

---

## 4.1 输出类型归类（强制）

所有工作流必须明确归类输出类型：

- `callback_task_id`：`output` 为 task id，统一通过 `/api/coze/podi/tasks/get` 轮询结果
- `image_url`：直接输出图片 URL（无需回调）
- `video_url`：直接输出视频 URL（无需回调）
- `text_output`：直接输出文本或分析结果
- `json_output`：直接输出结构化 JSON（如 `items/lora_names`、标签结果）

评测端/管理端展示层必须按上述类型选择渲染策略。

---

## 5. 文档一致性要求（硬性）

新增/修改接口时，必须同时更新：

1. 模块接口文档（`docs/api/modules/*.md`）
2. 错误码总表（`docs/standards/error-catalog.md`）
3. 测评端开发文档（`/api/evals/docs/workflows` 对应内容）
4. 若涉及状态/错误口径，必须更新本文档
5. 若涉及业务入口、Coze 工具箱、原生业务 API、原子能力 API 或测评分类，必须更新 `docs/standards/business-interface-taxonomy.md`
6. 若涉及 `/api/business/*` 对外字段、枚举、返回结构或业务方交付材料，必须更新 `docs/standards/business-api-enums.md`

---

## 6. PR 最低验收清单

- [ ] 状态词是否落在本准则允许集合
- [ ] 错误码是否进入 `error-catalog`
- [ ] 前端展示是否保留机器错误码 + 中文解释
- [ ] 文档（管理端 / 测评端）是否同步
- [ ] 至少覆盖 1 条失败路径测试（参数缺失/依赖失败/超时/并发限制）
