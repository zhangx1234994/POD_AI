"""Task domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TaskBatch(Base):
    __tablename__ = "task_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool_action: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="batch")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_batch", "batch_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("task_batches.id", ondelete="SET NULL")
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wallet_hold_id: Mapped[str | None] = mapped_column(String(64))
    points_cost: Mapped[int | None] = mapped_column(Integer)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    notify_cursor: Mapped[str | None] = mapped_column(String(64))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    batch: Mapped[TaskBatch | None] = relationship(back_populates="tasks")
    assets: Mapped[list["TaskAsset"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskAsset(Base):
    __tablename__ = "task_assets"
    __table_args__ = (
        Index("ix_task_assets_task_type", "task_id", "asset_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)  # input/output/preview
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024))
    file_name: Mapped[str | None] = mapped_column(String(256))
    mime_type: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(128))
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    task: Mapped[Task] = relationship(back_populates="assets")


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    task: Mapped[Task] = relationship(back_populates="events")
