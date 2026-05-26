"""数据库会话与基础模型。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()


def _engine_options_from_settings(config: Any) -> dict[str, Any]:
    options: dict[str, Any] = {
        "echo": False,
        "future": True,
        "pool_pre_ping": True,
    }
    url = make_url(config.database_url)
    if url.get_backend_name() == "sqlite" and (url.database in {None, "", ":memory:"}):
        return options
    options.update(
        {
            "pool_size": max(1, int(getattr(config, "database_pool_size", 20) or 20)),
            "max_overflow": max(0, int(getattr(config, "database_max_overflow", 20) or 20)),
            "pool_timeout": max(1, int(getattr(config, "database_pool_timeout", 30) or 30)),
            "pool_recycle": max(60, int(getattr(config, "database_pool_recycle", 1800) or 1800)),
        }
    )
    return options


engine = create_engine(settings.database_url, **_engine_options_from_settings(settings))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative Base."""


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Session:
    """FastAPI dependency that yields a SQLAlchemy session.

    Note: `get_session()` is a contextmanager used by services/scripts; FastAPI
    needs a generator dependency that yields the Session instance directly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
