"""Agent/manifest/task models for ComfyUI server management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str | None] = mapped_column(String(64))
    host: Mapped[str | None] = mapped_column(String(128))
    base_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_manifest_version: Mapped[str | None] = mapped_column(String(64))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class AgentManifest(Base):
    __tablename__ = "agent_manifests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    download_url: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("agents.id", ondelete="CASCADE"))
    manifest_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_manifests.id", ondelete="SET NULL")
    )
    manifest_url: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    token_nonce: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class AgentTaskEvent(Base):
    __tablename__ = "agent_task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("agent_tasks.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentAlert(Base):
    __tablename__ = "agent_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("agents.id", ondelete="CASCADE"))
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
