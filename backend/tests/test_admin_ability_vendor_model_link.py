from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.admin_abilities as admin_abilities_module
from app.core.db import Base
from app.deps.auth import require_admin
from app.main import app
from app.models.integration import VendorModelCatalog
from app.services.auth_service import auth_service


client = TestClient(app)


def setup_module() -> None:
    app.dependency_overrides[require_admin] = auth_service.build_service_user


def teardown_module() -> None:
    app.dependency_overrides.pop(require_admin, None)


def install_ability_db(monkeypatch) -> int:
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

    monkeypatch.setattr(admin_abilities_module, "get_session", fake_get_session)
    with testing_session() as session:
        item = VendorModelCatalog(
            provider="openai",
            model="gpt-image-2",
            display_name="OpenAI GPT Image 2",
            status="active",
            api_types=["image_generation", "image_edit"],
            execution_modes=["sync_then_store"],
            supports_mask=True,
            supports_multiple_images=True,
            supports_text=True,
            requires_global_egress=True,
            source="backend-test",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return int(item.id)


def test_admin_ability_can_bind_vendor_model(monkeypatch) -> None:
    vendor_model_id = install_ability_db(monkeypatch)

    response = client.post(
        "/api/admin/abilities",
        json={
            "id": "ability_openai_image_test",
            "provider": "openai",
            "category": "image_generation",
            "capability_key": "gpt_image_2_generate",
            "version": "v1",
            "display_name": "GPT Image 2 生成",
            "status": "active",
            "ability_type": "api",
            "vendor_model_id": vendor_model_id,
            "default_params": {"model": "gpt-image-2"},
            "input_schema": {"fields": []},
            "metadata": {"api_type": "image_generation"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vendor_model_id"] == vendor_model_id


def test_admin_ability_rejects_missing_vendor_model(monkeypatch) -> None:
    install_ability_db(monkeypatch)

    response = client.post(
        "/api/admin/abilities",
        json={
            "id": "ability_missing_model_test",
            "provider": "openai",
            "category": "image_generation",
            "capability_key": "gpt_image_2_missing_model",
            "display_name": "缺失模型测试",
            "status": "active",
            "vendor_model_id": 9999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "VENDOR_MODEL_NOT_FOUND"


def test_admin_ability_health_summary_endpoint(monkeypatch) -> None:
    def fake_refresh_health_summaries(*, stale_hours: int = 24, limit: int = 20, **_kwargs):
        return {
            "generatedAt": "2026-04-25T10:00:00Z",
            "staleHours": stale_hours,
            "total": 1,
            "healthy": 0,
            "degraded": 0,
            "failed": 0,
            "unknown": 1,
            "staleCount": 1,
            "needsTestCount": 1,
            "items": [
                {
                    "abilityId": "ability_test",
                    "displayName": "测试能力",
                    "provider": "openai",
                    "capabilityKey": "gpt_image_2",
                    "status": "active",
                    "healthStatus": "unknown",
                    "lastHealthCheckAt": None,
                    "successRate": None,
                    "finishedLogCount": 0,
                    "latestLogStatus": None,
                    "latestLogAt": None,
                    "stale": True,
                    "needsTest": True,
                }
            ],
        }

    monkeypatch.setattr(admin_abilities_module.ability_log_service, "refresh_health_summaries", fake_refresh_health_summaries)

    response = client.get("/api/admin/abilities/health/summary?staleHours=12&limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["staleHours"] == 12
    assert body["needsTestCount"] == 1
    assert body["items"][0]["abilityId"] == "ability_test"


def test_admin_ability_health_export_endpoint(monkeypatch) -> None:
    def fake_refresh_health_summaries(*, stale_hours: int = 24, limit: int = 20, **kwargs):
        assert stale_hours == 24
        assert kwargs["needs_test"] is True
        return {
            "generatedAt": "2026-04-25T10:00:00Z",
            "staleHours": stale_hours,
            "total": 1,
            "healthy": 0,
            "degraded": 0,
            "failed": 0,
            "unknown": 1,
            "staleCount": 1,
            "needsTestCount": 1,
            "items": [
                {
                    "abilityId": "ability_test",
                    "displayName": "测试能力",
                    "provider": "openai",
                    "capabilityKey": "gpt_image_2",
                    "status": "active",
                    "healthStatus": "unknown",
                    "lastHealthCheckAt": None,
                    "successRate": None,
                    "finishedLogCount": 0,
                    "latestLogStatus": None,
                    "latestLogAt": None,
                    "stale": True,
                    "needsTest": True,
                }
            ],
        }

    monkeypatch.setattr(admin_abilities_module.ability_log_service, "refresh_health_summaries", fake_refresh_health_summaries)

    response = client.get("/api/admin/abilities/health/export?needsTest=true")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "ability_test" in response.text
    assert "测试能力" in response.text
