# 接口一致性统一准则（必须遵守）

> 目标：避免“前后端状态词不一致、错误处理风格不一致、文档口径不一致”。
> 适用范围：`/api/*`（管理端、评测端、Coze 工具、Agent 协议）与所有对外文档。

---

## 1. 状态词统一（按领域）

### 1.1 能力异步任务（`/api/ability-tasks`）

- 允许状态：`queued` / `running` / `succeeded` / `failed` / `cancelled`
- 约束：
  - 不得返回 `success/completed/done` 作为任务状态
  - 失败必须同时提供 `errorMessage`（可空但推荐）

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

### 1.4 Agent 同步任务（`/api/agent/*` + `/api/admin/comfyui/tasks*`）

- 允许状态：`pending` / `running` / `success` / `failed` / `rejected`
- 说明：Agent 协议历史上使用 `success`，中台文档必须明确这不是 AbilityTask 的 `succeeded`。

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

---

## 4. 预览字段解析统一顺序

所有列表/详情页、导出逻辑统一按以下顺序取预览 URL：

1. `stored_url`
2. `result_assets[*].ossUrl/url/sourceUrl`
3. `response_payload.assets[*]`
4. `response_payload.images[*]`
5. `response_payload.resultUrls[] / imageUrls[] / imageUrl`

---

## 5. 文档一致性要求（硬性）

新增/修改接口时，必须同时更新：

1. 模块接口文档（`docs/api/modules/*.md`）  
2. 错误码总表（`docs/standards/error-catalog.md`）  
3. 测评端开发文档（`/api/evals/docs/workflows` 对应内容）  
4. 若涉及状态/错误口径，必须更新本文档

---

## 6. PR 最低验收清单

- [ ] 状态词是否落在本准则允许集合  
- [ ] 错误码是否进入 `error-catalog`  
- [ ] 前端展示是否保留机器错误码 + 中文解释  
- [ ] 文档（管理端 / 测评端）是否同步  
- [ ] 至少覆盖 1 条失败路径测试（参数缺失/依赖失败/超时/并发限制）
