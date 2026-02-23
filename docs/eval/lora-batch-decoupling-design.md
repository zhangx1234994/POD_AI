# LoRA 批测两阶段解耦设计（定稿）

> 状态：已定稿（用于分步实施）  
> 版本：2026-02-23

## 1. 背景与问题

当前 LoRA 批测由前端直接循环执行“上传图片 + 创建任务 + 轮询结果”，在大批量场景下会出现：

- 上传与任务创建耦合，网络波动导致“素材成功但任务缺失”或“任务创建重复”
- 停止批次后仍可能有旧页面继续提交
- 明细查询与提交并行，接口压力高、超时概率上升
- 批次语义依赖 `parameters_json` 内部字段，不利于统计与治理

## 2. 目标与边界

### 2.1 目标

- 批测链路拆成两个阶段：
  - 阶段 A：素材上传阶段
  - 阶段 B：任务创建与执行阶段
- 前端不再直接循环创建评测任务，由后端统一展开执行项
- 停止批次为后端强约束：停止后不允许新增执行项
- 统计口径统一，异常可回放、可重试、可审计

### 2.2 非目标

- 本阶段不改 Coze/ComfyUI/KIE 的底层执行适配逻辑
- 不调整业务工作流参数语义（仅治理提交流程与状态管理）

## 3. 总体架构（四层解耦）

1. 素材层：上传、校验、重试、去重
2. 批次层：批次状态机、任务展开、停止与恢复
3. 执行层：按现有 eval_run / ability_task 调度执行
4. 展示层：只读状态，不驱动核心写操作

## 4. 数据模型（新增）

### 4.1 `eval_batch_session`

- 主键：`id`（string）
- 核心字段：`workflow_version_id`、`created_by`、`status`
- 计划字段：`planned_image_count`、`repeat_count`、`planned_run_count`
- 进度字段：`uploaded_count`、`upload_failed_count`、`submitted_count`、`running_count`、`succeeded_count`、`failed_count`、`canceled_count`
- 错误/元数据：`last_error_code`、`last_error_message`、`metadata`
- 时间：`created_at`、`updated_at`、`finished_at`

### 4.2 `eval_batch_asset`

- 主键：`id`（string）
- 外键：`batch_session_id -> eval_batch_session.id`
- 业务字段：`source_key`、`file_name`、`oss_url`、`object_key`、`size_bytes`、`width`、`height`
- 状态字段：`upload_status`（pending/uploading/uploaded/failed/skipped）
- 错误字段：`upload_error_code`、`upload_error_message`
- 时间：`created_at`、`updated_at`
- 约束：`(batch_session_id, source_key)` 唯一

### 4.3 `eval_batch_run_item`

- 主键：`id`（string）
- 外键：
  - `batch_session_id -> eval_batch_session.id`
  - `asset_id -> eval_batch_asset.id`
  - `eval_run_id -> eval_run.id`（可空）
- 业务字段：`repeat_index`
- 状态字段：`status`（pending/submitting/submitted/running/succeeded/failed/canceled）
- 错误字段：`error_code`、`error_message`
- 时间：`created_at`、`updated_at`
- 约束：`(batch_session_id, asset_id, repeat_index)` 唯一

## 5. 状态机（强约束）

### 5.1 批次状态

- `draft`（草稿）
- `uploading`（上传中）
- `ready`（素材上传完成，待提交）
- `submitting`（批量创建任务中）
- `running`（任务已提交，执行中）
- `succeeded`（全部完成且无失败）
- `failed`（批次级失败）
- `stopped`（人工停止）

转移规则：

- `stopped` 为终态；进入后禁止新增执行项
- `ready -> submitting` 为唯一提交入口
- `submitting/running` 允许转 `stopped`

### 5.2 素材状态

- `pending -> uploading -> uploaded`
- `uploading -> failed`
- `failed -> uploading`（手动重试）

### 5.3 执行项状态

- `pending -> submitting -> submitted -> running -> succeeded/failed`
- 任意未完成态可转 `canceled`（批次停止）

## 6. 错误码（批测域）

- `BATCH_STOPPED`：批次已停止，拒绝写入
- `BATCH_NOT_READY`：素材未完成，不能提交
- `BATCH_PLAN_LIMIT_EXCEEDED`：计划条数超上限
- `BATCH_ASSET_DUPLICATE`：素材重复登记
- `BATCH_ASSET_UPLOAD_FAILED`：素材上传失败
- `BATCH_ITEM_SUBMIT_FAILED`：执行项创建失败
- `BATCH_INTEGRITY_MISMATCH`：批次统计不一致

> 错误码总表上线时同步登记到 `docs/standards/error-catalog.md`。

## 7. 接口规划（后端主导）

### 7.1 批次

- `POST /api/evals/batches`：创建批次
- `GET /api/evals/batches`：批次列表
- `GET /api/evals/batches/{batch_id}`：批次详情
- `POST /api/evals/batches/{batch_id}/stop`：停止批次
- `POST /api/evals/batches/{batch_id}/submit`：开始提交

### 7.2 素材

- `POST /api/evals/batches/{batch_id}/assets`：登记素材（前端上传 OSS 成功后调用）
- `GET /api/evals/batches/{batch_id}/assets`：素材分页

### 7.3 执行项

- `GET /api/evals/batches/{batch_id}/items`：执行项分页
- `POST /api/evals/batches/{batch_id}/items/retry`：失败执行项重试（后续）

## 8. 分步实施

### 第 1 步（当前）

- 文档定稿
- 落地数据库表结构与索引（不切流量）

### 第 2 步

- 后端实现批次/素材/执行项 API（保留旧接口）
- 后端提交器统一展开执行项，前端停止直提

### 第 3 步

- 前端切换到新流程（创建批次 -> 上传素材 -> 开始提交）
- 明细分页与进度分层展示

### 第 4 步

- 灰度开关上线，按账号切流
- 回归后全量切换，旧逻辑下线

## 9. 验收标准

- 停止批次后 5 秒内无新增执行项
- 页面关闭后不会继续产生新任务
- 计划数与执行项状态总数保持恒等
- 大批量（500+）提交时，明细查询无全量超时

## 10. 回滚策略

- 使用开关回退到旧流程
- 新表保留，不影响旧接口与历史数据
- 回滚不执行删表，仅停用新写路径
