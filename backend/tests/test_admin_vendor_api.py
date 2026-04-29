from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.admin_vendor as admin_vendor_module
import app.services.vendor_admin_client as vendor_admin_client_module
from app.core.db import Base
from app.deps.auth import require_admin
from app.main import app
from app.models.integration import Ability, ApiKey, VendorModelCatalog
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


def install_vendor_governance_db(monkeypatch):
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

    monkeypatch.setattr(admin_vendor_module, "get_session", fake_get_session)
    return fake_get_session


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


def test_vendor_usage_summary_degrades_when_vendor_service_rejects(monkeypatch) -> None:
    def raise_unauthorized(*, window_hours: int = 24):
        raise HTTPException(status_code=403, detail="INTERNAL_ONLY")

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "usage_summary", raise_unauthorized)

    response = client.get("/api/admin/vendor-api/usage/summary?windowHours=12")

    assert response.status_code == 200
    body = response.json()
    assert body["windowHours"] == 12
    assert body["items"] == []


def test_vendor_governance_summary_combines_keys_models_abilities_and_usage(monkeypatch) -> None:
    get_session = install_vendor_governance_db(monkeypatch)
    with get_session() as session:
        session.add_all(
            [
                VendorModelCatalog(
                    provider="openai",
                    model="gpt-image-2",
                    display_name="OpenAI · GPT Image 2",
                    status="active",
                    api_types=["image_generation", "image_edit"],
                    execution_modes=["sync_then_store"],
                    supports_mask=True,
                    supports_multiple_images=True,
                    supports_video=False,
                    supports_text=True,
                    requires_global_egress=True,
                    source="test",
                    route_policy={},
                    default_task_policy={},
                    input_schema={},
                    cost_policy={},
                    extra_metadata={},
                ),
                Ability(
                    id="openai_gpt_image_2_generate",
                    provider="openai",
                    category="image_generation",
                    capability_key="gpt_image_2_generate",
                    display_name="GPT Image 2 生图",
                    status="active",
                    ability_type="api",
                ),
                Ability(
                    id="baidu_quality_upgrade",
                    provider="baidu",
                    category="image_process",
                    capability_key="quality_upgrade",
                    display_name="百度清晰度提升",
                    status="active",
                    ability_type="api",
                ),
                ApiKey(
                    id="vkey_disabled",
                    provider="openai",
                    name="old",
                    key="sk-test-0000",
                    status="disabled",
                    usage_count=1,
                    extra_metadata={"maxConcurrency": 1},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ),
            ]
        )
        session.commit()

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
                    "envKeyConfigured": False,
                    "supportedChecks": ["models"],
                    "supportedApiTypes": ["image_generation", "image_edit"],
                    "executionModes": ["sync_then_store"],
                },
                {
                    "provider": "baidu",
                    "displayName": "百度图像处理",
                    "status": "active",
                    "requiresGlobalEgress": False,
                    "envKeyConfigured": True,
                    "supportedChecks": ["oauth"],
                    "supportedApiTypes": ["baidu_image_process"],
                    "executionModes": ["sync_then_store"],
                },
            ],
        }

    def fake_usage_summary(window_hours: int = 24):
        return {
            "baseUrl": "http://vendor.local",
            "windowHours": window_hours,
            "items": [
                {
                    "provider": "openai",
                    "model": "gpt-image-2",
                    "status": "failed",
                    "count": 2,
                    "errorCode": "VENDOR_API_KEY_MISSING",
                    "avgLatencyMs": 50,
                    "lastSeenAt": "2026-04-25T10:00:00+00:00",
                },
                {
                    "provider": "baidu",
                    "model": "quality_upgrade",
                    "status": "succeeded",
                    "count": 3,
                    "errorCode": None,
                    "avgLatencyMs": 1200,
                    "lastSeenAt": "2026-04-25T10:01:00+00:00",
                },
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)
    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "usage_summary", fake_usage_summary)

    response = client.get("/api/admin/vendor-api/governance/summary?windowHours=12")

    assert response.status_code == 200
    body = response.json()
    assert body["baseUrl"] == "http://vendor.local"
    assert body["windowHours"] == 12
    providers = {item["provider"]: item for item in body["providers"]}
    assert providers["openai"]["runtimeKeyConfigured"] is False
    assert providers["openai"]["disabledKeyCount"] == 1
    assert "VENDOR_API_KEY_MISSING" in providers["openai"]["issues"]
    assert "VENDOR_API_RECENT_FAILURES" in providers["openai"]["issues"]
    assert providers["baidu"]["runtimeKeyConfigured"] is True
    assert providers["baidu"]["activeAbilityCount"] == 1
    assert providers["baidu"]["succeededCalls"] == 3
    assert body["totals"]["providerCount"] >= 2
    assert body["totals"]["issueCount"] >= 2


def test_vendor_governance_summary_degrades_when_vendor_api_is_unavailable(monkeypatch) -> None:
    install_vendor_governance_db(monkeypatch)

    def raise_unavailable(*args, **kwargs):
        raise HTTPException(status_code=502, detail="VENDOR_API_EXECUTOR_UNAVAILABLE")

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", raise_unavailable)
    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_keys", raise_unavailable)
    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "usage_summary", raise_unavailable)

    response = client.get("/api/admin/vendor-api/governance/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["providers"] == []
    assert "VENDOR_PROVIDER_REGISTRY_UNAVAILABLE:VENDOR_API_EXECUTOR_UNAVAILABLE" in body["issues"]
    assert "VENDOR_USAGE_SUMMARY_UNAVAILABLE:VENDOR_API_EXECUTOR_UNAVAILABLE" in body["issues"]


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
