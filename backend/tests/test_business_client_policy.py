from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.business_runs as business_runs_module
from app.core.db import Base
from app.models.integration import BusinessRun
from app.models.user import User as _User  # noqa: F401 - registers the users table for SQLAlchemy metadata.
from app.schemas.business import BusinessClientCreateRequest, BusinessClientUpdateRequest, BusinessRunCreateRequest
from app.services.business_runs import BusinessRunService


os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")


def _install_business_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(business_runs_module, "get_session", fake_get_session)
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    return testing_session


def test_business_client_admin_crud(monkeypatch) -> None:
    _install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_client(
        BusinessClientCreateRequest(
            tenantId="tenant-a",
            clientId="coze-main",
            displayName="业务方 A",
            allowedBusinessKeys=["fission", "outpaint", "fission"],
            dailyRunLimit=20,
            concurrentRunLimit=3,
        )
    )

    assert created["tenant_id"] == "tenant-a"
    assert created["client_id"] == "coze-main"
    assert created["allowed_business_keys"] == ["fission", "outpaint"]

    listed = service.list_clients(tenant_id="tenant-a")
    assert [item["id"] for item in listed] == [created["id"]]

    updated = service.update_client(
        created["id"],
        BusinessClientUpdateRequest(status="disabled", dailyQuotaUnits=100),
    )
    assert updated["status"] == "disabled"
    assert updated["daily_quota_units"] == 100


def test_business_client_policy_blocks_disabled_client(monkeypatch) -> None:
    _install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_client(
        BusinessClientCreateRequest(
            tenantId="tenant-a",
            clientId="coze-main",
            displayName="业务方 A",
            status="disabled",
            allowedBusinessKeys=["fission"],
        )
    )

    with pytest.raises(HTTPException) as exc:
        service.create_run(
            business_key="fission",
            payload=BusinessRunCreateRequest(
                imageUrl="https://example.com/a.png",
                tenantId="tenant-a",
                clientId="coze-main",
            ),
            user=None,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "BUSINESS_CLIENT_DISABLED"


def test_business_client_policy_blocks_daily_run_limit(monkeypatch) -> None:
    testing_session = _install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_client(
        BusinessClientCreateRequest(
            tenantId="tenant-a",
            clientId="coze-main",
            displayName="业务方 A",
            allowedBusinessKeys=["fission"],
            dailyRunLimit=1,
        )
    )
    with testing_session() as session:
        session.add(
            BusinessRun(
                id="existing_run",
                business_key="fission",
                status="succeeded",
                source="business-api",
                tenant_id="tenant-a",
                client_id="coze-main",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        session.commit()

    with pytest.raises(HTTPException) as exc:
        service.create_run(
            business_key="fission",
            payload=BusinessRunCreateRequest(
                imageUrl="https://example.com/a.png",
                tenantId="tenant-a",
                clientId="coze-main",
            ),
            user=None,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail == "BUSINESS_CLIENT_DAILY_RUN_LIMITED"


def test_business_client_policy_blocks_disallowed_business_key(monkeypatch) -> None:
    _install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_client(
        BusinessClientCreateRequest(
            tenantId="tenant-a",
            clientId="coze-main",
            displayName="业务方 A",
            allowedBusinessKeys=["outpaint"],
        )
    )

    with pytest.raises(HTTPException) as exc:
        service.create_run(
            business_key="fission",
            payload=BusinessRunCreateRequest(
                imageUrl="https://example.com/a.png",
                tenantId="tenant-a",
                clientId="coze-main",
            ),
            user=None,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "BUSINESS_CLIENT_BUSINESS_NOT_ALLOWED"


def test_business_client_policy_falls_back_to_tenant_config(monkeypatch) -> None:
    testing_session = _install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_client(
        BusinessClientCreateRequest(
            tenantId="tenant-a",
            displayName="业务方 A 默认策略",
            allowedBusinessKeys=["fission"],
            concurrentRunLimit=1,
        )
    )
    with testing_session() as session:
        session.add(
            BusinessRun(
                id="existing_running",
                business_key="fission",
                status="running",
                source="business-api",
                tenant_id="tenant-a",
                client_id="any-client",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        session.commit()

    with pytest.raises(HTTPException) as exc:
        service.create_run(
            business_key="fission",
            payload=BusinessRunCreateRequest(
                imageUrl="https://example.com/a.png",
                tenantId="tenant-a",
                clientId="new-client",
            ),
            user=None,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail == "BUSINESS_CLIENT_CONCURRENCY_LIMITED"
