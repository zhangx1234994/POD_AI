"""Models for executor/workflow/api-key management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
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

    @property
    def tags(self) -> list[str]:
        cfg = self.config if isinstance(self.config, dict) else {}
        raw = cfg.get("tags") or cfg.get("tag")
        values: list[str] = []
        if isinstance(raw, list):
            values = [str(item).strip() for item in raw if str(item).strip()]
        elif isinstance(raw, str):
            values = [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]
        elif raw is not None:
            values = [str(raw).strip()] if str(raw).strip() else []
        return values


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


class ComfyuiLora(Base):
    __tablename__ = "comfyui_lora_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_model: Mapped[str | None] = mapped_column(String(256))
    base_models: Mapped[list[str] | None] = mapped_column(JSON)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    trigger_words: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ComfyuiModelCatalog(Base):
    __tablename__ = "comfyui_model_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    download_url: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ComfyuiPluginCatalog(Base):
    __tablename__ = "comfyui_plugin_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    download_url: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ComfyuiVersionCatalog(Base):
    __tablename__ = "comfyui_version_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    repo_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    download_url: Mapped[str | None] = mapped_column(Text)
    released_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class ComfyuiServerDiffLog(Base):
    __tablename__ = "comfyui_server_diff_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    baseline_executor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class VendorModelCatalog(Base):
    __tablename__ = "vendor_model_catalog"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_vendor_model_catalog_provider_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    api_types: Mapped[list[str] | None] = mapped_column(JSON)
    execution_modes: Mapped[list[str] | None] = mapped_column(JSON)
    supports_mask: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_multiple_images: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_video: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_text: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_global_egress: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="backend-admin", nullable=False)
    route_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    default_task_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    cost_policy: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Ability(Base):
    __tablename__ = "abilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="inactive", nullable=False)
    ability_type: Mapped[str] = mapped_column(String(32), default="api", nullable=False)
    executor_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("executors.id", ondelete="SET NULL"))
    workflow_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("workflows.id", ondelete="SET NULL"))
    vendor_model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vendor_model_catalog.id", ondelete="SET NULL")
    )
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
    vendor_model: Mapped[VendorModelCatalog | None] = relationship()


class AbilityInvocationLog(Base):
    __tablename__ = "ability_invocation_logs"
    __table_args__ = (
        Index("ix_ability_logs_provider_capability_created", "ability_provider", "capability_key", "created_at"),
        Index("ix_ability_logs_status_created", "status", "created_at"),
        Index("ix_ability_logs_source_created", "source", "created_at"),
    )

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
    callback_status: Mapped[str | None] = mapped_column(String(32))
    callback_http_status: Mapped[int | None] = mapped_column(Integer)
    callback_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    callback_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    callback_error: Mapped[str | None] = mapped_column(Text)
    callback_started_at: Mapped[datetime | None] = mapped_column(DateTime)
    callback_finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    workflow_run_id: Mapped[str | None] = mapped_column(String(64))
    billing_unit: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 4))
    currency: Mapped[str | None] = mapped_column(String(16))
    cost_amount: Mapped[float | None] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
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


class BusinessCapability(Base):
    __tablename__ = "business_capabilities"
    __table_args__ = (
        UniqueConstraint("business_key", "version", name="uq_business_capability_key_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="inactive", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    release_time: Mapped[datetime | None] = mapped_column(DateTime)
    recipe: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BusinessDefaultApproval(Base):
    __tablename__ = "business_default_approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_capability_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("business_capabilities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_capability_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_capabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    requester_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    requester_username: Mapped[str | None] = mapped_column(String(128))
    approver_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    approver_username: Mapped[str | None] = mapped_column(String(128))
    request_note: Mapped[str | None] = mapped_column(Text)
    decision_note: Mapped[str | None] = mapped_column(Text)
    before_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    source_capability: Mapped[BusinessCapability | None] = relationship(
        foreign_keys=[source_capability_id],
    )
    target_capability: Mapped[BusinessCapability] = relationship(
        foreign_keys=[target_capability_id],
    )


class BusinessOperationLog(Base):
    __tablename__ = "business_operation_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_username: Mapped[str | None] = mapped_column(String(128))
    actor_role: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    before_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class BusinessClient(Base):
    __tablename__ = "business_clients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    allowed_business_keys: Mapped[list[str] | None] = mapped_column(JSON)
    daily_run_limit: Mapped[int | None] = mapped_column(Integer)
    daily_quota_units: Mapped[int | None] = mapped_column(Integer)
    concurrent_run_limit: Mapped[int | None] = mapped_column(Integer)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BusinessApiKeyUsageLog(Base):
    __tablename__ = "business_api_key_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("api_keys.id", ondelete="SET NULL"), index=True)
    api_key_name: Mapped[str | None] = mapped_column(String(128))
    api_key_preview: Mapped[str | None] = mapped_column(String(32))
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(256), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    error_code: Mapped[str | None] = mapped_column(String(128))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class BusinessRun(Base):
    __tablename__ = "business_runs"
    __table_args__ = (
        Index("ix_business_runs_key_created", "business_key", "created_at"),
        Index("ix_business_runs_key_status_created", "business_key", "status", "created_at"),
        Index("ix_business_runs_version_created", "business_version_id", "created_at"),
        Index("ix_business_runs_version_status_created", "business_version_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("business_capabilities.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), default="business-api", nullable=False)
    channel: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    user_name: Mapped[str | None] = mapped_column(String(128))
    ability_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("abilities.id", ondelete="SET NULL"))
    ability_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("ability_tasks.id", ondelete="SET NULL"))
    ability_log_id: Mapped[int | None] = mapped_column(Integer)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    image_urls: Mapped[list[str] | None] = mapped_column(JSON)
    video_urls: Mapped[list[str] | None] = mapped_column(JSON)
    texts: Mapped[list[str] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    billing_unit: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[float | None] = mapped_column(Numeric(14, 6))
    currency: Mapped[str | None] = mapped_column(String(16))
    cost_amount: Mapped[float | None] = mapped_column(Numeric(14, 4))
    quota_units: Mapped[int | None] = mapped_column(Integer)
    cost_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    callback_url: Mapped[str | None] = mapped_column(String(512))
    callback_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    callback_status: Mapped[str | None] = mapped_column(String(32))
    callback_http_status: Mapped[int | None] = mapped_column(Integer)
    callback_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    callback_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    callback_error: Mapped[str | None] = mapped_column(Text)
    debug_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    business_version: Mapped[BusinessCapability | None] = relationship()


class BusinessAgentSession(Base):
    __tablename__ = "business_agent_sessions"
    __table_args__ = (
        Index("ix_business_agent_sessions_agent_status_updated", "agent_key", "status", "updated_at"),
        Index("ix_business_agent_sessions_tenant_client_updated", "tenant_id", "client_id", "updated_at"),
        Index("ix_business_agent_sessions_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_key: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="collecting_context", nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(128))
    image_url: Mapped[str | None] = mapped_column(String(1024))
    latest_plan_id: Mapped[str | None] = mapped_column(String(64), index=True)
    latest_run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("business_runs.id", ondelete="SET NULL"))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    user_name: Mapped[str | None] = mapped_column(String(128))
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    latest_run: Mapped[BusinessRun | None] = relationship()


class BusinessAgentMessage(Base):
    __tablename__ = "business_agent_messages"
    __table_args__ = (
        Index("ix_business_agent_messages_session_created", "session_id", "created_at"),
        Index("ix_business_agent_messages_role_created", "role", "created_at"),
        Index("uq_business_agent_messages_session_request", "session_id", "request_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    plan_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("business_runs.id", ondelete="SET NULL"))
    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    run: Mapped[BusinessRun | None] = relationship()


class BusinessAgentPlan(Base):
    __tablename__ = "business_agent_plans"
    __table_args__ = (
        Index("ix_business_agent_plans_session_created", "session_id", "created_at"),
        Index("ix_business_agent_plans_status_updated", "status", "updated_at"),
        Index("ix_business_agent_plans_tool_created", "tool_name", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_key: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="awaiting_confirmation", nullable=False, index=True)
    intent: Mapped[str] = mapped_column(String(64), default="image_edit", nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(128))
    summary: Mapped[str | None] = mapped_column(Text)
    edit_plan: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    tool_name: Mapped[str] = mapped_column(String(96), default="business.image_edit", nullable=False, index=True)
    tool_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    estimated_cost_level: Mapped[str | None] = mapped_column(String(32))
    risk_level: Mapped[str | None] = mapped_column(String(32))
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    planner_model: Mapped[str | None] = mapped_column(String(128))
    planner_mode: Mapped[str | None] = mapped_column(String(64))
    warnings: Mapped[list[str] | None] = mapped_column(JSON)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BusinessAgentToolCall(Base):
    __tablename__ = "business_agent_tool_calls"
    __table_args__ = (
        Index("ix_business_agent_tool_calls_session_created", "session_id", "created_at"),
        Index("ix_business_agent_tool_calls_plan_created", "plan_id", "created_at"),
        Index("ix_business_agent_tool_calls_business_created", "business_key", "created_at"),
        Index("ix_business_agent_tool_calls_run_id", "run_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_agent_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("business_runs.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    run: Mapped[BusinessRun | None] = relationship()


class BusinessProject(Base):
    __tablename__ = "business_projects"
    __table_args__ = (
        Index("ix_business_projects_tenant_client_updated", "tenant_id", "client_id", "updated_at"),
        Index("ix_business_projects_scenario_status_updated", "scenario", "status", "updated_at"),
        Index("ix_business_projects_owner_updated", "owner_user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    owner_user_name: Mapped[str | None] = mapped_column(String(128))
    current_flow_step_key: Mapped[str | None] = mapped_column(String(64))
    flow_template_id: Mapped[str | None] = mapped_column(String(64), index=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    assets: Mapped[list["BusinessProjectAsset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    run_links: Mapped[list["BusinessProjectRunLink"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    selections: Mapped[list["BusinessProjectSelection"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    export_packages: Mapped[list["BusinessExportPackage"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class BusinessProjectAsset(Base):
    __tablename__ = "business_project_assets"
    __table_args__ = (
        Index("ix_business_project_assets_project_type_created", "project_id", "asset_type", "created_at"),
        Index("ix_business_project_assets_project_selected_updated", "project_id", "selected", "updated_at"),
        Index("ix_business_project_assets_source_run_output", "source_run_id", "source_output_index"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    url: Mapped[str | None] = mapped_column(String(1024))
    content_type: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str | None] = mapped_column(String(255))
    source_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("business_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_business_key: Mapped[str | None] = mapped_column(String(64), index=True)
    source_flow_step_key: Mapped[str | None] = mapped_column(String(64), index=True)
    source_output_index: Mapped[int | None] = mapped_column(Integer)
    quality_grade: Mapped[str | None] = mapped_column(String(32), index=True)
    input_tags: Mapped[list[str] | None] = mapped_column(JSON)
    issue_tags: Mapped[list[str] | None] = mapped_column(JSON)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    project: Mapped[BusinessProject] = relationship(back_populates="assets")
    source_run: Mapped[BusinessRun | None] = relationship()


class BusinessProjectRunLink(Base):
    __tablename__ = "business_project_run_links"
    __table_args__ = (
        Index("ix_business_project_run_links_project_step_created", "project_id", "flow_step_key", "created_at"),
        Index("ix_business_project_run_links_project_client_request", "project_id", "client_request_id"),
        Index("ix_business_project_run_links_business_created", "business_key", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    flow_step_key: Mapped[str | None] = mapped_column(String(64), index=True)
    flow_step_name: Mapped[str | None] = mapped_column(String(128))
    flow_template_id: Mapped[str | None] = mapped_column(String(64), index=True)
    input_asset_ids: Mapped[list[str] | None] = mapped_column(JSON)
    output_asset_ids: Mapped[list[str] | None] = mapped_column(JSON)
    client_request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    asset_sync_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    asset_sync_error: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    project: Mapped[BusinessProject] = relationship(back_populates="run_links")
    run: Mapped[BusinessRun] = relationship()


class BusinessProjectSelection(Base):
    __tablename__ = "business_project_selections"
    __table_args__ = (
        Index("ix_business_project_selections_project_created", "project_id", "created_at"),
        Index("ix_business_project_selections_asset_created", "asset_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_project_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("business_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_flow_step_key: Mapped[str | None] = mapped_column(String(64), index=True)
    target_flow_step_key: Mapped[str | None] = mapped_column(String(64), index=True)
    selected_by_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    selected_by_user_name: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    project: Mapped[BusinessProject] = relationship(back_populates="selections")
    asset: Mapped[BusinessProjectAsset] = relationship()
    source_run: Mapped[BusinessRun | None] = relationship()


class BusinessExportPackage(Base):
    __tablename__ = "business_export_packages"
    __table_args__ = (
        Index("ix_business_export_packages_project_created", "project_id", "created_at"),
        Index("ix_business_export_packages_status_updated", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    run_ids: Mapped[list[str] | None] = mapped_column(JSON)
    download_url: Mapped[str | None] = mapped_column(String(1024))
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    project: Mapped[BusinessProject] = relationship(back_populates="export_packages")


class BusinessOutputReview(Base):
    __tablename__ = "business_output_reviews"
    __table_args__ = (
        UniqueConstraint("run_id", "output_index", name="uq_business_output_review_run_output"),
        Index("ix_business_output_reviews_business_created", "business_key", "created_at"),
        Index("ix_business_output_reviews_batch_created", "batch_id", "created_at"),
        Index("ix_business_output_reviews_grade_created", "quality_grade", "created_at"),
        Index("ix_business_output_reviews_version_created", "business_version_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("business_capabilities.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[str | None] = mapped_column(String(32))
    output_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_url: Mapped[str | None] = mapped_column(String(1024))
    sample_key: Mapped[str | None] = mapped_column(String(64))
    sample_label: Mapped[str | None] = mapped_column(String(128))
    batch_id: Mapped[str | None] = mapped_column(String(64))
    quality_grade: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    input_tags: Mapped[list[str] | None] = mapped_column(JSON)
    issue_tags: Mapped[list[str] | None] = mapped_column(JSON)
    next_action: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    reviewer_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_username: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    run: Mapped[BusinessRun] = relationship()
    business_version: Mapped[BusinessCapability | None] = relationship()


class BusinessQualitySample(Base):
    __tablename__ = "business_quality_samples"
    __table_args__ = (
        UniqueConstraint("business_key", "sample_key", name="uq_business_quality_sample_business_key"),
        Index("ix_business_quality_samples_business_status", "business_key", "status"),
        Index("ix_business_quality_samples_business_sort", "business_key", "sort_order", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    generated_image_url: Mapped[str | None] = mapped_column(String(1024))
    input_tags: Mapped[list[str] | None] = mapped_column(JSON)
    default_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    created_by_username: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BusinessQualitySampleVersion(Base):
    __tablename__ = "business_quality_sample_versions"
    __table_args__ = (
        Index("ix_business_quality_sample_versions_sample_created", "sample_id", "created_at"),
        Index("ix_business_quality_sample_versions_business_key", "business_key", "sample_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sample_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_quality_samples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    generated_image_url: Mapped[str | None] = mapped_column(String(1024))
    input_tags: Mapped[list[str] | None] = mapped_column(JSON)
    default_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    change_note: Mapped[str | None] = mapped_column(Text)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    actor_username: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    sample: Mapped[BusinessQualitySample] = relationship()


class BusinessQualityActionRule(Base):
    __tablename__ = "business_quality_action_rules"
    __table_args__ = (
        UniqueConstraint("business_key", "rule_key", name="uq_business_quality_action_business_key"),
        Index("ix_business_quality_action_business_status", "business_key", "status"),
        Index("ix_business_quality_action_business_type", "business_key", "action_type"),
        Index("ix_business_quality_action_business_priority", "business_key", "priority", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    issue_tags: Mapped[list[str] | None] = mapped_column(JSON)
    input_tags: Mapped[list[str] | None] = mapped_column(JSON)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_business_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("business_capabilities.id", ondelete="SET NULL")
    )
    target_version: Mapped[str | None] = mapped_column(String(32))
    target_label: Mapped[str | None] = mapped_column(String(128))
    target_ref: Mapped[str | None] = mapped_column(String(128))
    target_params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sample_batch_id: Mapped[str | None] = mapped_column(String(64), index=True)
    evidence_review_ids: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"))
    owner_username: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    target_business_version: Mapped[BusinessCapability | None] = relationship()


class BusinessRunStep(Base):
    __tablename__ = "business_run_steps"
    __table_args__ = (
        Index("ix_business_run_steps_run_order_id", "run_id", "step_order", "id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("business_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(64))
    step_type: Mapped[str] = mapped_column(String(64), default="ability_task", nullable=False)
    role: Mapped[str | None] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False, index=True)
    ability_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("abilities.id", ondelete="SET NULL"))
    ability_name: Mapped[str | None] = mapped_column(String(128))
    ability_provider: Mapped[str | None] = mapped_column(String(64))
    ability_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("ability_tasks.id", ondelete="SET NULL"))
    ability_log_id: Mapped[int | None] = mapped_column(Integer)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    billing_unit: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[float | None] = mapped_column(Numeric(14, 6))
    currency: Mapped[str | None] = mapped_column(String(16))
    cost_amount: Mapped[float | None] = mapped_column(Numeric(14, 4))
    quota_units: Mapped[int | None] = mapped_column(Integer)
    cost_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    run: Mapped[BusinessRun] = relationship()
    ability: Mapped[Ability | None] = relationship(foreign_keys=[ability_id])
