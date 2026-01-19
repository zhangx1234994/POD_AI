"""Models for executor/workflow/api-key management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Executor(Base):
    __tablename__ = "executors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # comfyui/openai/aliyun/etc
    base_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="inactive", nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    health_status: Mapped[str | None] = mapped_column(String(32))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    workflow_bindings: Mapped[list["WorkflowBinding"]] = relationship(back_populates="executor")
    api_key_links: Mapped[list["ExecutorApiKey"]] = relationship(
        back_populates="executor",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        secondary="executor_api_keys",
        primaryjoin="Executor.id==ExecutorApiKey.executor_id",
        secondaryjoin="ExecutorApiKey.api_key_id==ApiKey.id",
        viewonly=True,
    )

    @property
    def api_key_ids(self) -> list[str]:
        return [link.api_key_id for link in self.api_key_links]


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    type: Mapped[str] = mapped_column(String(32), default="generic")
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="inactive")
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    bindings: Mapped[list["WorkflowBinding"]] = relationship(back_populates="workflow")


class WorkflowBinding(Base):
    __tablename__ = "workflow_bindings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflows.id", ondelete="CASCADE"))
    executor_id: Mapped[str] = mapped_column(String(64), ForeignKey("executors.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    executor: Mapped[Executor] = relationship(back_populates="workflow_bindings")
    workflow: Mapped[Workflow] = relationship(back_populates="bindings")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    daily_quota: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    executor_links: Mapped[list["ExecutorApiKey"]] = relationship(
        back_populates="api_key",
        cascade="all, delete-orphan",
    )


class ExecutorApiKey(Base):
    __tablename__ = "executor_api_keys"

    executor_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("executors.id", ondelete="CASCADE"),
        primary_key=True,
    )
    api_key_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    executor: Mapped[Executor] = relationship(back_populates="api_key_links")
    api_key: Mapped[ApiKey] = relationship(back_populates="executor_links")

class Ability(Base):
    __tablename__ = "abilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="inactive", nullable=False)
    ability_type: Mapped[str] = mapped_column(String(32), default="api", nullable=False)
    executor_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("executors.id", ondelete="SET NULL"))
    workflow_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("workflows.id", ondelete="SET NULL"))
    coze_workflow_id: Mapped[str | None] = mapped_column(String(64))
    default_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_health_status: Mapped[str | None] = mapped_column(String(32))
    success_rate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    executor: Mapped[Executor | None] = relationship()
    workflow: Mapped[Workflow | None] = relationship()


class AbilityInvocationLog(Base):
    __tablename__ = "ability_invocation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ability_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("abilities.id", ondelete="SET NULL"), nullable=True
    )
    ability_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ability_name: Mapped[str | None] = mapped_column(String(128))
    executor_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("executors.id", ondelete="SET NULL"), nullable=True
    )
    executor_name: Mapped[str | None] = mapped_column(String(128))
    executor_type: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="admin-test", nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    stored_url: Mapped[str | None] = mapped_column(String(512))
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_assets: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    workflow_run_id: Mapped[str | None] = mapped_column(String(64))
    billing_unit: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    currency: Mapped[str | None] = mapped_column(String(16))
    cost_amount: Mapped[float | None] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class AbilityTask(Base):
    __tablename__ = "ability_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ability_id: Mapped[str] = mapped_column(String(64), ForeignKey("abilities.id", ondelete="CASCADE"), nullable=False)
    ability_name: Mapped[str | None] = mapped_column(String(128))
    ability_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_key: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    user_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    log_id: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    callback_url: Mapped[str | None] = mapped_column(String(512))
    callback_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class AbilityCostSnapshot(Base):
    __tablename__ = "ability_cost_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ability_id: Mapped[str] = mapped_column(String(64), ForeignKey("abilities.id", ondelete="CASCADE"), nullable=False)
    executor_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("executors.id", ondelete="SET NULL"),
        nullable=True,
    )
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    invocation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost: Mapped[float | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str | None] = mapped_column(String(16))
    unit: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
