"""数据库会话与基础模型。"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, echo=False, future=True, pool_pre_ping=True)
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
