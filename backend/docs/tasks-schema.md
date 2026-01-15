# 任务模型设计

> 当前数据库采用 SQLAlchemy ORM 定义（`app/models/task.py`），通过 `scripts/create_schema.py` 可在指定 `DATABASE_URL` 下建表。以下说明主要字段含义及未来扩展点。

## task_batches
| 字段 | 说明 |
|------|------|
| `id` | 批次 ID，可使用 UUID/雪花。 |
| `user_id` | 发起批处理的用户。 |
| `tool_action` | 功能类型（`hires`、`pattern-extract` 等）。 |
| `title` | 批量任务标题，前端显示。 |
| `status` | `pending/running/completed/failed/cancelled`。 |
| `total_count` / `completed_count` | 批次内包含的任务数量。 |
| `metadata` | JSON 描述批量导入方式、参数模版（字段名在 ORM 中为 `extra_metadata`）。 |
| `created_at` / `updated_at` | 时间戳。 |

## tasks
| 字段 | 说明 |
|------|------|
| `id` | 任务 ID。 |
| `batch_id` | 归属批次；单任务为空。 |
| `user_id` / `channel` | 用户及来源渠道（web-ui/openapi/batch）。 |
| `tool_action` | 功能类型，与前端 action 一致。 |
| `status` | 生命周期状态。 |
| `progress` | 0~100 的进度百分比。 |
| `priority` | 队列优先级，默认 0。 |
| `wallet_hold_id` / `points_cost` | 对应积分冻结/扣款信息。 |
| `input_payload` | 任务参数 JSON（prompt、scale、图片 key 等）。 |
| `result_payload` | 输出摘要 JSON（结果图列表、统计信息等）。 |
| `error_message` | 失败原因。 |
| `notify_cursor` | 推送进度标记。 |
| `is_deleted` | 软删标记，方便回收站。 |
| `created_at` / `updated_at` / `started_at` / `finished_at` | 时间戳。 |

索引：
- `ix_tasks_user_status`：快速查询某用户的运行中/已完成任务。
- `ix_tasks_batch`：批量详情页加载任务列表。

## task_assets
存储任务的输入/输出/预览资源。

| 字段 | 说明 |
|------|------|
| `task_id` | 所属任务。 |
| `asset_type` | `input`/`output`/`preview` 等。 |
| `object_key` / `url` | OSS 对象 Key 与可访问 URL。 |
| `file_name` / `mime_type` / `size_bytes` / `width` / `height` | 元信息。 |
| `checksum` | 校验值，便于去重。 |
| `metadata` | 结构化描述（裁剪参数、所属步骤等，在 ORM 中字段名为 `extra_metadata`）。 |
| 备注 | 提交任务时会把 `workflowParams.imageList` 中的输入图保存为 `asset_type='input'`，并在 `tasks.result_payload.inputPreview` 存首张图片 URL 供前端展示。 |

## task_events
记录任务状态流，用于推送与调试。

| 字段 | 说明 |
|------|------|
| `event_type` | `created`, `progress`, `succeeded`, `failed` 等。 |
| `payload` | JSON 载荷（包含 progress、结果 URL、错误码等）。 |
| `created_at` | 时间戳。 |

## 建表方式
```bash
cd backend
source .venv/bin/activate
export DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/podi
python scripts/create_schema.py
```

如需使用 Alembic，可在后续集成时把 `app/models` 中的 Base 注册到 Alembic env 并生成迁移。
