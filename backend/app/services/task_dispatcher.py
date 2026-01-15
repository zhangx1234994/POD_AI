"""Simple synchronous task dispatcher used during development."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select

from app.core.db import get_session
from app.models.integration import Executor, Workflow, WorkflowBinding
from app.models.task import Task, TaskEvent
from app.services.api_key_service import api_key_service
from app.services.executors import ExecutionContext, ExecutionResult, registry
from app.services.wallet import wallet_service


@dataclass(slots=True)
class DispatchReport:
    task_id: str
    status: str
    progress: int
    message: str | None = None
    wallet_event: dict[str, Any] | None = None


class TaskDispatcherService:
    """Naive dispatcher that runs inside the API process for now."""

    def dispatch_pending(self, limit: int = 5) -> list[DispatchReport]:
        reports: list[DispatchReport] = []
        with get_session() as session:
            stmt: Select[tuple[Task]] = (
                select(Task)
                .where(Task.status.in_(("pending", "queued")))
                .order_by(Task.priority.desc(), Task.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            tasks = session.execute(stmt).scalars().all()
            if not tasks:
                return []

            for task in tasks:
                report = self._process_task(session, task)
                reports.append(report)
        return reports

    def _process_task(self, session, task: Task) -> DispatchReport:
        binding_row = self._pick_binding(session, task.tool_action)
        if not binding_row:
            return self._mark_blocked(session, task, "NO_BINDING_AVAILABLE")

        binding, workflow, executor = binding_row
        adapter = registry.get(executor.type)
        if not adapter:
            return self._mark_blocked(session, task, f"NO_ADAPTER:{executor.type}")

        task.status = "running"
        task.started_at = datetime.utcnow()
        session.add(TaskEvent(task_id=task.id, event_type="started", payload={"executor": executor.id}))
        session.add(task)
        session.commit()
        session.refresh(task)

        provider = (executor.config or {}).get("provider") or executor.type
        api_key = api_key_service.acquire(provider)
        context = ExecutionContext(
            task=task,
            workflow=workflow,
            executor=executor,
            payload=task.input_payload or {},
            api_key=api_key,
        )

        try:
            result = adapter.execute(context)
        except Exception as exc:  # pragma: no cover - defensive
            return self._mark_failed(session, task, f"EXECUTOR_ERROR:{exc}")

        if result.success:
            return self._mark_succeeded(session, task, result)
        return self._mark_failed(session, task, result.error_message or "EXECUTION_FAILED")

    def _pick_binding(self, session, action: str):
        stmt = (
            select(WorkflowBinding, Workflow, Executor)
            .join(Workflow, Workflow.id == WorkflowBinding.workflow_id)
            .join(Executor, Executor.id == WorkflowBinding.executor_id)
            .where(
                WorkflowBinding.action == action,
                WorkflowBinding.enabled.is_(True),
                Executor.status == "active",
            )
            .order_by(WorkflowBinding.priority.desc(), Executor.weight.desc())
            .limit(1)
        )
        return session.execute(stmt).first()

    def _mark_blocked(self, session, task: Task, reason: str) -> DispatchReport:
        task.status = "blocked"
        task.error_message = reason
        session.add(TaskEvent(task_id=task.id, event_type="blocked", payload={"reason": reason}))
        session.add(task)
        session.commit()
        return DispatchReport(task_id=task.id, status="blocked", progress=task.progress, message=reason)

    def _mark_failed(self, session, task: Task, reason: str) -> DispatchReport:
        task.status = "failed"
        task.progress = 100
        task.finished_at = datetime.utcnow()
        task.error_message = reason
        session.add(TaskEvent(task_id=task.id, event_type="failed", payload={"reason": reason}))
        session.add(task)
        session.commit()
        wallet_event = None
        if task.wallet_hold_id:
            _, balance = wallet_service.release(task.wallet_hold_id)
            wallet_event = {
                "type": "wallet.points",
                "payload": {"taskId": task.id, "status": "released", "balance": balance},
            }
        return DispatchReport(task_id=task.id, status="failed", progress=0, message=reason, wallet_event=wallet_event)

    def _mark_succeeded(self, session, task: Task, result: ExecutionResult) -> DispatchReport:
        task.status = "completed"
        task.progress = result.progress or 100
        task.finished_at = datetime.utcnow()
        payload = result.result_payload or {}
        task.result_payload = (task.result_payload or {}) | payload
        session.add(
            TaskEvent(
                task_id=task.id,
                event_type="succeeded",
                payload={"status": task.status, "executorPayload": payload},
            )
        )
        session.add(task)
        session.commit()
        if task.wallet_hold_id:
            wallet_service.confirm(task.wallet_hold_id)
        wallet_event = {
            "type": "wallet.points",
            "payload": {"taskId": task.id, "status": "deducted"},
        }
        return DispatchReport(task_id=task.id, status="completed", progress=task.progress, wallet_event=wallet_event)


task_dispatcher_service = TaskDispatcherService()
