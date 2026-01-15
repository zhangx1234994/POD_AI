"""Mock executor adapter for local development."""

from __future__ import annotations

from datetime import datetime

from .base import ExecutionContext, ExecutionResult


class MockExecutorAdapter:
    """Simulates execution locally without talking to remote AI providers."""

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        preview = (context.task.result_payload or {}).get("inputPreview")
        payload = {
            "executor": context.executor.id,
            "workflowId": context.workflow.id,
            "completedAt": datetime.utcnow().isoformat(),
        }
        if preview:
            payload["inputPreview"] = preview
        return ExecutionResult(
            success=True,
            status="completed",
            progress=100,
            result_payload=payload,
        )
