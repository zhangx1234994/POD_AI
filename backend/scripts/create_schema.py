"""
Simple helper to create database tables using SQLAlchemy metadata.

Usage:
    cd backend
    source .venv/bin/activate
    DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/podi python scripts/create_schema.py
"""

from app.core.db import Base, engine  # pylint: disable=unused-import
from app.models import task  # noqa: F401
from app.models import integration  # noqa: F401


def main() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
