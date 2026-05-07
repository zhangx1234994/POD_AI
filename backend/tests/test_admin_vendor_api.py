from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
    assert providers["openai"]["supportedApiTypes"] == ["image_generation", "image_edit"]
    assert providers["openai"]["executionModes"] == ["sync_then_store"]
    assert "VENDOR_API_KEY_MISSING" in providers["openai"]["issues"]
    assert "VENDOR_MODEL_COST_POLICY_MISSING:1" in providers["openai"]["issues"]
    assert "VENDOR_API_RECENT_FAILURES" in providers["openai"]["issues"]
    assert providers["baidu"]["runtimeKeyConfigured"] is True
    assert providers["baidu"]["activeAbilityCount"] == 1
    assert providers["baidu"]["succeededCalls"] == 3
    assert "VENDOR_API_UNCOSTED_SUCCESS_CALLS" in providers["baidu"]["issues"]
    assert body["totals"]["providerCount"] >= 2
    assert body["totals"]["issueCount"] >= 2


def test_vendor_governance_summary_flags_quota_key_error_and_queue(monkeypatch) -> None:
    get_session = install_vendor_governance_db(monkeypatch)
    with get_session() as session:
        session.add_all(
            [
                VendorModelCatalog(
                    provider="openai",
                    model="gpt-image-2",
                    display_name="OpenAI · GPT Image 2",
                    status="active",
                    api_types=["image_edit"],
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
                    cost_policy={"billingUnit": "image", "unitPrice": 0.35, "currency": "CNY"},
                    extra_metadata={},
                ),
                Ability(
                    id="openai_image_edit",
                    provider="openai",
                    category="image_edit",
                    capability_key="gpt_image_2_edit",
                    display_name="GPT Image 2 图片编辑",
                    status="active",
                    ability_type="api",
                ),
                ApiKey(
                    id="vkey_openai_active",
                    provider="openai",
                    name="OpenAI 临时 Key",
                    key="sk-test-1111",
                    status="active",
                    daily_quota=100,
                    usage_count=85,
                    extra_metadata={"maxConcurrency": 2, "last_error": "VENDOR_API_RATE_LIMITED"},
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
                    "supportedApiTypes": ["image_edit"],
                    "executionModes": ["sync_then_store"],
                }
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
                    "status": "queued",
                    "count": 4,
                    "errorCode": None,
                    "avgLatencyMs": None,
                    "lastSeenAt": "2026-04-25T10:00:00+00:00",
                },
                {
                    "provider": "openai",
                    "model": "gpt-image-2",
                    "status": "running",
                    "count": 2,
                    "errorCode": None,
                    "avgLatencyMs": None,
                    "lastSeenAt": "2026-04-25T10:01:00+00:00",
                },
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)
    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "usage_summary", fake_usage_summary)

    response = client.get("/api/admin/vendor-api/governance/summary?windowHours=6")

    assert response.status_code == 200
    provider = response.json()["providers"][0]
    assert provider["runtimeKeyConfigured"] is True
    assert provider["queuedCalls"] == 4
    assert provider["runningCalls"] == 2
    assert provider["failedCalls"] == 0
    assert provider["uncheckedKeyCount"] == 1
    assert "VENDOR_API_KEY_QUOTA_NEAR_LIMIT:1" in provider["issues"]
    assert "VENDOR_API_KEY_RECENT_ERROR:1" in provider["issues"]
    assert "VENDOR_API_KEY_NEVER_CHECKED:1" in provider["issues"]
    assert "VENDOR_API_TASKS_QUEUED:4" in provider["issues"]
    assert "VENDOR_API_TASKS_RUNNING_LONG:2" in provider["issues"]


def test_vendor_governance_summary_flags_stale_and_failed_key_checks(monkeypatch) -> None:
    get_session = install_vendor_governance_db(monkeypatch)
    old_checked_at = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
    with get_session() as session:
        session.add_all(
            [
                VendorModelCatalog(
                    provider="openai",
                    model="gpt-image-2",
                    display_name="OpenAI · GPT Image 2",
                    status="active",
                    api_types=["image_edit"],
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
                    cost_policy={"billingUnit": "image", "unitPrice": 0.35, "currency": "CNY"},
                    extra_metadata={},
                ),
                ApiKey(
                    id="vkey_openai_failed_check",
                    provider="openai",
                    name="OpenAI Failed Check",
                    key="sk-test-2222",
                    status="active",
                    usage_count=1,
                    extra_metadata={
                        "maxConcurrency": 2,
                        "lastCheck": {
                            "success": False,
                            "errorCode": "VENDOR_API_AUTH_FAILED",
                            "checkedAt": old_checked_at,
                        },
                    },
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
                    "supportedApiTypes": ["image_edit"],
                    "executionModes": ["sync_then_store"],
                }
            ],
        }

    def fake_usage_summary(window_hours: int = 24):
        return {"baseUrl": "http://vendor.local", "windowHours": window_hours, "items": []}

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)
    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "usage_summary", fake_usage_summary)

    response = client.get("/api/admin/vendor-api/governance/summary?windowHours=6")

    assert response.status_code == 200
    provider = response.json()["providers"][0]
    assert provider["failedKeyCheckCount"] == 1
    assert provider["staleKeyCheckCount"] == 1
    assert "VENDOR_API_KEY_CHECK_FAILED:1" in provider["issues"]
    assert "VENDOR_API_KEY_CHECK_STALE:1" in provider["issues"]


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
    assert item["releaseGate"]["acceptancePassed"] is False
    assert "VENDOR_MODEL_ACCEPTANCE_REQUIRED" in item["releaseGate"]["blockers"]


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
            "costPolicy": {
                "currency": "cny",
                "billing_unit": "image",
                "unit_price": 0.35,
                "quota_units": 2,
                "pricing_version": "v1",
            },
            "metadata": {"outputFormats": ["png"]},
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["metadata"]["outputFormats"] == ["png"]
    assert created["costPolicy"]["currency"] == "CNY"
    assert created["costPolicy"]["billingUnit"] == "image"
    assert created["costPolicy"]["unitPrice"] == 0.35
    assert created["costPolicy"]["quotaUnits"] == 2
    assert created["releaseGate"]["primaryIssue"] == "VENDOR_MODEL_RUNTIME_KEY_MISSING"
    assert created["releaseGate"]["primaryActionLabel"] == "补密钥"

    update_response = client.patch(
        f"/api/admin/vendor-api/models/{created['id']}",
        json={"status": "disabled", "supportsMask": False, "metadata": {"reason": "gray rollback"}},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["status"] == "disabled"
    assert updated["supportsMask"] is False
    assert updated["metadata"]["reason"] == "gray rollback"

    invalid_response = client.patch(
        f"/api/admin/vendor-api/models/{created['id']}",
        json={"costPolicy": {"billingUnit": "image", "unitPrice": -1}},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["detail"] == "VENDOR_MODEL_COST_POLICY_INVALID"


def test_vendor_model_save_response_uses_runtime_key_context(monkeypatch) -> None:
    fake_get_session = install_vendor_governance_db(monkeypatch)
    checked_at = datetime.now(timezone.utc).isoformat()

    with fake_get_session() as session:
        session.add(
            ApiKey(
                id="vkey_openai_ready",
                provider="openai",
                name="OpenAI Ready Key",
                key="sk-test-ready",
                status="active",
                daily_quota=100,
                usage_count=1,
                extra_metadata={
                    "maxConcurrency": 2,
                    "lastCheck": {"success": True, "checkedAt": checked_at},
                },
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
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
                    "envKeyConfigured": False,
                    "supportedApiTypes": ["image_generation"],
                    "executionModes": ["sync_then_store"],
                }
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    create_response = client.post(
        "/api/admin/vendor-api/models",
        json={
            "provider": "openai",
            "model": "gpt-image-2-ready",
            "displayName": "OpenAI · GPT Image 2 Ready",
            "status": "active",
            "apiTypes": ["image_generation"],
            "executionModes": ["sync_then_store"],
            "supportsText": True,
            "requiresGlobalEgress": True,
            "costPolicy": {"currency": "CNY", "billingUnit": "image", "unitPrice": 0.35},
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["releaseGate"]["runtimeKeyConfigured"] is True
    assert created["releaseGate"]["egressVerified"] is True
    assert "VENDOR_MODEL_RUNTIME_KEY_MISSING" not in created["releaseGate"]["blockers"]
    assert "VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED" not in created["releaseGate"]["warnings"]
    assert created["releaseGate"]["primaryIssue"] == "VENDOR_MODEL_ACCEPTANCE_REQUIRED"
    assert created["releaseGate"]["primaryActionLabel"] == "跑验收"

    update_response = client.patch(
        f"/api/admin/vendor-api/models/{created['id']}",
        json={"displayName": "OpenAI · GPT Image 2 Ready Updated"},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["releaseGate"]["runtimeKeyConfigured"] is True
    assert updated["releaseGate"]["egressVerified"] is True
    assert "VENDOR_MODEL_RUNTIME_KEY_MISSING" not in updated["releaseGate"]["blockers"]
    assert "VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED" not in updated["releaseGate"]["warnings"]


def test_vendor_model_release_gate_requires_recent_egress_check_for_global_model(monkeypatch) -> None:
    fake_get_session = install_vendor_governance_db(monkeypatch)

    with fake_get_session() as session:
        session.add(
            ApiKey(
                id="vkey_openai_unchecked",
                provider="openai",
                name="OpenAI Unchecked Key",
                key="sk-test-unchecked",
                status="active",
                daily_quota=100,
                usage_count=1,
                extra_metadata={"maxConcurrency": 2},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
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
                    "envKeyConfigured": False,
                    "supportedApiTypes": ["image_generation"],
                    "executionModes": ["sync_then_store"],
                }
            ],
        }

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    response = client.post(
        "/api/admin/vendor-api/models",
        json={
            "provider": "openai",
            "model": "gpt-image-2-unchecked",
            "displayName": "OpenAI · GPT Image 2 Unchecked",
            "status": "active",
            "apiTypes": ["image_generation"],
            "executionModes": ["sync_then_store"],
            "supportsText": True,
            "requiresGlobalEgress": True,
            "costPolicy": {"currency": "CNY", "billingUnit": "image", "unitPrice": 0.35},
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["releaseGate"]["runtimeKeyConfigured"] is True
    assert created["releaseGate"]["egressVerified"] is False
    assert "VENDOR_MODEL_GLOBAL_EGRESS_REQUIRED" in created["releaseGate"]["warnings"]
    assert "带密钥出网验证" in " ".join(created["releaseGate"]["suggestions"])
    assert created["releaseGate"]["primaryIssue"] == "VENDOR_MODEL_KEY_NEVER_CHECKED"
    assert created["releaseGate"]["primaryActionLabel"] == "验密钥"


def test_vendor_model_acceptance_record_updates_release_gate(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)

    def fake_list_providers():
        return {"service": "vendor-api-ops", "baseUrl": "http://vendor.local", "providers": []}

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    create_response = client.post(
        "/api/admin/vendor-api/models",
        json={
            "provider": "openai",
            "model": "gpt-image-2",
            "displayName": "OpenAI · GPT Image 2",
            "status": "active",
            "apiTypes": ["image_generation", "image_edit"],
            "executionModes": ["sync_then_store"],
            "supportsMask": True,
            "supportsMultipleImages": True,
            "supportsText": True,
            "requiresGlobalEgress": True,
            "source": "backend-admin",
            "costPolicy": {"currency": "CNY", "billingUnit": "image", "unitPrice": 0.35},
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["latestAcceptance"] is None
    assert "VENDOR_MODEL_ACCEPTANCE_REQUIRED" in created["releaseGate"]["blockers"]

    acceptance_response = client.post(
        f"/api/admin/vendor-api/models/{created['id']}/acceptance-records",
        json={
            "status": "passed",
            "note": "能力测试已跑通，OSS 回填正常",
            "evidenceRunId": "run_vendor_test",
            "evidenceUrl": "https://example.com/evidence",
        },
    )

    assert acceptance_response.status_code == 200
    accepted = acceptance_response.json()
    assert accepted["latestAcceptance"]["status"] == "passed"
    assert accepted["latestAcceptance"]["evidenceRunId"] == "run_vendor_test"
    assert accepted["acceptanceRecords"][0]["note"] == "能力测试已跑通，OSS 回填正常"
    assert accepted["releaseGate"]["acceptancePassed"] is True
    assert "VENDOR_MODEL_ACCEPTANCE_REQUIRED" not in accepted["releaseGate"]["blockers"]
    assert accepted["releaseGate"]["primaryIssue"] == "VENDOR_MODEL_RUNTIME_KEY_MISSING"
    assert accepted["releaseGate"]["primaryActionLabel"] == "补密钥"

    invalid_response = client.post(
        f"/api/admin/vendor-api/models/{created['id']}/acceptance-records",
        json={"status": "unknown"},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["detail"] == "VENDOR_MODEL_ACCEPTANCE_STATUS_INVALID"


def test_vendor_model_update_preserves_acceptance_and_adds_audit(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)

    def fake_list_providers():
        return {"service": "vendor-api-ops", "baseUrl": "http://vendor.local", "providers": []}

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    create_response = client.post(
        "/api/admin/vendor-api/models",
        json={
            "provider": "openai",
            "model": "gpt-image-2-audit",
            "displayName": "OpenAI · GPT Image 2 Audit",
            "status": "active",
            "apiTypes": ["image_generation"],
            "executionModes": ["sync_then_store"],
            "supportsText": True,
            "requiresGlobalEgress": True,
            "metadata": {"owner": "ai-team"},
            "costPolicy": {"currency": "CNY", "billingUnit": "image", "unitPrice": 0.35},
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    acceptance_response = client.post(
        f"/api/admin/vendor-api/models/{created['id']}/acceptance-records",
        json={"status": "passed", "note": "首轮验收通过"},
    )
    assert acceptance_response.status_code == 200

    update_response = client.patch(
        f"/api/admin/vendor-api/models/{created['id']}",
        json={"metadata": {"owner": "ops-team"}},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["metadata"]["owner"] == "ops-team"
    assert updated["latestAcceptance"]["status"] == "passed"
    assert updated["acceptanceRecords"][0]["note"] == "首轮验收通过"
    assert updated["auditRecords"][0]["action"] == "update"


def test_vendor_model_bulk_action_updates_models_and_records_audit(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)

    def fake_list_providers():
        return {"service": "vendor-api-ops", "baseUrl": "http://vendor.local", "providers": []}

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    created_ids: list[int] = []
    for suffix in ("a", "b"):
        response = client.post(
            "/api/admin/vendor-api/models",
            json={
                "provider": "openai",
                "model": f"gpt-image-2-bulk-{suffix}",
                "displayName": f"OpenAI · Bulk {suffix}",
                "status": "active",
                "apiTypes": ["image_generation"],
                "executionModes": ["sync_then_store"],
                "supportsText": True,
                "requiresGlobalEgress": True,
            },
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    response = client.post(
        "/api/admin/vendor-api/models/bulk-action",
        json={
            "modelIds": [created_ids[0], created_ids[1], created_ids[1], 99999],
            "action": "disable",
            "note": "供应商余额异常，批量停用",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["updated"] == 2
    assert body["failed"] == 1
    success_items = [item for item in body["items"] if item["success"]]
    assert {item["model"]["status"] for item in success_items} == {"disabled"}
    assert all(item["model"]["auditRecords"][0]["action"] == "disable" for item in success_items)
    assert all(item["model"]["releaseGate"]["primaryIssue"] == "VENDOR_MODEL_INACTIVE" for item in success_items)
    failed_items = [item for item in body["items"] if not item["success"]]
    assert failed_items[0]["error"] == "VENDOR_MODEL_NOT_FOUND"


def test_vendor_model_bulk_action_can_record_acceptance_and_apply_cost(monkeypatch) -> None:
    install_vendor_catalog_db(monkeypatch)

    def fake_list_providers():
        return {"service": "vendor-api-ops", "baseUrl": "http://vendor.local", "providers": []}

    monkeypatch.setattr(vendor_admin_client_module.vendor_admin_client, "list_providers", fake_list_providers)

    create_response = client.post(
        "/api/admin/vendor-api/models",
        json={
            "provider": "openai",
            "model": "gpt-image-2-bulk-cost",
            "displayName": "OpenAI · Bulk Cost",
            "status": "active",
            "apiTypes": ["image_generation"],
            "executionModes": ["sync_then_store"],
            "supportsText": True,
            "requiresGlobalEgress": True,
        },
    )
    assert create_response.status_code == 201
    model_id = create_response.json()["id"]

    acceptance_response = client.post(
        "/api/admin/vendor-api/models/bulk-action",
        json={
            "modelIds": [model_id],
            "action": "record_acceptance",
            "acceptance": {"status": "passed", "note": "批量验收通过"},
        },
    )
    assert acceptance_response.status_code == 200
    accepted = acceptance_response.json()["items"][0]["model"]
    assert accepted["latestAcceptance"]["status"] == "passed"
    assert accepted["auditRecords"][0]["action"] == "record_acceptance"

    cost_response = client.post(
        "/api/admin/vendor-api/models/bulk-action",
        json={
            "modelIds": [model_id],
            "action": "apply_cost_policy",
            "costPolicy": {"currency": "cny", "billing_unit": "image", "unit_price": 0.42},
        },
    )
    assert cost_response.status_code == 200
    priced = cost_response.json()["items"][0]["model"]
    assert priced["costPolicy"]["currency"] == "CNY"
    assert priced["costPolicy"]["unitPrice"] == 0.42
    assert priced["auditRecords"][0]["action"] == "apply_cost_policy"
    assert priced["latestAcceptance"]["status"] == "passed"

    invalid_response = client.post(
        "/api/admin/vendor-api/models/bulk-action",
        json={"modelIds": [model_id], "action": "apply_cost_policy", "costPolicy": {"unitPrice": -1}},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["detail"] == "VENDOR_MODEL_COST_POLICY_INVALID"


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
