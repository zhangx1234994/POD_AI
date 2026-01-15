"""Task persistence logic."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, desc

from app.core.db import get_session
from app.models.task import Task, TaskEvent, TaskAsset


class TaskService:
    def create_task(self, payload, wallet_hold_id: str) -> Task:
        """Create a task or update existing one."""
        with get_session() as session:
            task = session.get(Task, payload.taskId)
            if task is None:
                task = Task(
                    id=payload.taskId,
                    user_id=payload.userId,
                    channel=payload.channel,
                    tool_action=payload.action,
                    status="pending",
                    progress=0,
                    wallet_hold_id=wallet_hold_id,
                    points_cost=payload.points,
                    input_payload=payload.workflowParams,
                    created_at=datetime.utcnow(),
                )
                session.add(task)
                session.add(TaskEvent(task_id=task.id, event_type="created", payload={"status": "pending"}))
            else:
                task.wallet_hold_id = wallet_hold_id
                task.points_cost = payload.points
                task.input_payload = payload.workflowParams
                task.tool_action = payload.action
                task.channel = payload.channel
                task.status = "pending"
                task.progress = 0
                task.updated_at = datetime.utcnow()
                session.add(TaskEvent(task_id=task.id, event_type="recreated", payload={"status": "pending"}))

            preview_url = self._sync_input_assets(session, task, payload.workflowParams)
            if preview_url:
                task.result_payload = (task.result_payload or {}) | {"inputPreview": preview_url}
            session.commit()
            session.refresh(task)
            return task

    def get_task(self, task_id: str) -> Task | None:
        with get_session() as session:
            return session.get(Task, task_id)

    def list_tasks(
        self,
        *,
        user_id: str,
        action: str | None = None,
        status: str | None = None,
        page: int = 0,
        size: int = 10,
    ) -> tuple[list[Task], int]:
        with get_session() as session:
            conditions = [Task.user_id == user_id]
            if action:
                conditions.append(Task.tool_action == action)
            if status:
                conditions.append(Task.status == status)

            total_stmt = select(func.count()).select_from(Task).where(*conditions)
            total = session.scalar(total_stmt) or 0

            query = (
                select(Task)
                .where(*conditions)
                .order_by(desc(Task.created_at))
                .offset(page * size)
                .limit(size)
            )
            result = session.execute(query).scalars().all()
            return result, total

    def complete_task(self, task_id: str, success: bool, result_payload: dict[str, Any] | None = None) -> Task:
        with get_session() as session:
            task = session.get(Task, task_id)
            if task is None:
                raise ValueError("TASK_NOT_FOUND")
            task.status = "completed" if success else "failed"
            task.progress = 100
            task.finished_at = datetime.utcnow()
            task.result_payload = result_payload
            session.add(
                TaskEvent(
                    task_id=task.id,
                    event_type="succeeded" if success else "failed",
                    payload={"status": task.status},
                )
            )
            session.commit()
            session.refresh(task)
            return task

    def _sync_input_assets(self, session, task: Task, workflow_params: dict | None) -> str | None:
        if not workflow_params:
            return None
        image_list = workflow_params.get("imageList") or workflow_params.get("image_list")
        if not image_list or not isinstance(image_list, list):
            return None
        session.query(TaskAsset).filter(TaskAsset.task_id == task.id, TaskAsset.asset_type == "input").delete()

        preview_url = None
        for index, item in enumerate(image_list):
            if not isinstance(item, dict):
                continue
            object_key = (
                item.get("objectKey")
                or item.get("ossKey")
                or item.get("key")
                or item.get("filename")
                or f"{task.id}_input_{index}"
            )
            url = item.get("ossUrl") or item.get("url")
            file_name = item.get("filename")
            size = item.get("size") or item.get("sizeBytes")
            metadata = item.get("metadata") or item.get("extra") or {}
            if item.get("o_size"):
                metadata = {**metadata, "o_size": item.get("o_size")}
            asset = TaskAsset(
                task_id=task.id,
                asset_type="input",
                object_key=str(object_key),
                url=url,
                file_name=file_name,
                size_bytes=size,
                extra_metadata=metadata,
            )
            session.add(asset)
            if preview_url is None and url:
                preview_url = url
        return preview_url


task_service = TaskService()
