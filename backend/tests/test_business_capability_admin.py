from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.business_runs as business_runs_module
from app.core.db import Base
from app.models.integration import Ability, AbilityInvocationLog, AbilityTask, BusinessCapability, BusinessRun, VendorModelCatalog
from app.schemas.business import (
    BusinessCapabilityCreateRequest,
    BusinessCapabilityPromoteRequest,
    BusinessCapabilityRollbackRequest,
    BusinessCapabilityUpdateRequest,
    BusinessDefaultApprovalCreateRequest,
    BusinessDefaultApprovalDecisionRequest,
    BusinessRunCreateRequest,
    BusinessUsageSummaryResponse,
)
from app.services.business_runs import BusinessRunService


def install_business_db(monkeypatch):
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
    with testing_session() as session:
        model = VendorModelCatalog(
            provider="openai",
            model="gpt-image-2",
            display_name="GPT Image 2",
            status="active",
            api_types=["image_edit"],
            execution_modes=["sync_then_store"],
            supports_mask=True,
            supports_multiple_images=True,
            supports_text=True,
            requires_global_egress=True,
            source="backend-test",
        )
        session.add(model)
        session.flush()
        session.add(
            Ability(
                id="ability_openai_fission",
                provider="openai",
                category="image_generation",
                capability_key="gpt_image_2_fission",
                version="v1",
                display_name="GPT Image 2 图裂变",
                status="active",
                ability_type="api",
                vendor_model_id=model.id,
            )
        )
        session.add(
            Ability(
                id="test_vl_analyze_image",
                provider="volcengine",
                category="vision",
                capability_key="vl_analyze_image",
                version="v1",
                display_name="VL 图像理解",
                status="active",
                ability_type="api",
            )
        )
        session.add(
            BusinessCapability(
                id="biz_fission_old",
                business_key="fission",
                version="old",
                display_name="旧图裂变",
                status="active",
                is_default=True,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
            )
        )
        session.commit()
        return int(model.id)


def test_business_capability_create_sets_default_and_resolves_model(monkeypatch) -> None:
    vendor_model_id = install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="新版图裂变",
            status="active",
            isDefault=True,
            primaryAbilityId="ability_openai_fission",
            metadata={"release_note": "test"},
        )
    )

    assert created["business_key"] == "fission"
    assert created["version"] == "v2"
    assert created["is_default"] is True
    assert created["primary_ability_id"] == "ability_openai_fission"
    assert created["primary_ability_name"] == "GPT Image 2 图裂变"
    assert created["vendor_model_id"] == vendor_model_id
    assert created["vendor_model_name"] == "GPT Image 2"

    listed = {item["id"]: item for item in service.list_capabilities()}
    assert listed["biz_fission_old"]["is_default"] is False


def test_business_capability_create_rejects_inactive_default(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.create_capability(
            BusinessCapabilityCreateRequest(
                businessKey="fission",
                version="bad-default",
                displayName="不可用默认版",
                status="inactive",
                isDefault=True,
                primaryAbilityId="ability_openai_fission",
            )
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE"
    else:  # pragma: no cover - defensive
        raise AssertionError("inactive default business capability should be rejected")


def test_business_capability_update_rejects_stopping_default(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.update_capability(
            "biz_fission_old",
            BusinessCapabilityUpdateRequest(status="inactive"),
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_DEFAULT_VERSION_MUST_BE_ACTIVE"
    else:  # pragma: no cover - defensive
        raise AssertionError("default business capability should not be stopped directly")


def test_business_capability_update_switches_default(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="新版图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
        )
    )
    updated = service.update_capability(
        created["id"],
        BusinessCapabilityUpdateRequest(status="active", isDefault=True),
    )

    listed = {item["id"]: item for item in service.list_capabilities()}
    assert updated["is_default"] is True
    assert listed["biz_fission_old"]["is_default"] is False
    assert listed[created["id"]]["is_default"] is True


def test_business_capability_promote_sets_default_and_records_event(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="新版图裂变",
            status="inactive",
            primaryAbilityId="ability_openai_fission",
        )
    )

    promoted = service.promote_capability(
        created["id"],
        BusinessCapabilityPromoteRequest(note="验证通过后切默认"),
    )
    listed = {item["id"]: item for item in service.list_capabilities()}

    assert promoted["status"] == "active"
    assert promoted["is_default"] is True
    assert listed["biz_fission_old"]["is_default"] is False
    events = promoted["extra_metadata"]["releaseEvents"]
    assert events[-1]["action"] == "promote_default"
    assert events[-1]["note"] == "验证通过后切默认"
    assert events[-1]["previousDefaultCapabilityId"] == "biz_fission_old"


def test_business_default_approval_approves_default_and_records_operation_log(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="approval-v2",
            displayName="审批图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
        )
    )

    approval = service.create_default_approval(
        created["id"],
        BusinessDefaultApprovalCreateRequest(note="灰度通过，申请切默认"),
    )
    assert approval["status"] == "pending"
    assert approval["business_key"] == "fission"

    decided = service.decide_default_approval(
        approval["id"],
        BusinessDefaultApprovalDecisionRequest(note="确认发布"),
        approve=True,
    )
    assert decided["status"] == "approved"
    assert decided["applied_at"] is not None

    listed = {item["id"]: item for item in service.list_capabilities()}
    assert listed[created["id"]]["is_default"] is True
    assert listed["biz_fission_old"]["is_default"] is False

    approvals = service.list_default_approvals(status="approved", business_key="fission")
    assert approvals[0]["id"] == approval["id"]

    actions = [item["action"] for item in service.list_operation_logs(business_key="fission")]
    assert "request_default_approval" in actions
    assert "approve_default_approval" in actions


def test_business_capability_rollback_restores_previous_default(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="新版图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
        )
    )
    promoted = service.promote_capability(
        created["id"],
        BusinessCapabilityPromoteRequest(note="灰度验证通过"),
    )

    rolled_back = service.rollback_default(
        "fission",
        BusinessCapabilityRollbackRequest(note="线上失败，回滚上一版"),
    )
    listed = {item["id"]: item for item in service.list_capabilities()}

    assert promoted["is_default"] is True
    assert rolled_back["id"] == "biz_fission_old"
    assert rolled_back["is_default"] is True
    assert listed[created["id"]]["is_default"] is False
    events = rolled_back["extra_metadata"]["releaseEvents"]
    assert events[-1]["action"] == "rollback_default"
    assert events[-1]["note"] == "线上失败，回滚上一版"
    assert events[-1]["previousDefaultCapabilityId"] == created["id"]


def test_business_capability_rollback_can_use_explicit_target(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="新版图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
        )
    )
    service.update_capability(
        created["id"],
        BusinessCapabilityUpdateRequest(status="active", isDefault=True),
    )

    rolled_back = service.rollback_default(
        "fission",
        BusinessCapabilityRollbackRequest(targetCapabilityId="biz_fission_old", note="指定回滚"),
    )

    assert rolled_back["id"] == "biz_fission_old"
    assert rolled_back["is_default"] is True


def test_business_capability_create_accepts_multistep_recipe(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="VL 辅助图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
            recipe={
                "mode": "pipeline",
                "vlAssist": {"enabled": True, "abilityId": "test_vl_analyze_image"},
                "steps": [
                    {"id": "vl", "type": "vl_analyze", "role": "preprocess", "abilityId": "test_vl_analyze_image"},
                    {
                        "id": "primary",
                        "type": "ability_task",
                        "role": "primary",
                        "abilityId": "ability_openai_fission",
                    },
                ],
            },
        )
    )

    assert created["primary_ability_id"] == "ability_openai_fission"
    assert [step["abilityId"] for step in created["recipe_steps"]] == [
        "test_vl_analyze_image",
        "ability_openai_fission",
    ]
    assert created["recipe_steps"][0]["abilityName"] == "VL 图像理解"


def test_business_run_records_recipe_steps(monkeypatch) -> None:
    install_business_db(monkeypatch)

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert ability_id == "ability_openai_fission"
            assert payload.imageUrl == "https://example.com/a.png"
            return {"id": "task_run_1", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/a.png",
            version="old",
            metadata={"grayKey": "tenant-a"},
        ),
        user=None,
    )

    assert run["status"] == "queued"
    assert len(run["steps"]) == 1
    assert run["steps"][0]["role"] == "primary"
    assert run["steps"][0]["status"] == "queued"
    assert run["steps"][0]["ability_id"] == "ability_openai_fission"
    assert run["steps"][0]["ability_task_id"] == "t1.fission.auto.task_run_1"


def test_business_run_accepts_flat_fission_params(monkeypatch) -> None:
    install_business_db(monkeypatch)

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert ability_id == "ability_openai_fission"
            assert payload.inputs["bili"] == 65
            assert payload.inputs["width"] == 1024
            assert payload.inputs["height"] == 768
            assert payload.inputs["image_desc"] == "蓝白植物纹样"
            assert payload.inputs["prompt"] == "做一组裂变"
            return {"id": "task_run_flat", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/a.png",
            version="old",
            prompt="做一组裂变",
            bili=65,
            width=1024,
            height=768,
            image_desc="蓝白植物纹样",
        ),
        user=None,
    )

    assert run["status"] == "queued"
    assert run["ability_task_id"] == "t1.fission.auto.task_run_flat"


def test_business_run_accepts_flat_pattern_extract_params(monkeypatch) -> None:
    install_business_db(monkeypatch)
    with business_runs_module.get_session() as session:
        session.add(
            Ability(
                id="ability_pattern_extract",
                provider="comfyui",
                category="image_generation",
                capability_key="pattern_extract",
                version="v1",
                display_name="花纹提取",
                status="active",
                ability_type="workflow",
            )
        )
        session.add(
            BusinessCapability(
                id="biz_pattern_extract_test",
                business_key="pattern_extract",
                version="old",
                display_name="花纹提取测试版",
                status="active",
                is_default=True,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_pattern_extract",
                    "steps": [
                        {
                            "id": "primary",
                            "type": "ability_task",
                            "role": "primary",
                            "abilityId": "ability_pattern_extract",
                        }
                    ],
                },
            )
        )
        session.commit()

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert ability_id == "ability_pattern_extract"
            assert payload.imageUrl == "https://example.com/pattern.png"
            assert payload.inputs["prompt"] == "提取主体花纹"
            assert payload.inputs["negative_prompt"] == "不要背景"
            assert payload.inputs["width"] == 1800
            assert payload.inputs["height"] == 1800
            assert payload.inputs["batch"] == 2
            assert payload.inputs["lora"] == "杯子1124.safetensors"
            return {"id": "task_pattern_flat", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    run = service.create_run(
        business_key="pattern_extract",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/pattern.png",
            version="old",
            prompt="提取主体花纹",
            negative_prompt="不要背景",
            width=1800,
            height=1800,
            batch=2,
            lora="杯子1124.safetensors",
        ),
        user=None,
    )

    assert run["status"] == "queued"
    assert run["ability_task_id"] == "t1.pattern_extract.auto.task_pattern_flat"


def test_business_run_records_trace_and_cost_from_ability_log(monkeypatch) -> None:
    install_business_db(monkeypatch)
    started = datetime.utcnow() - timedelta(seconds=3)
    finished = datetime.utcnow()

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert payload.metadata["traceId"] == "trace-001"
            assert payload.metadata["requestId"] == "req-001"
            assert payload.metadata["tenantId"] == "tenant-a"
            assert payload.metadata["clientId"] == "client-web"
            assert payload.metadata["channel"] == "coze-workflow"
            return {"id": "task_costed", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/a.png",
            version="old",
            source="coze",
            channel="coze-workflow",
            traceId="trace-001",
            requestId="req-001",
            tenantId="tenant-a",
            clientId="client-web",
        ),
        user=None,
    )

    with business_runs_module.get_session() as session:
        log = AbilityInvocationLog(
            ability_id="ability_openai_fission",
            ability_provider="openai",
            capability_key="gpt_image_2_fission",
            ability_name="GPT Image 2 图裂变",
            source="business-api",
            task_id="task_costed",
            status="success",
            trace_id="trace-001",
            duration_ms=3000,
            billing_unit="image",
            unit_price=0.12,
            currency="USD",
            cost_amount=0.24,
        )
        session.add(log)
        session.flush()
        session.add(
            AbilityTask(
                id="task_costed",
                ability_id="ability_openai_fission",
                ability_name="GPT Image 2 图裂变",
                ability_provider="openai",
                capability_key="gpt_image_2_fission",
                status="succeeded",
                log_id=log.id,
                duration_ms=3000,
                result_payload={
                    "images": [{"url": "https://example.com/result.png"}],
                    "usage": {"total_tokens": 12},
                },
                started_at=started,
                finished_at=finished,
            )
        )
        session.commit()

    fetched = service.get_run(run_id=run["id"], user=None)

    assert fetched["source"] == "coze"
    assert fetched["channel"] == "coze-workflow"
    assert fetched["trace_id"] == "trace-001"
    assert fetched["request_id"] == "req-001"
    assert fetched["tenant_id"] == "tenant-a"
    assert fetched["client_id"] == "client-web"
    assert fetched["duration_ms"] == 3000
    assert fetched["billing_unit"] == "image"
    assert fetched["cost_amount"] == 0.24
    assert fetched["currency"] == "USD"
    assert fetched["quota_units"] == 12
    assert fetched["image_urls"] == ["https://example.com/result.png"]
    primary_step = fetched["steps"][0]
    assert primary_step["duration_ms"] == 3000
    assert primary_step["cost_amount"] == 0.24
    assert primary_step["quota_units"] == 12


def test_business_run_list_filters_by_business_status_and_version(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add_all(
            [
                BusinessRun(
                    id="run_fission_v1_ok",
                    business_key="fission",
                    version="old",
                    status="succeeded",
                    source="coze",
                    tenant_id="tenant-a",
                    client_id="client-web",
                    trace_id="trace-filter",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/a.png"],
                ),
                BusinessRun(
                    id="run_fission_v2_fail",
                    business_key="fission",
                    version="v2",
                    status="failed",
                    ability_id="ability_openai_fission",
                    error_message="TASK_FAILED",
                ),
                BusinessRun(
                    id="run_outpaint_v1_ok",
                    business_key="outpaint",
                    version="v1",
                    status="succeeded",
                    ability_id="ability_openai_fission",
                ),
            ]
        )
        session.commit()

    total, items = service.list_runs(
        business_key="fission",
        status="succeeded",
        version="old",
        source="coze",
        tenant_id="tenant-a",
        client_id="client-web",
        trace_id="trace-filter",
        limit=20,
    )

    assert total == 1
    assert [item["id"] for item in items] == ["run_fission_v1_ok"]


def test_business_usage_summary_groups_source_tenant_and_cost(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    now = datetime.utcnow()

    with business_runs_module.get_session() as session:
        session.add_all(
            [
                BusinessRun(
                    id="run_usage_ok",
                    business_key="fission",
                    version="old",
                    status="succeeded",
                    source="coze",
                    channel="coze-workflow",
                    tenant_id="tenant-a",
                    client_id="client-web",
                    trace_id="trace-usage-1",
                    ability_id="ability_openai_fission",
                    duration_ms=2000,
                    cost_amount=0.2,
                    currency="USD",
                    quota_units=1,
                    created_at=now - timedelta(minutes=10),
                ),
                BusinessRun(
                    id="run_usage_fail",
                    business_key="fission",
                    version="v2",
                    status="failed",
                    source="coze",
                    tenant_id="tenant-a",
                    client_id="client-web",
                    trace_id="trace-usage-2",
                    ability_id="ability_openai_fission",
                    duration_ms=4000,
                    cost_amount=0.1,
                    currency="USD",
                    quota_units=1,
                    error_message="TASK_FAILED",
                    created_at=now - timedelta(minutes=5),
                ),
                BusinessRun(
                    id="run_usage_old",
                    business_key="outpaint",
                    version="v1",
                    status="succeeded",
                    source="client",
                    tenant_id="tenant-b",
                    ability_id="ability_openai_fission",
                    created_at=now - timedelta(hours=48),
                ),
            ]
        )
        session.commit()

    summary = service.usage_summary(window_hours=24, source="coze", tenant_id="tenant-a")

    assert summary["total"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["avg_duration_ms"] == 3000
    assert summary["cost_by_currency"] == {"USD": 0.3}
    assert summary["quota_units"] == 2
    assert summary["by_business"][0]["key"] == "fission"
    assert summary["by_source"][0]["key"] == "coze"
    assert summary["by_tenant"][0]["key"] == "tenant-a"
    assert summary["by_client"][0]["key"] == "client-web"
    assert summary["recent_failures"][0]["id"] == "run_usage_fail"
    validated = BusinessUsageSummaryResponse.model_validate(summary).model_dump(by_alias=False)
    assert validated["recentFailures"][0]["runId"] == "run_usage_fail"

    trace_summary = service.usage_summary(window_hours=24, trace_id="trace-usage-2")
    assert trace_summary["total"] == 1
    assert trace_summary["recent_failures"][0]["trace_id"] == "trace-usage-2"


def test_business_capability_list_includes_latest_run_summary(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    now = datetime.utcnow()

    with business_runs_module.get_session() as session:
        session.add_all(
            [
                BusinessRun(
                    id="run_old_success",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/a.png"],
                    created_at=now - timedelta(minutes=5),
                ),
                BusinessRun(
                    id="run_new_failed",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="failed",
                    ability_id="ability_openai_fission",
                    error_message="TASK_FAILED",
                    created_at=now,
                ),
            ]
        )
        session.commit()

    listed = {item["id"]: item for item in service.list_capabilities()}

    latest = listed["biz_fission_old"]["latest_run"]
    assert latest["id"] == "run_new_failed"
    assert latest["status"] == "failed"
    assert latest["error"] == "TASK_FAILED"

    metrics = listed["biz_fission_old"]["run_metrics"]
    assert metrics["window_hours"] == 24
    assert metrics["total"] == 2
    assert metrics["succeeded"] == 1
    assert metrics["failed"] == 1
    assert metrics["success_rate"] == 0.5


def test_business_run_submits_vl_sidecar_step(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="vl",
            displayName="VL 辅助图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
            recipe={
                "mode": "pipeline",
                "vlAssist": {"enabled": True, "abilityId": "test_vl_analyze_image"},
                "steps": [
                    {
                        "id": "vl",
                        "type": "vl_analyze",
                        "role": "preprocess",
                        "abilityId": "test_vl_analyze_image",
                    },
                    {
                        "id": "primary",
                        "type": "ability_task",
                        "role": "primary",
                        "abilityId": "ability_openai_fission",
                    },
                ],
            },
        )
    )

    calls = []

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            calls.append((ability_id, payload))
            return {"id": f"task_run_{len(calls)}", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/a.png",
            version="vl",
            inputs={
                "vl_provider": "coze_vl",
                "coze_workflow_id": "763_vl",
                "vl_prompt": "分析图案主体和颜色",
            },
            metadata={"grayKey": "tenant-a"},
        ),
        user=None,
    )

    assert [item[0] for item in calls] == ["ability_openai_fission", "test_vl_analyze_image"]
    vl_payload = calls[1][1]
    assert vl_payload.imageUrl == "https://example.com/a.png"
    assert vl_payload.inputs["provider"] == "coze_vl"
    assert vl_payload.inputs["coze_workflow_id"] == "763_vl"
    assert vl_payload.inputs["prompt"] == "分析图案主体和颜色"
    assert len(run["steps"]) == 2
    assert run["steps"][0]["step_type"] == "vl_analyze"
    assert run["steps"][0]["status"] == "queued"
    assert run["steps"][0]["ability_task_id"] == "t1.fission.auto.task_run_2"
    assert run["steps"][1]["role"] == "primary"
    assert run["steps"][1]["ability_task_id"] == "t1.fission.auto.task_run_1"


def test_business_run_waits_for_vl_before_primary_and_applies_summary(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="vl-blocking",
            displayName="VL 串联图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
            recipe={
                "mode": "vl_then_primary",
                "vlAssist": {
                    "enabled": True,
                    "abilityId": "test_vl_analyze_image",
                    "waitForResult": True,
                    "applyToPrimary": True,
                },
                "steps": [
                    {"id": "vl", "type": "vl_analyze", "role": "preprocess", "abilityId": "test_vl_analyze_image"},
                    {"id": "primary", "type": "ability_task", "role": "primary", "abilityId": "ability_openai_fission"},
                ],
            },
        )
    )

    calls = []

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            calls.append((ability_id, payload))
            if ability_id == "test_vl_analyze_image":
                return {"id": "task_vl", "status": "queued"}
            assert ability_id == "ability_openai_fission"
            assert payload.inputs["image_desc"] == "蓝白植物连续花型"
            assert payload.inputs["prompt"] == "生成蓝白植物面料裂变图"
            return {"id": "task_primary", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", version="vl-blocking"),
        user=None,
    )

    assert [item[0] for item in calls] == ["test_vl_analyze_image"]
    assert run["ability_task_id"] is None
    assert run["steps"][0]["status"] == "queued"
    assert run["steps"][1]["status"] == "planned"

    with business_runs_module.get_session() as session:
        session.add(
            AbilityTask(
                id="task_vl",
                ability_id="test_vl_analyze_image",
                ability_name="VL 图像理解",
                ability_provider="vl",
                capability_key="analyze_image",
                status="succeeded",
                result_payload={
                    "texts": [
                        '{"summary":"蓝白植物图案","promptCard":{"imageDesc":"蓝白植物连续花型",'
                        '"positivePrompt":"生成蓝白植物面料裂变图"}}'
                    ],
                },
            )
        )
        session.commit()

    fetched = service.get_run(run_id=run["id"], user=None)

    assert [item[0] for item in calls] == ["test_vl_analyze_image", "ability_openai_fission"]
    assert fetched["ability_task_id"] == "t1.fission.auto.task_primary"
    assert fetched["steps"][0]["status"] == "succeeded"
    assert fetched["steps"][1]["status"] == "queued"
    assert fetched["steps"][1]["ability_task_id"] == "t1.fission.auto.task_primary"


def test_business_run_blocks_primary_when_required_vl_fails(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="vl-blocking",
            displayName="VL 串联图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
            recipe={
                "mode": "vl_then_primary",
                "vlAssist": {"enabled": True, "abilityId": "test_vl_analyze_image", "waitForResult": True},
                "steps": [
                    {"id": "vl", "type": "vl_analyze", "role": "preprocess", "abilityId": "test_vl_analyze_image"},
                    {"id": "primary", "type": "ability_task", "role": "primary", "abilityId": "ability_openai_fission"},
                ],
            },
        )
    )

    calls = []

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            calls.append(ability_id)
            return {"id": "task_vl", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", version="vl-blocking"),
        user=None,
    )
    with business_runs_module.get_session() as session:
        session.add(
            AbilityTask(
                id="task_vl",
                ability_id="test_vl_analyze_image",
                ability_name="VL 图像理解",
                ability_provider="vl",
                capability_key="analyze_image",
                status="failed",
                error_message="VL_DOWN",
            )
        )
        session.commit()

    fetched = service.get_run(run_id=run["id"], user=None)

    assert calls == ["test_vl_analyze_image"]
    assert fetched["status"] == "failed"
    assert fetched["error_message"] == "VL_DOWN"
    assert fetched["ability_task_id"] is None
    assert fetched["steps"][1]["status"] == "failed"
    assert fetched["steps"][1]["error_message"] == "VL_DOWN"


def test_business_run_keeps_primary_when_vl_sidecar_submit_fails(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="vl",
            displayName="VL 辅助图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
            recipe={
                "mode": "pipeline",
                "vlAssist": {"enabled": True, "abilityId": "test_vl_analyze_image"},
                "steps": [
                    {"id": "vl", "type": "vl_analyze", "role": "preprocess", "abilityId": "test_vl_analyze_image"},
                    {"id": "primary", "type": "ability_task", "role": "primary", "abilityId": "ability_openai_fission"},
                ],
            },
        )
    )

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            if ability_id == "test_vl_analyze_image":
                raise HTTPException(status_code=502, detail="VL_DOWN")
            return {"id": "task_primary", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", version="vl"),
        user=None,
    )

    assert run["status"] == "queued"
    assert run["ability_task_id"] == "t1.fission.auto.task_primary"
    assert run["steps"][0]["status"] == "failed"
    assert run["steps"][0]["error_message"] == "VL_DOWN"
    assert run["steps"][1]["status"] == "queued"


def test_business_run_step_returns_safe_vl_result_summary(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="vl",
            displayName="VL 辅助图裂变",
            status="active",
            primaryAbilityId="ability_openai_fission",
            recipe={
                "mode": "pipeline",
                "vlAssist": {"enabled": True, "abilityId": "test_vl_analyze_image"},
                "steps": [
                    {"id": "vl", "type": "vl_analyze", "role": "preprocess", "abilityId": "test_vl_analyze_image"},
                    {"id": "primary", "type": "ability_task", "role": "primary", "abilityId": "ability_openai_fission"},
                ],
            },
        )
    )

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            return {"id": "task_vl" if ability_id == "test_vl_analyze_image" else "task_primary", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", version="vl"),
        user=None,
    )

    with business_runs_module.get_session() as session:
        session.add(
            AbilityTask(
                id="task_vl",
                ability_id="test_vl_analyze_image",
                ability_name="VL 图像理解",
                ability_provider="vl",
                capability_key="analyze_image",
                status="succeeded",
                result_payload={
                    "texts": [
                        '{"summary":"蓝白植物图案","style":"清新手绘","subjects":["植物","花朵"],'
                        '"colors":["蓝色","白色"],"promptCard":{"imageDesc":"蓝白色植物纹样",'
                        '"positivePrompt":"蓝白植物连续花型","negativePrompt":"低清晰度"}}'
                    ],
                },
            )
        )
        session.commit()

    fetched = service.get_run(run_id=run["id"], user=None)
    vl_step = fetched["steps"][0]
    assert vl_step["status"] == "succeeded"
    assert vl_step["result_summary"]["summary"] == "蓝白植物图案"
    assert vl_step["result_summary"]["style"] == "清新手绘"
    assert vl_step["result_summary"]["imageDesc"] == "蓝白色植物纹样"
    assert vl_step["result_summary"]["positivePrompt"] == "蓝白植物连续花型"


def test_business_run_detail_includes_flow_evidence(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            return {"id": "task_primary", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", source="coze"),
        user=None,
    )

    with business_runs_module.get_session() as session:
        log = AbilityInvocationLog(
            ability_id="ability_openai_fission",
            ability_provider="openai",
            capability_key="gpt_image_2_fission",
            ability_name="GPT Image 2 图裂变",
            executor_id="executor_comfyui_4090",
            executor_name="ComfyUI 4090 · 233",
            executor_type="comfyui",
            source="business-api",
            task_id="task_primary",
            status="succeeded",
            duration_ms=1200,
            stored_url="https://oss.example.com/result.png",
            result_assets=[{"storedUrl": "https://oss.example.com/result.png"}],
        )
        session.add(log)
        session.flush()
        session.add(
            AbilityTask(
                id="task_primary",
                ability_id="ability_openai_fission",
                ability_name="GPT Image 2 图裂变",
                ability_provider="openai",
                capability_key="gpt_image_2_fission",
                status="succeeded",
                log_id=log.id,
                duration_ms=1200,
                result_payload={"assets": [{"storedUrl": "https://oss.example.com/result.png"}]},
                started_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
        )
        session.commit()

    fetched = service.get_run(run_id=run["id"], user=None)

    assert fetched["status"] == "succeeded"
    assert fetched["image_urls"] == ["https://oss.example.com/result.png"]
    assert fetched["flow_summary"]["message"] == "业务链路执行成功"
    assert fetched["flow_summary"]["route"]["businessKey"] == "fission"
    assert fetched["flow_summary"]["ability"]["id"] == "ability_openai_fission"
    assert fetched["flow_summary"]["executor"]["id"] == "executor_comfyui_4090"
    assert fetched["flow_summary"]["output"]["hasOssOutput"] is True
    assert fetched["steps"][0]["executor_name"] == "ComfyUI 4090 · 233"
    assert fetched["steps"][0]["execution_evidence"]["hasOssOutput"] is True


def test_business_capability_update_rejects_missing_ability(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.update_capability(
            "biz_fission_old",
            BusinessCapabilityUpdateRequest(primaryAbilityId="missing_ability"),
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE"
    else:  # pragma: no cover - defensive
        raise AssertionError("missing ability should be rejected")


def test_business_capability_create_rejects_missing_step_ability(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.create_capability(
            BusinessCapabilityCreateRequest(
                businessKey="fission",
                version="v2",
                displayName="坏配方",
                status="active",
                primaryAbilityId="ability_openai_fission",
                recipe={
                    "mode": "pipeline",
                    "steps": [
                        {"id": "primary", "type": "ability_task", "role": "primary", "abilityId": "ability_openai_fission"},
                        {"id": "extra", "type": "ability_task", "abilityId": "missing_ability"},
                    ],
                },
            )
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE"
    else:  # pragma: no cover - defensive
        raise AssertionError("missing step ability should be rejected")


def test_business_capability_create_rejects_missing_vl_assist_ability(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.create_capability(
            BusinessCapabilityCreateRequest(
                businessKey="fission",
                version="v2",
                displayName="坏 VL 配方",
                status="active",
                primaryAbilityId="ability_openai_fission",
                recipe={"vlAssist": {"enabled": True, "abilityId": "missing_vl"}},
            )
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_RECIPE_ABILITY_NOT_AVAILABLE"
    else:  # pragma: no cover - defensive
        raise AssertionError("missing VL ability should be rejected")


def test_business_selects_rollout_version_by_allowlist(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_v2_gray",
                business_key="fission",
                version="v2",
                display_name="灰度图裂变",
                status="active",
                is_default=False,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
                extra_metadata={"rollout": {"enabled": True, "percent": 0, "allowlist": ["tenant-a"]}},
            )
        )
        session.commit()
        selected, route = service._select_capability(
            session,
            business_key="fission",
            version=None,
            payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", metadata={"grayKey": "tenant-a"}),
            image_url="https://example.com/a.png",
        )

    assert selected.version == "v2"
    assert route["selectedBy"] == "rollout_allowlist"
    assert route["routeKeyHash"]


def test_business_rollout_uses_top_level_tenant_id(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_v2_gray",
                business_key="fission",
                version="v2",
                display_name="灰度图裂变",
                status="active",
                is_default=False,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
                extra_metadata={"rollout": {"enabled": True, "percent": 0, "allowlist": ["tenant-a"]}},
            )
        )
        session.commit()
        selected, route = service._select_capability(
            session,
            business_key="fission",
            version=None,
            payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", tenantId="tenant-a"),
            image_url="https://example.com/a.png",
        )

    assert selected.version == "v2"
    assert route["selectedBy"] == "rollout_allowlist"


def test_business_route_preview_does_not_submit_task(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_v2_gray",
                business_key="fission",
                version="v2",
                display_name="灰度图裂变",
                status="active",
                is_default=False,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
                extra_metadata={"rollout": {"enabled": True, "percent": 0, "allowlist": ["tenant-a"]}},
            )
        )
        session.commit()

    preview = service.preview_route(
        business_key="fission",
        payload=BusinessRunCreateRequest(tenantId="tenant-a"),
        user=None,
    )

    assert preview["selected_version"] == "v2"
    assert preview["selected_by"] == "rollout_allowlist"
    assert preview["default_version"] == "old"
    assert any(item["version"] == "v2" and item["hasRollout"] for item in preview["active_versions"])


def test_business_rollout_falls_back_to_default_when_missed(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_v2_gray",
                business_key="fission",
                version="v2",
                display_name="灰度图裂变",
                status="active",
                is_default=False,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
                extra_metadata={"rollout": {"enabled": True, "percent": 0, "allowlist": ["tenant-a"]}},
            )
        )
        session.commit()
        selected, route = service._select_capability(
            session,
            business_key="fission",
            version=None,
            payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", metadata={"grayKey": "tenant-b"}),
            image_url="https://example.com/a.png",
        )

    assert selected.version == "old"
    assert route["selectedBy"] == "default"
