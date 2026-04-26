from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.ability_logs as ability_logs_module
from app.core.db import Base
from app.models.integration import Ability
from app.services.ability_logs import AbilityLogService


def install_log_db(monkeypatch):
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

    monkeypatch.setattr(ability_logs_module, "get_session", fake_get_session)
    with testing_session() as session:
        session.add(
            Ability(
                id="ability_health_test",
                provider="openai",
                category="image_generation",
                capability_key="gpt_image_2_generate",
                display_name="GPT Image 2",
                status="active",
                ability_type="api",
            )
        )
        session.commit()
    return testing_session


def test_extract_stored_url_from_images_when_assets_missing():
    svc = AbilityLogService()
    payload = {
        "images": [
            {"ossUrl": "https://oss.example.com/a.png"},
            {"sourceUrl": "https://raw.example.com/b.png"},
        ]
    }
    assert svc._extract_stored_url(payload) == "https://oss.example.com/a.png"


def test_extract_stored_url_from_image_urls_when_no_object_assets():
    svc = AbilityLogService()
    payload = {"imageUrls": ["https://oss.example.com/a.png", "https://oss.example.com/b.png"]}
    assert svc._extract_stored_url(payload) == "https://oss.example.com/a.png"


def test_extract_assets_fallback_from_images_and_result_urls():
    svc = AbilityLogService()
    from_images = svc._extract_assets({"images": [{"ossUrl": "https://oss.example.com/a.png", "tag": "comfyui"}]})
    assert isinstance(from_images, list) and from_images[0]["ossUrl"] == "https://oss.example.com/a.png"
    from_urls = svc._extract_assets({"resultUrls": ["https://oss.example.com/c.png"]})
    assert isinstance(from_urls, list) and from_urls[0]["url"] == "https://oss.example.com/c.png"


def test_finish_log_updates_ability_health_summary(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    log_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            ability_id="ability_health_test",
            provider="openai",
            capability_key="gpt_image_2_generate",
        )
    )
    svc.finish_success(log_id, response_payload={"imageUrls": ["https://oss.example.com/a.png"]}, duration_ms=100)

    with testing_session() as session:
        ability = session.get(Ability, "ability_health_test")
        assert ability is not None
        assert ability.last_health_status == "healthy"
        assert ability.last_health_check_at is not None
        assert ability.success_rate == 1.0


def test_latest_failed_log_marks_ability_degraded_when_recent_rate_ok(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    for _ in range(4):
        log_id = svc.start_log(
            ability_logs_module.AbilityLogStartParams(
                ability_id="ability_health_test",
                provider="openai",
                capability_key="gpt_image_2_generate",
            )
        )
        svc.finish_success(log_id, response_payload={"ok": True}, duration_ms=100)
    failed_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            ability_id="ability_health_test",
            provider="openai",
            capability_key="gpt_image_2_generate",
        )
    )
    svc.finish_failure(failed_id, error_message="upstream timeout", response_payload={"error": "timeout"}, duration_ms=100)

    with testing_session() as session:
        ability = session.get(Ability, "ability_health_test")
        assert ability is not None
        assert ability.last_health_status == "degraded"
        assert ability.last_health_check_at is not None
        assert ability.success_rate == 0.8


def test_failed_log_clears_estimated_cost(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    log_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            ability_id="ability_health_test",
            provider="openai",
            capability_key="gpt_image_2_generate",
            billing_unit="per_image",
            unit_price=0.08,
            currency="USD",
            cost_amount=0.08,
        )
    )
    svc.finish_failure(log_id, error_message="upstream rejected", response_payload={"status": "failed"}, duration_ms=100)

    with testing_session() as session:
        log = session.get(ability_logs_module.AbilityInvocationLog, log_id)
        assert log is not None
        assert log.status == "failed"
        assert log.unit_price == Decimal("0.0800")
        assert log.cost_amount is None


def test_refresh_health_summaries_marks_untested_active_abilities(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    with testing_session() as session:
        session.add(
            Ability(
                id="ability_needs_test",
                provider="kie",
                category="image_generation",
                capability_key="new_model",
                display_name="New Model",
                status="active",
                ability_type="api",
            )
        )
        session.commit()

    log_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            ability_id="ability_health_test",
            provider="openai",
            capability_key="gpt_image_2_generate",
        )
    )
    svc.finish_success(log_id, response_payload={"ok": True}, duration_ms=100)

    summary = svc.refresh_health_summaries(stale_hours=24, limit=10)

    assert summary["total"] == 2
    assert summary["healthy"] == 1
    assert summary["unknown"] == 1
    assert summary["needsTestCount"] == 1
    needs_test = [item for item in summary["items"] if item["abilityId"] == "ability_needs_test"][0]
    assert needs_test["healthStatus"] == "unknown"
    assert needs_test["stale"] is True
    assert needs_test["needsTest"] is True


def test_refresh_health_summaries_marks_old_checks_stale(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    with testing_session() as session:
        ability = session.get(Ability, "ability_health_test")
        assert ability is not None
        ability.last_health_status = "healthy"
        ability.success_rate = 1.0
        ability.last_health_check_at = datetime.utcnow() - timedelta(hours=48)
        session.add(ability)
        session.commit()

    summary = svc.refresh_health_summaries(stale_hours=24, limit=10)

    assert summary["staleCount"] == 1
    item = summary["items"][0]
    assert item["abilityId"] == "ability_health_test"
    assert item["healthStatus"] == "healthy"
    assert item["stale"] is True
    assert item["needsTest"] is True


def test_refresh_health_summaries_filters_export_items(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    with testing_session() as session:
        session.add(
            Ability(
                id="ability_needs_test",
                provider="kie",
                category="image_generation",
                capability_key="new_model",
                display_name="New Model",
                status="active",
                ability_type="api",
            )
        )
        session.commit()

    log_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            ability_id="ability_health_test",
            provider="openai",
            capability_key="gpt_image_2_generate",
        )
    )
    svc.finish_success(log_id, response_payload={"ok": True}, duration_ms=100)

    needs_test_summary = svc.refresh_health_summaries(needs_test=True, stale_hours=24, limit=10)
    assert [item["abilityId"] for item in needs_test_summary["items"]] == ["ability_needs_test"]

    healthy_summary = svc.refresh_health_summaries(health_status="healthy", stale_hours=24, limit=10)
    assert [item["abilityId"] for item in healthy_summary["items"]] == ["ability_health_test"]
