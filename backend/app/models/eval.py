"""Models for AI ability evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class EvalWorkflowVersion(Base):
    """AI ability evaluation workflow version."""
    
    __tablename__ = "eval_workflow_version"
    
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
