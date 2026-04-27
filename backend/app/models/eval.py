"""Models for AI ability evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class EvalWorkflowVersion(Base):
    """AI ability evaluation workflow version."""

    __tablename__ = "eval_workflow_version"
    __table_args__ = (
        UniqueConstraint("workflow_id", "category", name="uq_eval_workflow_version_workflow_category"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="v1")
    coze_base_url: Mapped[str | None] = mapped_column(String(512))
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    runs: Mapped[list["EvalRun"]] = relationship(back_populates="workflow_version")


class EvalDatasetItem(Base):
    """AI ability evaluation dataset item."""
    
    __tablename__ = "eval_dataset_item"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    oss_url: Mapped[str] = mapped_column(String(512), nullable=False)
    meta_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    runs: Mapped[list["EvalRun"]] = relationship(back_populates="dataset_item")


class EvalRun(Base):
    """AI ability evaluation run record."""
    
    __tablename__ = "eval_run"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_workflow_version.id", ondelete="SET NULL")
    )
    dataset_item_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("eval_dataset_item.id", ondelete="SET NULL")
    )
    input_oss_urls_json: Mapped[list[str] | None] = mapped_column(JSON)
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    coze_execute_id: Mapped[str | None] = mapped_column(String(64))
    coze_debug_url: Mapped[str | None] = mapped_column(String(512))
    podi_task_id: Mapped[str | None] = mapped_column(String(64))
    result_image_urls_json: Mapped[list[str] | None] = mapped_column(JSON)
    # For non-image workflows (e.g. image tagging), persist `output` as JSON so the eval UI can render it.
    result_output_json: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = mapped_column(
        JSON, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    workflow_version: Mapped[EvalWorkflowVersion | None] = relationship(back_populates="runs")
    dataset_item: Mapped[EvalDatasetItem | None] = relationship(back_populates="runs")
    annotations: Mapped[list["EvalAnnotation"]] = relationship(back_populates="run")


class EvalAnnotation(Base):
    """AI ability evaluation annotation."""
    
    __tablename__ = "eval_annotation"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    tags_json: Mapped[list[str] | None] = mapped_column(JSON)
    comment: Mapped[str | None] = mapped_column(Text)
    
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    run: Mapped[EvalRun] = relationship(back_populates="annotations")


class EvalBatchSession(Base):
    """Batch session for LoRA regression runs."""

    __tablename__ = "eval_batch_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("eval_workflow_version.id", ondelete="SET NULL")
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)

    planned_image_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repeat_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    planned_run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    uploaded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    upload_failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    running_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    canceled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    workflow_version: Mapped[EvalWorkflowVersion | None] = relationship()
    assets: Mapped[list["EvalBatchAsset"]] = relationship(
        back_populates="batch_session", cascade="all, delete-orphan"
    )
    run_items: Mapped[list["EvalBatchRunItem"]] = relationship(
        back_populates="batch_session", cascade="all, delete-orphan"
    )


class EvalBatchAsset(Base):
    """Uploaded source assets inside a batch session."""

    __tablename__ = "eval_batch_asset"
    __table_args__ = (
        UniqueConstraint("batch_session_id", "source_key", name="uq_eval_batch_asset_source"),
        Index("ix_eval_batch_asset_batch_upload_status", "batch_session_id", "upload_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_batch_session.id", ondelete="CASCADE"), nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(191), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    oss_url: Mapped[str | None] = mapped_column(String(1024))
    object_key: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    upload_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    upload_error_code: Mapped[str | None] = mapped_column(String(64))
    upload_error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    batch_session: Mapped[EvalBatchSession] = relationship(back_populates="assets")
    run_items: Mapped[list["EvalBatchRunItem"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class EvalBatchRunItem(Base):
    """Expanded execution item (asset x repeat index)."""

    __tablename__ = "eval_batch_run_item"
    __table_args__ = (
        UniqueConstraint(
            "batch_session_id",
            "asset_id",
            "repeat_index",
            name="uq_eval_batch_run_item_repeat",
        ),
        Index("ix_eval_batch_run_item_batch_status", "batch_session_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_batch_session.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_batch_asset.id", ondelete="CASCADE"), nullable=False
    )
    repeat_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    eval_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("eval_run.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    batch_session: Mapped[EvalBatchSession] = relationship(back_populates="run_items")
    asset: Mapped[EvalBatchAsset] = relationship(back_populates="run_items")
    eval_run: Mapped[EvalRun | None] = relationship()
    output_reviews: Mapped[list["EvalBatchOutputReview"]] = relationship(
        back_populates="run_item", cascade="all, delete-orphan"
    )


class EvalBatchOutputReview(Base):
    """Per-output review for LoRA batch comparison results."""

    __tablename__ = "eval_batch_output_review"
    __table_args__ = (
        UniqueConstraint("run_item_id", "output_index", name="uq_eval_batch_output_review_item_index"),
        Index("ix_eval_batch_output_review_batch", "batch_session_id"),
        Index("ix_eval_batch_output_review_eval_run_id", "eval_run_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_batch_session.id", ondelete="CASCADE"), nullable=False
    )
    run_item_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("eval_batch_run_item.id", ondelete="CASCADE"), nullable=False
    )
    eval_run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("eval_run.id", ondelete="SET NULL"), nullable=True
    )
    output_index: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    run_item: Mapped[EvalBatchRunItem] = relationship(back_populates="output_reviews")
