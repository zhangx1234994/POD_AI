from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.admin_vendor as admin_vendor_module
import app.services.vendor_admin_client as vendor_admin_client_module
from app.deps.auth import require_admin
from app.main import app
from app.models.integration import VendorModelCatalog
from app.services.auth_service import auth_service


client = TestClient(app)


def setup_module() -> None:
    app.dependency_overrides[require_admin] = auth_service.build_service_user


def teardown_module() -> None:
    app.dependency_overrides.pop(require_admin, None)


def install_vendor_catalog_db(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    VendorModelCatalog.__table__.create(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def fake_get_session():
        session = testing_session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(admin_vendor_module, "get_session", fake_get_session)


def test_admin_api_keys_do_not_return_plaintext_key() -> None:
    from app.models.integration import ApiKey
    from app.schemas.admin_integrations import ApiKeyRead

    row = ApiKey(
        id="key_1",
        provider="openai",
        name="OpenAI Test",
        key="sk-test-1234567890",
        status="active",
        usage_count=3,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    payload = ApiKeyRead.model_validate(row).model_dump()

    assert "key" not in payload
    assert payload["key_preview"] == "sk-t...7890"


def test_vendor_provider_proxy_adds_backend_base_url(monkeypatch) -> None:
    def fake_list_providers():
        return {
            "service": "vendor-api-ops",
            "baseUrl": "http://vendor.local",
            "providers": [
                {
                    "provider": "openai",
                    "displayName": "OpenAI",
                    "status": "active",
                    "requiresGlobalEgress": True,
                    "supportedChecks": ["models"],
                    "supportedApiTypes": ["image_generation", "image_edit"],
                    "executionModes": ["sync"],
                }
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    response = client.get("/api/admin/vendor-api/providers")

    assert response.status_code == 200
    body = response.json()
    assert body["baseUrl"] == "http://vendor.local"
    assert body["providers"][0]["provider"] == "openai"


def test_vendor_usage_summary_proxy(monkeypatch) -> None:
    def fake_usage_summary(window_hours: int = 24):
        return {
            "baseUrl": "http://vendor.local",
            "windowHours": window_hours,
            "items": [
                {
                    "provider": "openai",
                    "model": "gpt-image-2",
                    "status": "succeeded",
                    "count": 3,
                    "errorCode": None,
                    "avgLatencyMs": 1200,
                    "lastSeenAt": "2026-04-25T10:00:00+00:00",
                }
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "usage_summary", fake_usage_summary)

    response = client.get("/api/admin/vendor-api/usage/summary?windowHours=12")

    assert response.status_code == 200
    body = response.json()
    assert body["baseUrl"] == "http://vendor.local"
    assert body["windowHours"] == 12
    assert body["items"][0]["provider"] == "openai"
    assert body["items"][0]["count"] == 3


def test_vendor_models_include_openai_gpt_image_2(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)

    def fake_list_providers():
        return {
            "service": "vendor-api-ops",
            "baseUrl": "http://vendor.local",
            "providers": [
                {
                    "provider": "openai",
                    "displayName": "OpenAI",
                    "status": "active",
                    "requiresGlobalEgress": True,
                    "supportedChecks": ["models"],
                    "supportedApiTypes": ["image_generation", "image_edit"],
                    "executionModes": ["sync", "sync_then_store"],
                }
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    response = client.get("/api/admin/vendor-api/models")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["provider"] == "openai"
    assert item["model"] == "gpt-image-2"
    assert item["supportsMask"] is True
    assert item["requiresGlobalEgress"] is True


def test_vendor_model_catalog_can_create_and_update(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)

    def fake_list_providers():
        return {"service": "vendor-api-ops", "baseUrl": "http://vendor.local", "providers": []}

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    create_response = client.post(
        "/api/admin/vendor-api/models",
        json={
            "provider": "openai",
            "model": "gpt-image-2-edit",
            "displayName": "OpenAI · GPT Image 2 Edit",
            "status": "active",
            "apiTypes": ["image_edit"],
            "executionModes": ["sync_then_store"],
            "supportsMask": True,
            "supportsMultipleImages": True,
            "supportsVideo": False,
            "supportsText": True,
            "requiresGlobalEgress": True,
            "source": "backend-admin",
            "metadata": {"outputFormats": ["png"]},
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["metadata"]["outputFormats"] == ["png"]

    update_response = client.patch(
        f"/api/admin/vendor-api/models/{created['id']}",
        json={"status": "disabled", "supportsMask": False, "metadata": {"reason": "gray rollback"}},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "disabled"
    assert updated["supportsMask"] is False
    assert updated["metadata"]["reason"] == "gray rollback"


def test_sync_volcengine_models_upserts_catalog(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)
    monkeypatch.setattr(
        admin_vendor_module,
        "get_settings",
        lambda: SimpleNamespace(
            volcengine_api_key="volc-key",
            volcengine_base_url="https://ark.cn-beijing.volces.com",
            vendor_api_base_url="http://vendor.local",
        ),
    )

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "data": [
                    {"id": "doubao-seedream-4-5", "object": "model", "owned_by": "volcengine"},
                    {"id": "doubao-seedance-1-5-pro", "object": "model", "owned_by": "volcengine"},
                    {"bad": "missing-id"},
                ]
            }

    calls = {}

    def fake_get(url, headers, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(admin_vendor_module.httpx, "get", fake_get)

    response = client.post("/api/admin/vendor-api/models/sync/volcengine")

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 2
    assert body["skipped"] == 1
    assert calls["url"] == "https://ark.cn-beijing.volces.com/api/v3/models"
    assert calls["headers"]["Authorization"] == "Bearer volc-key"

    list_response = client.get("/api/admin/vendor-api/models")
    assert list_response.status_code == 200
    items = {item["model"]: item for item in list_response.json()["items"]}
    assert items["doubao-seedream-4-5"]["apiTypes"] == ["image_generation", "image_edit"]
    assert items["doubao-seedream-4-5"]["supportsMultipleImages"] is True
    assert items["doubao-seedance-1-5-pro"]["apiTypes"] == ["video_generation"]
    assert items["doubao-seedance-1-5-pro"]["supportsVideo"] is True


def test_sync_volcengine_models_requires_key(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)
    monkeypatch.setattr(
        admin_vendor_module,
        "get_settings",
        lambda: SimpleNamespace(
            volcengine_api_key=None,
            volcengine_base_url="https://ark.cn-beijing.volces.com",
            vendor_api_base_url="http://vendor.local",
        ),
    )

    response = client.post("/api/admin/vendor-api/models/sync/volcengine")

    assert response.status_code == 400
    assert response.json()["detail"] == "VOLCENGINE_API_KEY_MISSING"
