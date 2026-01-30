"""Schemas for admin dashboard, monitoring, and system configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskStatusBucket(BaseModel):
    status: str
    count: int


class TodaySummary(BaseModel):
    created: int
    completed: int
    failed: int


class DashboardTotals(BaseModel):
    total_tasks: int
    queue_depth: int
    pending_batches: int
    failed_tasks: int


class QueueOverview(BaseModel):
    total_pending: int
    total_running: int
    task_pending: int
    task_running: int
    ability_pending: int
    ability_running: int
    eval_pending: int
    eval_running: int
    pending_batches: int
    pending_batch_tasks: int


class RecentTask(BaseModel):
    id: str
    user_id: str
    tool_action: str
    channel: str
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class ExecutorHealth(BaseModel):
    id: str
    name: str
    status: str
    health_status: str | None = None
    max_concurrency: int
    weight: int
    last_heartbeat_at: datetime | None = None


class DashboardMetricsResponse(BaseModel):
    totals: DashboardTotals
    queue_overview: QueueOverview
    status_buckets: list[TaskStatusBucket]
    today: TodaySummary
    recent_tasks: list[RecentTask]
    executor_health: list[ExecutorHealth]


class DispatchLogEntry(BaseModel):
    id: int
    task_id: str
    tool_action: str
    task_status: str
    event_type: str
    payload: dict[str, Any] | None = None
    created_at: datetime


class DispatchLogResponse(BaseModel):
    entries: list[DispatchLogEntry]


class DatabaseConfig(BaseModel):
    backend: str
    driver: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    dsn: str


class OssConfig(BaseModel):
    bucket: str
    endpoint: str
    public_domain: str | None = None
    root_prefix: str
    sts_duration: int
    role_arn: str | None = None


class SecurityConfig(BaseModel):
    jwt_access_ttl: int
    jwt_refresh_ttl: int
    upload_token_ttl: int


class CozeConfig(BaseModel):
    base_url: str | None = None
    loop_base_url: str | None = None
    default_timeout: int
    token_present: bool = False
    token_hint: str | None = None


class TodoItem(BaseModel):
    title: str
    description: str
    severity: str = Field(default="medium", description="low/medium/high/critical")
    status: str = "pending"


class SystemConfigResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    app_name: str
    database: DatabaseConfig
    oss: OssConfig
    security: SecurityConfig
    coze: CozeConfig | None = None
    feature_flags: dict[str, bool]
    todo_items: list[TodoItem]
