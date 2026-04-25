"""User and auth models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRole(str, Enum):  # type: ignore[misc]
    USER = "user"
    ADMIN = "admin"
    CLIENT = "client"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    refresh_jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    created_by: Mapped[str | None] = mapped_column(String(64), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
