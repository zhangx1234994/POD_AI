"""Admin dashboard endpoints for system overview, monitoring, and logs."""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.eval import EvalRun, EvalWorkflowVersion
from app.models.integration import AbilityInvocationLog, AbilityTask, Executor
from app.models.task import Task, TaskBatch, TaskEvent
from app.schemas import admin_dashboard as schemas

router = APIRouter(prefix="/admin/dashboard", dependencies=[Depends(require_admin)])


def _today_start() -> datetime:
    """Return start of today in Asia/Shanghai, converted to naive UTC for DB comparisons.

    Most of our timestamps are stored/treated as UTC in DB. The dashboard, however, should
    reflect China business day boundaries.
    """
    now_cn = datetime.now(ZoneInfo("Asia/Shanghai"))
    start_cn = datetime.combine(now_cn.date(), time.min, tzinfo=ZoneInfo("Asia/Shanghai"))
    return start_cn.astimezone(UTC).replace(tzinfo=None)


@router.get("/metrics", response_model=schemas.DashboardMetricsResponse)
def get_dashboard_metrics() -> schemas.DashboardMetricsResponse:
    today_start = _today_start()
    with get_session() as session:
        # NOTE: The legacy task pipeline uses `tasks`/`task_events`.
        # The evaluation platform and Coze plugin primarily create `eval_run` and `ability_tasks`.
        # For a useful dashboard in the current product stage, we aggregate across all three.
        total_tasks = (session.scalar(select(func.count(Task.id))) or 0) + (
            session.scalar(select(func.count(AbilityTask.id))) or 0
        ) + (session.scalar(select(func.count(EvalRun.id))) or 0)

        queue_depth = (
            (session.scalar(select(func.count(Task.id)).where(Task.status.in_(["created", "pending", "queued"]))) or 0)
            + (session.scalar(select(func.count(AbilityTask.id)).where(AbilityTask.status == "queued")) or 0)
            + (session.scalar(select(func.count(EvalRun.id)).where(EvalRun.status.in_(["queued", "running"]))) or 0)
        )

        pending_batches = session.scalar(
            select(func.count(TaskBatch.id)).where(TaskBatch.status.notin_(["completed", "cancelled"]))
        ) or 0

        failed_tasks = (
            (session.scalar(select(func.count(Task.id)).where(Task.status == "failed")) or 0)
            + (session.scalar(select(func.count(AbilityTask.id)).where(AbilityTask.status == "failed")) or 0)
            + (session.scalar(select(func.count(EvalRun.id)).where(EvalRun.status == "failed")) or 0)
        )

        # Status buckets aggregated across the three pipelines.
        buckets: dict[str, int] = {}
        for status, count in session.execute(select(Task.status, func.count(Task.id)).group_by(Task.status)).all():
            if status is None:
                continue
            buckets[str(status)] = buckets.get(str(status), 0) + int(count or 0)
        for status, count in session.execute(
            select(AbilityTask.status, func.count(AbilityTask.id)).group_by(AbilityTask.status)
        ).all():
            if status is None:
                continue
            buckets[str(status)] = buckets.get(str(status), 0) + int(count or 0)
        for status, count in session.execute(select(EvalRun.status, func.count(EvalRun.id)).group_by(EvalRun.status)).all():
            if status is None:
                continue
            buckets[str(status)] = buckets.get(str(status), 0) + int(count or 0)
        status_buckets = [schemas.TaskStatusBucket(status=k, count=v) for k, v in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))]

        today_map: dict[str, int] = {}
        for status, count in session.execute(
            select(Task.status, func.count(Task.id)).where(Task.created_at >= today_start).group_by(Task.status)
        ).all():
            if status is None:
                continue
            today_map[str(status)] = today_map.get(str(status), 0) + int(count or 0)
        for status, count in session.execute(
            select(AbilityTask.status, func.count(AbilityTask.id)).where(AbilityTask.created_at >= today_start).group_by(AbilityTask.status)
        ).all():
            if status is None:
                continue
            today_map[str(status)] = today_map.get(str(status), 0) + int(count or 0)
        for status, count in session.execute(
            select(EvalRun.status, func.count(EvalRun.id)).where(EvalRun.created_at >= today_start).group_by(EvalRun.status)
        ).all():
            if status is None:
                continue
            today_map[str(status)] = today_map.get(str(status), 0) + int(count or 0)

        # Merge recent "tasks" from all pipelines.
        legacy_tasks = session.execute(select(Task).order_by(Task.created_at.desc()).limit(8)).scalars().all()
        ability_tasks = (
            session.execute(select(AbilityTask).order_by(AbilityTask.created_at.desc()).limit(8)).scalars().all()
        )
        eval_rows = (
            session.execute(
                select(EvalRun, EvalWorkflowVersion)
                .join(EvalWorkflowVersion, EvalWorkflowVersion.id == EvalRun.workflow_version_id, isouter=True)
                .order_by(EvalRun.created_at.desc())
                .limit(8)
            )
            .all()
        )
        recent: list[schemas.RecentTask] = []
        for task in legacy_tasks:
            recent.append(
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
            )
        for t in ability_tasks:
            recent.append(
                schemas.RecentTask(
                    id=t.id,
                    user_id=str(t.user_id or ""),
                    tool_action=f"{t.ability_provider}:{t.capability_key or ''}",
                    channel="ability-task",
                    status=t.status,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                    error_message=t.error_message,
                )
            )
        for run, wf in eval_rows:
            name = wf.name if wf else (run.workflow_version_id or "eval")
            recent.append(
                schemas.RecentTask(
                    id=run.id,
                    user_id=run.created_by,
                    tool_action=f"eval:{name}",
                    channel="eval",
                    status=run.status,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                    error_message=run.error_message,
                )
            )
        recent.sort(key=lambda x: x.created_at, reverse=True)
        recent_tasks = recent[:8]

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
            created=int(today_map.get("created", 0) + today_map.get("pending", 0) + today_map.get("queued", 0)),
            completed=int(today_map.get("completed", 0) + today_map.get("succeeded", 0)),
            failed=int(today_map.get("failed", 0)),
        ),
        recent_tasks=recent_tasks,
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

    entries: list[schemas.DispatchLogEntry] = []
    for event, task in rows:
        entries.append(
            schemas.DispatchLogEntry(
                id=event.id,
                task_id=task.id,
                tool_action=task.tool_action,
                task_status=task.status,
                event_type=event.event_type,
                payload=event.payload,
                created_at=event.created_at,
            )
        )

    # If the legacy pipeline has no events, fall back to ability invocation logs
    # so the dashboard isn't a "whiteboard" during eval/testing stage.
    if not entries:
        with get_session() as session:
            logs = (
                session.execute(select(AbilityInvocationLog).order_by(AbilityInvocationLog.created_at.desc()).limit(limit))
                .scalars()
                .all()
            )
        for log in logs:
            payload = {
                "source": log.source,
                "executor": log.executor_name or log.executor_id or log.executor_type,
                "stored_url": log.stored_url,
                "error": log.error_message,
                "trace_id": log.trace_id,
                "workflow_run_id": log.workflow_run_id,
            }
            entries.append(
                schemas.DispatchLogEntry(
                    id=int(log.id),
                    task_id=str(log.task_id or ""),
                    tool_action=f"{log.ability_provider}:{log.capability_key}",
                    task_status=log.status,
                    event_type="ability_invocation",
                    payload={k: v for k, v in payload.items() if v},
                    created_at=log.created_at,
                )
            )
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
    coze_token_hint = None
    if settings.coze_api_token:
        coze_token_hint = "COZE_API_TOKEN"
    elif settings.service_api_token:
        coze_token_hint = "SERVICE_API_TOKEN"
    coze_config = schemas.CozeConfig(
        base_url=settings.coze_base_url,
        loop_base_url=settings.coze_loop_base_url,
        default_timeout=settings.coze_default_timeout,
        token_present=bool(settings.coze_api_token or settings.service_api_token),
        token_hint=coze_token_hint,
    )
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
        coze=coze_config,
        feature_flags=feature_flags,
        todo_items=todo_items,
    )
