from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.ability_logs as ability_logs_module
from app.core.db import Base
from app.models.integration import Ability, AbilityInvocationLog
from app.schemas.admin_ability_logs import AbilityInvocationLogRead
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
    assert from_images[0]["type"] == "image"
    from_urls = svc._extract_assets({"resultUrls": ["https://oss.example.com/c.png"]})
    assert isinstance(from_urls, list) and from_urls[0]["url"] == "https://oss.example.com/c.png"


def test_extract_assets_preserves_video_output_type():
    svc = AbilityLogService()
    assets = svc._extract_assets({"videoUrls": ["https://oss.example.com/output.mp4"]})
    assert isinstance(assets, list)
    assert assets[0]["url"] == "https://oss.example.com/output.mp4"
    assert assets[0]["type"] == "video"


def test_log_read_outputs_summary_for_image_video_and_text():
    log = AbilityInvocationLog(
        id=1,
        ability_provider="openai",
        capability_key="mixed_output",
        source="ability-api",
        status="success",
        stored_url=None,
        response_payload={
            "imageUrls": ["https://oss.example.com/a.png"],
            "videoUrls": ["https://oss.example.com/b.mp4"],
            "texts": ["结构化分析完成"],
        },
        result_assets=None,
        created_at=datetime.utcnow(),
    )

    read = AbilityInvocationLogRead.model_validate(log)

    assert read.output_summary.has_output is True
    assert read.output_summary.image_count == 1
    assert read.output_summary.video_count == 1
    assert read.output_summary.text_count == 1
    assert read.output_summary.primary_kind == "image"
    assert read.output_summary.primary_url == "https://oss.example.com/a.png"
    assert read.output_summary.text_preview == "结构化分析完成"


def test_log_read_outputs_summary_for_text_only():
    log = AbilityInvocationLog(
        id=2,
        ability_provider="volcengine",
        capability_key="vl_analyze",
        source="ability-api",
        status="success",
        response_payload={"texts": [{"text": "图片主体是花纹布料"}]},
        created_at=datetime.utcnow(),
    )

    read = AbilityInvocationLogRead.model_validate(log)

    assert read.output_summary.has_output is True
    assert read.output_summary.primary_kind == "text"
    assert read.output_summary.primary_url is None
    assert read.output_summary.text_count == 1


def test_log_read_outputs_summary_for_structured_only():
    log = AbilityInvocationLog(
        id=3,
        ability_provider="volcengine",
        capability_key="image_tags",
        source="ability-api",
        status="success",
        response_payload={"jsonOutput": {"tags": ["花纹", "蓝色"]}},
        created_at=datetime.utcnow(),
    )

    read = AbilityInvocationLogRead.model_validate(log)

    assert read.output_summary.has_output is True
    assert read.output_summary.primary_kind == "structured"
    assert read.output_summary.structured_count == 1


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


def test_start_log_truncates_long_source_to_column_limit(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    log_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            ability_id="ability_health_test",
            provider="openai",
            capability_key="gpt_image_2_generate",
            source="codex-dual-node-softstyle-release-check",
        )
    )

    with testing_session() as session:
        log = session.get(AbilityInvocationLog, log_id)
        assert log is not None
        assert log.source == "codex-dual-node-softstyle-releas"
        assert len(log.source) == 32


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


def test_list_logs_search_filters_full_log_history(monkeypatch):
    install_log_db(monkeypatch)
    svc = AbilityLogService()

    for executor_id, executor_name in [
        ("executor_comfyui_4090_233", "ComfyUI 4090 · 117.50.216.233"),
        ("executor_comfyui_5090_158", "ComfyUI 5090 · 117.50.80.158"),
    ]:
        log_id = svc.start_log(
            ability_logs_module.AbilityLogStartParams(
                provider="comfyui",
                capability_key="image_fission",
                ability_name="图裂变",
                executor_id=executor_id,
                executor_name=executor_name,
                source="workflow",
                task_id=f"task_{executor_id}",
                trace_id=f"trace_{executor_id}",
                request_payload={"imageUrl": f"https://example.com/{executor_id}.png"},
            )
        )
        svc.finish_success(log_id, response_payload={"storedUrl": f"https://oss.example.com/{executor_id}.png"})

    entries = svc.list_logs(provider="comfyui", search="4090", limit=20)

    assert len(entries) == 1
    assert entries[0].executor_id == "executor_comfyui_4090_233"
    assert svc.count_logs(provider="comfyui", search="4090") == 1


def test_list_logs_callback_failed_filter(monkeypatch):
    testing_session = install_log_db(monkeypatch)
    svc = AbilityLogService()

    ok_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            provider="comfyui",
            capability_key="image_fission",
            ability_name="图裂变",
            source="workflow",
            task_id="task_ok",
        )
    )
    failed_id = svc.start_log(
        ability_logs_module.AbilityLogStartParams(
            provider="comfyui",
            capability_key="image_fission",
            ability_name="图裂变",
            source="workflow",
            task_id="task_callback_failed",
        )
    )
    svc.finish_success(ok_id, response_payload={"ok": True})
    svc.finish_success(failed_id, response_payload={"ok": True})
    with testing_session() as session:
        log = session.get(AbilityInvocationLog, failed_id)
        assert log is not None
        log.callback_status = "failed"
        log.callback_http_status = 401
        log.callback_error = "INTERNAL_ONLY"
        session.add(log)
        session.commit()

    entries = svc.list_logs(provider="comfyui", callback_failed=True, limit=20)

    assert len(entries) == 1
    assert entries[0].task_id == "task_callback_failed"
    assert svc.count_logs(provider="comfyui", callback_failed=True) == 1
