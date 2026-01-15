"""Shared execution context/adapter definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ExecutionContext:
    task: Any
    workflow: Any
    executor: Any
    payload: dict[str, Any]
    api_key: Any | None = None


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    status: str
    progress: int = 0
    result_payload: dict[str, Any] | None = None
    error_message: str | None = None


class ExecutorAdapter(Protocol):
    """Protocol for executor implementations."""

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        ...
