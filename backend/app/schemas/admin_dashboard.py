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


class DashboardStrategySummary(BaseModel):
    window_hours: int
    business_total: int
    business_succeeded: int
    business_failed: int
    success_rate: float | None = None
    billable: int
    unpriced: int
    no_charge: int
    billing_pending: int
    callback_failed: int
    callback_missing: int
    wallet_settled: int
    wallet_failed: int
    cost_by_currency: dict[str, float]
    quota_units: int
    risk_count: int


class DashboardMetricsResponse(BaseModel):
    totals: DashboardTotals
    queue_overview: QueueOverview
    status_buckets: list[TaskStatusBucket]
    today: TodaySummary
    recent_tasks: list[RecentTask]
    executor_health: list[ExecutorHealth]
    strategy_summary: DashboardStrategySummary


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
    internal_endpoint: str | None = None
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


class StrategySnapshotCreateRequest(BaseModel):
    window_hours: int = Field(default=168, alias="windowHours", ge=1, le=2160)
    note: str | None = None


class StrategySnapshotResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    generated_at: datetime = Field(alias="generatedAt")
    window_hours: int = Field(alias="windowHours")
    note: str | None = None
    summary: DashboardStrategySummary


class StrategySnapshotListResponse(BaseModel):
    items: list[StrategySnapshotResponse]


class WeeklyReportRunRequest(BaseModel):
    window_hours: int = Field(default=168, alias="windowHours", ge=1, le=2160)
    note: str | None = None
    send: bool = False
    webhook_format: str = Field(default="generic", alias="webhookFormat")


class WeeklyReportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    generated_at: datetime = Field(alias="generatedAt")
    window_hours: int = Field(alias="windowHours")
    report_path: str = Field(alias="reportPath")
    snapshot_id: str = Field(alias="snapshotId")
    send_status: str = Field(alias="sendStatus")
    send_detail: str | None = Field(default=None, alias="sendDetail")
    webhook_format: str = Field(alias="webhookFormat")
    webhook_configured: bool = Field(alias="webhookConfigured")
    summary: DashboardStrategySummary


class WeeklyReportListResponse(BaseModel):
    items: list[WeeklyReportResponse]


class ReleasePreflightRunRequest(BaseModel):
    mode: str = "light"
    base_url: str | None = Field(default=None, alias="baseUrl")
    expect_server_url: str | None = Field(default=None, alias="expectServerUrl")


class ReleasePreflightCheck(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    title: str
    status: str
    blocking: bool
    detail: str
    duration_ms: int | None = Field(default=None, alias="durationMs")
    suggestion: str | None = None


class ReleasePreflightResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    mode: str
    status: str
    can_release: bool = Field(alias="canRelease")
    generated_at: datetime = Field(alias="generatedAt")
    base_url: str = Field(alias="baseUrl")
    blocking_count: int = Field(alias="blockingCount")
    warning_count: int = Field(alias="warningCount")
    checks: list[ReleasePreflightCheck]


class ReleasePreflightSnapshotListResponse(BaseModel):
    items: list[ReleasePreflightResponse]


class ReleasePatrolRecordCreateRequest(BaseModel):
    status: str
    command: str | None = None
    report_path: str | None = Field(default=None, alias="reportPath")
    note: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class ReleasePatrolImportRequest(BaseModel):
    report_path: str = Field(alias="reportPath")
    command: str | None = None


class ReleasePatrolRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    status: str
    generated_at: datetime = Field(alias="generatedAt")
    command: str | None = None
    report_path: str | None = Field(default=None, alias="reportPath")
    note: str | None = None
    summary: dict[str, Any]


class ReleasePatrolRecordListResponse(BaseModel):
    items: list[ReleasePatrolRecordResponse]


class ReleaseDecisionRecordCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    title: str | None = None
    preflight_id: str | None = Field(default=None, alias="preflightId")
    patrol_id: str | None = Field(default=None, alias="patrolId")
    note: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class ReleaseDecisionRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    status: str
    title: str
    generated_at: datetime = Field(alias="generatedAt")
    preflight_id: str | None = Field(default=None, alias="preflightId")
    patrol_id: str | None = Field(default=None, alias="patrolId")
    note: str | None = None
    summary: dict[str, Any]


class ReleaseDecisionRecordListResponse(BaseModel):
    items: list[ReleaseDecisionRecordResponse]


class HealthWatchUnitStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    unit: str
    title: str
    kind: str
    status: str
    summary: str
    load_state: str | None = Field(default=None, alias="loadState")
    active_state: str | None = Field(default=None, alias="activeState")
    sub_state: str | None = Field(default=None, alias="subState")
    unit_file_state: str | None = Field(default=None, alias="unitFileState")
    result: str | None = None
    exec_main_status: int | None = Field(default=None, alias="execMainStatus")
    last_trigger: str | None = Field(default=None, alias="lastTrigger")
    next_elapse: str | None = Field(default=None, alias="nextElapse")
    recent_logs: list[str] = Field(default_factory=list, alias="recentLogs")


class HealthWatchStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    generated_at: datetime = Field(alias="generatedAt")
    supported: bool
    items: list[HealthWatchUnitStatus]
    issues: list[str] = Field(default_factory=list)
