"""Admin dashboard endpoints for system overview, monitoring, and logs."""

from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import Executor
from app.models.task import Task, TaskBatch, TaskEvent
from app.schemas import admin_dashboard as schemas

router = APIRouter(prefix="/admin/dashboard", dependencies=[Depends(require_admin)])


def _today_start() -> datetime:
    now = datetime.utcnow()
    return datetime.combine(now.date(), time.min)


@router.get("/metrics", response_model=schemas.DashboardMetricsResponse)
def get_dashboard_metrics() -> schemas.DashboardMetricsResponse:
    today_start = _today_start()
    with get_session() as session:
        total_tasks = session.scalar(select(func.count(Task.id))) or 0

        queue_depth = session.scalar(
            select(func.count(Task.id)).where(Task.status.in_(["created", "pending", "queued"]))
        ) or 0

        pending_batches = session.scalar(
            select(func.count(TaskBatch.id)).where(TaskBatch.status.notin_(["completed", "cancelled"]))
        ) or 0

        failed_tasks = session.scalar(select(func.count(Task.id)).where(Task.status == "failed")) or 0

        status_rows = session.execute(
            select(Task.status, func.count(Task.id)).group_by(Task.status)
        ).all()
        status_buckets = [
            schemas.TaskStatusBucket(status=row[0], count=row[1]) for row in status_rows if row[0] is not None
        ]

        today_rows = session.execute(
            select(Task.status, func.count(Task.id)).where(Task.created_at >= today_start).group_by(Task.status)
        ).all()
        today_map = {row[0]: row[1] for row in today_rows}

        recent_tasks = (
            session.execute(select(Task).order_by(Task.created_at.desc()).limit(8)).scalars().all()
        )

        executor_health = (
            session.execute(select(Executor).order_by(Executor.updated_at.desc())).scalars().all()
        )

    return schemas.DashboardMetricsResponse(
        totals=schemas.DashboardTotals(
            total_tasks=total_tasks,
            queue_depth=queue_depth,
            pending_batches=pending_batches,
            failed_tasks=failed_tasks,
        ),
        status_buckets=status_buckets,
        today=schemas.TodaySummary(
            created=today_map.get("created", 0) + today_map.get("pending", 0),
            completed=today_map.get("completed", 0),
            failed=today_map.get("failed", 0),
        ),
        recent_tasks=[
            schemas.RecentTask(
                id=task.id,
                user_id=task.user_id,
                tool_action=task.tool_action,
                channel=task.channel,
                status=task.status,
                created_at=task.created_at,
                updated_at=task.updated_at,
                error_message=task.error_message,
            )
            for task in recent_tasks
        ],
        executor_health=[
            schemas.ExecutorHealth(
                id=executor.id,
                name=executor.name,
                status=executor.status,
                health_status=executor.health_status,
                max_concurrency=executor.max_concurrency,
                weight=executor.weight,
                last_heartbeat_at=executor.last_heartbeat_at,
            )
            for executor in executor_health
        ],
    )


@router.get("/logs", response_model=schemas.DispatchLogResponse)
def get_dispatch_logs(limit: int = Query(25, ge=1, le=100)) -> schemas.DispatchLogResponse:
    with get_session() as session:
        rows = (
            session.execute(
                select(TaskEvent, Task)
                .join(Task, Task.id == TaskEvent.task_id)
                .order_by(TaskEvent.created_at.desc())
                .limit(limit)
            )
            .all()
        )

    entries = [
        schemas.DispatchLogEntry(
            id=event.id,
            task_id=task.id,
            tool_action=task.tool_action,
            task_status=task.status,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )
        for event, task in rows
    ]
    return schemas.DispatchLogResponse(entries=entries)


@router.get("/system-config", response_model=schemas.SystemConfigResponse)
def get_system_config() -> schemas.SystemConfigResponse:
    settings = get_settings()
    db_url = make_url(settings.database_url)
    backend = getattr(db_url, "get_backend_name", None)
    driver = getattr(db_url, "get_driver_name", None)
    backend_name = backend() if callable(backend) else db_url.drivername.split("+")[0]
    driver_name = driver() if callable(driver) else (db_url.drivername.split("+")[1] if "+" in db_url.drivername else None)
    sanitized_dsn = f"{backend_name}{'+' + driver_name if driver_name else ''}://{db_url.host or 'local'}:{db_url.port or '-'}"
    if db_url.database:
        sanitized_dsn += f"/{db_url.database}"

    todo_items = [
        schemas.TodoItem(
            title="RAM 角色信任策略待收紧",
            description="CLTZ 角色目前允许 root AssumeRole，需要限定来源账号并考虑 MFA；参见 AGENTS.md 中 TODO。",
            severity="high",
        ),
        schemas.TodoItem(
            title="积分服务独立实现",
            description="当前仅有临时积分接口，后续需替换为正式服务并补充扣费审计。",
            severity="medium",
        ),
        schemas.TodoItem(
            title="ComfyUI 工作流管理",
            description="需要在管理端实现工作流上传与版本比对，避免直接修改代码。",
            severity="medium",
        ),
    ]

    feature_flags = {
        "baidu_quality_upgrade": True,
        "oss_direct_upload": True,
        "comfyui_pipeline": False,
        "componentized_ai": False,
    }

    return schemas.SystemConfigResponse(
        app_name=settings.app_name,
        database=schemas.DatabaseConfig(
            backend=backend_name,
            driver=driver_name,
            host=db_url.host,
            port=db_url.port,
            database=db_url.database,
            dsn=sanitized_dsn,
        ),
        oss=schemas.OssConfig(
            bucket=settings.oss_bucket,
            endpoint=settings.oss_endpoint,
            public_domain=settings.oss_public_domain,
            root_prefix=settings.oss_root_prefix,
            sts_duration=settings.oss_sts_duration,
            role_arn=settings.oss_role_arn,
        ),
        security=schemas.SecurityConfig(
            jwt_access_ttl=settings.jwt_access_token_expires,
            jwt_refresh_ttl=settings.jwt_refresh_token_expires,
            upload_token_ttl=settings.upload_token_ttl,
        ),
        feature_flags=feature_flags,
        todo_items=todo_items,
    )
