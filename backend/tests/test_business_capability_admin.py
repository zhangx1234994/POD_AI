from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.business_runs as business_runs_module
from app.core.db import Base
from app.models.integration import (
    Ability,
    AbilityInvocationLog,
    AbilityTask,
    ApiKey,
    BusinessCapability,
    BusinessRun,
    BusinessRunStep,
    VendorModelCatalog,
)
from app.models.user import User
from app.schemas.business import (
    BusinessAcceptanceRecordRequest,
    BusinessCapabilityCreateRequest,
    BusinessCapabilityDraftCreateRequest,
    BusinessCapabilityDraftPublishRequest,
    BusinessCapabilityDraftRecipeUpdateRequest,
    BusinessCapabilityPromoteRequest,
    BusinessCapabilityRollbackRequest,
    BusinessCapabilityUpdateRequest,
    BusinessDefaultApprovalCreateRequest,
    BusinessDefaultApprovalDecisionRequest,
    BusinessRunCreateRequest,
    BusinessUsageSummaryResponse,
)
from app.services.business_runs import BusinessRunService
from app.services.wallet import wallet_service
from app.models.wallet import PackageBalance, PackageLedger


def passed_acceptance_metadata(note: str = "测试环境业务验收通过") -> dict:
    record = {
        "id": "bizacc_test",
        "status": "passed",
        "note": note,
        "createdAt": datetime.utcnow().isoformat(),
    }
    return {"latestAcceptance": record, "acceptanceRecords": [record]}


def test_business_capability_version_line_prefers_recipe_metadata() -> None:
    row = BusinessCapability(
        id="biz_test_custom_line",
        business_key="fission",
        version="gpt-image2-vl-v9",
        display_name="图裂变 · 测试版本",
        status="active",
        is_default=False,
        recipe={"primaryAbilityId": "ability_openai_fission"},
        input_schema={"fields": []},
        output_schema={"fields": []},
        extra_metadata={
            "provider": "openai",
            "versionLine": {
                "key": "business-owned-line",
                "label": "业务指定路线",
                "detail": "由业务配方显式指定，不再靠 provider 或版本名推断。",
                "priority": 12,
            },
        },
    )

    line = BusinessRunService._business_capability_version_line(
        row,
        primary_ability_provider="openai",
        vendor_model_provider="openai",
    )

    assert line == {
        "key": "business-owned-line",
        "label": "业务指定路线",
        "detail": "由业务配方显式指定，不再靠 provider 或版本名推断。",
        "priority": 12,
    }


def install_business_db(
    monkeypatch,
    *,
    with_vendor_cost: bool = False,
    with_vendor_key: bool = False,
    with_vendor_acceptance: bool = False,
):
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
            cost_policy={"unitPrice": 0.12, "unit": "image"} if with_vendor_cost else None,
            extra_metadata={
                "latestAcceptance": {
                    "id": "vmodacc_test",
                    "status": "passed",
                    "note": "测试环境验收通过",
                    "createdAt": datetime.utcnow().isoformat(),
                },
                "acceptanceRecords": [
                    {
                        "id": "vmodacc_test",
                        "status": "passed",
                        "note": "测试环境验收通过",
                        "createdAt": datetime.utcnow().isoformat(),
                    }
                ],
            }
            if with_vendor_acceptance
            else {},
            source="backend-test",
        )
        session.add(model)
        session.flush()
        if with_vendor_key:
            session.add(
                ApiKey(
                    id="key_openai_test",
                    provider="openai",
                    name="OpenAI 测试 Key",
                    key="sk-test",
                    status="active",
                    extra_metadata={
                        "lastCheck": {
                            "success": True,
                            "checkedAt": datetime.utcnow().isoformat(),
                        }
                    },
                )
            )
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
                default_params={"size": "1024x1024", "quality": "preview"},
                input_schema={
                    "fields": [
                        {"name": "imageUrl", "label": "原图 URL", "type": "image", "required": True},
                        {"name": "prompt", "label": "额外要求", "type": "textarea", "required": False},
                    ]
                },
                extra_metadata={
                    "routing_policy": "queue",
                    "allowed_executor_ids": ["executor_vendor_api_default"],
                    "fallback_to_default": False,
                },
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
    vendor_model_id = install_business_db(
        monkeypatch,
        with_vendor_cost=True,
        with_vendor_key=True,
        with_vendor_acceptance=True,
    )
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="v2",
            displayName="新版图裂变",
            status="active",
            isDefault=True,
            primaryAbilityId="ability_openai_fission",
            metadata={
                **passed_acceptance_metadata(),
                "release_note": "test",
                "versionLineage": {
                    "parentVersionId": "biz_fission_old",
                    "supersedesVersionId": "biz_fission_old",
                    "changeSummary": "商业模型线验证通过后替代旧图裂变。",
                    "breakingChange": False,
                    "decision": "version_upgrade",
                    "decisionNote": "入口不变，只替换底层模型。",
                },
            },
        )
    )

    assert created["business_key"] == "fission"
    assert created["version"] == "v2"
    assert created["is_default"] is True
    assert created["primary_ability_id"] == "ability_openai_fission"
    assert created["primary_ability_name"] == "GPT Image 2 图裂变"
    assert created["vendor_model_id"] == vendor_model_id
    assert created["vendor_model_name"] == "GPT Image 2"
    assert created["version_line"]["key"] == "commercial-model"
    assert created["version_line"]["label"] == "商业模型线"
    assert created["version_lineage"]["parentVersionId"] == "biz_fission_old"
    assert created["version_lineage"]["supersedesVersionId"] == "biz_fission_old"
    assert created["version_lineage"]["changeSummary"] == "商业模型线验证通过后替代旧图裂变。"
    assert created["version_lineage"]["breakingChange"] is False
    assert created["version_lineage"]["decision"] == "version_upgrade"
    assert created["version_lineage"]["decisionNote"] == "入口不变，只替换底层模型。"
    assert created["governance_status"] == "ready"
    assert created["runtime_key_configured"] is True
    assert created["model_cost_configured"] is True
    assert created["egress_verified"] is True
    assert created["orchestration_graph"]["mode"] == "recipe"
    assert created["orchestration_graph"]["businessKey"] == "fission"
    assert created["orchestration_graph"]["businessVersionId"] == created["id"]
    assert created["orchestration_graph"]["businessVersion"] == "v2"
    assert [node["id"] for node in created["orchestration_graph"]["nodes"]] == ["entry", "primary", "result"]
    assert created["orchestration_graph"]["nodes"][0]["businessKey"] == "fission"
    assert created["orchestration_graph"]["nodes"][0]["version"] == "v2"
    primary_node = created["orchestration_graph"]["nodes"][1]
    assert primary_node["inputSchema"]["fieldCount"] == 2
    assert primary_node["defaultParams"]["size"] == "1024x1024"
    assert primary_node["routing"]["allowedExecutorIds"] == ["executor_vendor_api_default"]
    assert primary_node["routing"]["fallbackToDefault"] is False

    listed = {item["id"]: item for item in service.list_capabilities()}
    assert listed["biz_fission_old"]["is_default"] is False


def test_business_capability_create_default_requires_release_gate(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with pytest.raises(HTTPException) as exc_info:
        service.create_capability(
            BusinessCapabilityCreateRequest(
                businessKey="fission",
                version="unsafe-default",
                displayName="未就绪默认图裂变",
                status="active",
                isDefault=True,
                primaryAbilityId="ability_openai_fission",
                metadata=passed_acceptance_metadata(),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "BUSINESS_RELEASE_GATE_BLOCKED"


def test_business_capability_governance_ready_when_vendor_runtime_is_configured(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="governance-ready",
            displayName="治理就绪图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
        )
    )

    assert created["governance_status"] == "ready"
    assert created["governance_issues"] == []
    assert created["runtime_key_configured"] is True
    assert created["model_cost_configured"] is True


def test_business_capability_governance_detects_stale_recipe_step_ability(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_stale_step",
                business_key="fission",
                version="stale-step",
                display_name="图裂变异常步骤",
                status="active",
                is_default=False,
                recipe={
                    "mode": "pipeline",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [
                        {
                            "id": "primary",
                            "type": "ability_task",
                            "role": "primary",
                            "abilityId": "ability_openai_fission",
                        },
                        {
                            "id": "score",
                            "type": "ability_task",
                            "role": "postprocess",
                            "abilityId": "missing_score_ability",
                        },
                    ],
                },
            )
        )
        session.commit()

    listed = {item["id"]: item for item in service.list_capabilities()}
    stale = listed["biz_fission_stale_step"]
    assert stale["governance_status"] == "blocker"
    assert "BUSINESS_GOVERNANCE_STEP_ABILITY_NOT_FOUND" in stale["governance_issues"]
    assert any("引用了不存在的能力" in item for item in stale["governance_suggestions"])


def test_business_capability_governance_blocks_unaccepted_vendor_model(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="vendor-unaccepted",
            displayName="未验收模型图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
        )
    )

    assert created["governance_status"] == "blocker"
    assert "BUSINESS_GOVERNANCE_VENDOR_MODEL_ACCEPTANCE_REQUIRED" in created["governance_issues"]
    assert created["runtime_key_configured"] is True
    assert created["model_cost_configured"] is True


def test_business_capability_governance_blocks_unverified_global_egress(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_acceptance=True)
    with business_runs_module.get_session() as session:
        session.add(
            ApiKey(
                id="key_openai_unchecked",
                provider="openai",
                name="OpenAI 未验 Key",
                key="sk-test-unchecked",
                status="active",
                extra_metadata={},
            )
        )
        session.commit()
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="egress-unchecked",
            displayName="出网未验图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
        )
    )

    assert created["governance_status"] == "blocker"
    assert created["runtime_key_configured"] is True
    assert created["egress_verified"] is False
    assert "BUSINESS_GOVERNANCE_VENDOR_EGRESS_NOT_VERIFIED" in created["governance_issues"]


def test_business_capability_default_blocks_missing_vendor_key(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_acceptance=True)
    service = BusinessRunService()

    with pytest.raises(HTTPException) as exc_info:
        service.create_capability(
            BusinessCapabilityCreateRequest(
                businessKey="fission",
                version="missing-key-default",
                displayName="缺密钥默认图裂变",
                status="active",
                isDefault=True,
                primaryAbilityId="ability_openai_fission",
                metadata=passed_acceptance_metadata(),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "BUSINESS_RELEASE_GATE_BLOCKED"

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="missing-key-inspect",
            displayName="缺密钥检查图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
            metadata=passed_acceptance_metadata(),
        )
    )

    assert created["runtime_key_configured"] is False
    assert "BUSINESS_GOVERNANCE_VENDOR_KEY_MISSING" in created["governance_issues"]
    assert created["release_gate"]["canRelease"] is False


def test_business_capability_default_blocks_missing_vendor_cost_policy(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_key=True, with_vendor_acceptance=True)
    service = BusinessRunService()

    with pytest.raises(HTTPException) as exc_info:
        service.create_capability(
            BusinessCapabilityCreateRequest(
                businessKey="fission",
                version="missing-cost-default",
                displayName="缺计价默认图裂变",
                status="active",
                isDefault=True,
                primaryAbilityId="ability_openai_fission",
                metadata=passed_acceptance_metadata(),
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "BUSINESS_RELEASE_GATE_BLOCKED"

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="missing-cost-inspect",
            displayName="缺计价检查图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
            metadata=passed_acceptance_metadata(),
        )
    )

    assert created["model_cost_configured"] is False
    assert "BUSINESS_GOVERNANCE_VENDOR_MODEL_COST_MISSING" in created["governance_issues"]
    assert created["release_gate"]["canRelease"] is False


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


def test_business_capability_update_rejects_default_recipe_mutation(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.update_capability(
            "biz_fission_old",
            BusinessCapabilityUpdateRequest(
                primaryAbilityId="test_vl_analyze_image",
            ),
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE"
    else:  # pragma: no cover - defensive
        raise AssertionError("default business capability recipe should require a draft version")


def test_business_capability_update_rejects_default_schema_mutation(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.update_capability(
            "biz_fission_old",
            BusinessCapabilityUpdateRequest(
                inputSchema={"fields": [{"name": "imageUrl", "type": "image", "required": True}]},
            ),
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE"
    else:  # pragma: no cover - defensive
        raise AssertionError("default business capability schema should require a draft version")


def test_business_capability_update_rejects_default_demotion(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    try:
        service.update_capability(
            "biz_fission_old",
            BusinessCapabilityUpdateRequest(isDefault=False),
        )
    except Exception as exc:
        assert getattr(exc, "detail", None) == "BUSINESS_DEFAULT_VERSION_CONTROL_FIELDS_IMMUTABLE"
    else:  # pragma: no cover - defensive
        raise AssertionError("default business capability should be changed by promoting another version")


def test_business_capability_can_copy_default_to_draft(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    draft = service.create_capability_draft(
        "biz_fission_old",
        BusinessCapabilityDraftCreateRequest(note="调整重绘幅度默认值"),
    )

    assert draft["business_key"] == "fission"
    assert draft["version"] == "old-draft"
    assert draft["status"] == "draft"
    assert draft["is_default"] is False
    assert draft["recipe"]["primaryAbilityId"] == "ability_openai_fission"
    assert draft["input_schema"] is None
    assert draft["extra_metadata"]["draftInfo"]["sourceCapabilityId"] == "biz_fission_old"
    assert draft["version_lineage"]["parentVersionId"] == "biz_fission_old"
    assert draft["version_lineage"]["decision"] == "version_upgrade"


def test_business_capability_draft_recipe_update_is_isolated(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    draft = service.create_capability_draft(
        "biz_fission_old",
        BusinessCapabilityDraftCreateRequest(version="old-draft-edit", note="复制为草稿"),
    )

    updated = service.update_capability_draft_recipe(
        draft["id"],
        BusinessCapabilityDraftRecipeUpdateRequest(
            recipe={
                "mode": "vl_then_primary",
                "primaryAbilityId": "ability_openai_fission",
                "steps": [
                    {
                        "id": "vl",
                        "type": "vl_analyze_image",
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
            note="增加 VL 预处理",
        ),
    )

    assert updated["id"] == draft["id"]
    assert updated["status"] == "draft"
    assert updated["is_default"] is False
    assert updated["recipe"]["mode"] == "vl_then_primary"
    assert len(updated["recipe"]["steps"]) == 2
    assert "处理步骤数量：1 -> 2" in updated["extra_metadata"]["draftInfo"]["lastRecipeDiff"]

    original = {item["id"]: item for item in service.list_capabilities()}["biz_fission_old"]
    assert original["is_default"] is True
    assert original["recipe"]["mode"] == "single_ability_task"
    assert len(original["recipe"]["steps"]) == 1


def test_business_capability_draft_recipe_update_rejects_non_draft(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with pytest.raises(HTTPException) as exc_info:
        service.update_capability_draft_recipe(
            "biz_fission_old",
            BusinessCapabilityDraftRecipeUpdateRequest(
                recipe={"primaryAbilityId": "ability_openai_fission"},
                note="不能直接改线上默认",
            ),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "BUSINESS_DRAFT_ONLY_EDITABLE"


def test_business_capability_draft_validate_lists_publish_blockers(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
    service = BusinessRunService()
    draft = service.create_capability_draft(
        "biz_fission_old",
        BusinessCapabilityDraftCreateRequest(version="old-draft-validate", note="准备校验"),
    )

    validation = service.validate_capability_draft(draft["id"])

    assert validation["can_publish"] is False
    assert validation["default_capability"]["id"] == "biz_fission_old"
    assert "配方结构未变化，仅更新了格式或说明。" in validation["diff_summary"]
    failed_codes = {item["code"] for item in validation["checks"] if not item["passed"]}
    assert "BUSINESS_DRAFT_REAL_RUN_PASSED" in failed_codes
    assert "BUSINESS_DRAFT_ACCEPTANCE_PASSED" in failed_codes
    assert validation["release_gate"]["status"] == "blocked"


def test_business_capability_draft_publish_requires_real_run_and_acceptance(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
    service = BusinessRunService()
    draft = service.create_capability_draft(
        "biz_fission_old",
        BusinessCapabilityDraftCreateRequest(version="old-draft-publish", note="准备发布"),
    )

    with pytest.raises(HTTPException) as blocked_exc:
        service.publish_capability_draft(draft["id"], BusinessCapabilityDraftPublishRequest(note="缺少真实测试"))
    assert blocked_exc.value.status_code == 409
    assert blocked_exc.value.detail == "BUSINESS_RELEASE_GATE_BLOCKED"

    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_draft_publish_success",
                business_key="fission",
                business_version_id=draft["id"],
                version=draft["version"],
                status="succeeded",
                source="admin-draft-run",
                channel="release-smoke",
                ability_id="ability_openai_fission",
                image_urls=["https://example.com/result.png"],
                result_payload={"imageUrls": ["https://example.com/result.png"]},
                created_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
        )
        session.commit()
    service.record_acceptance(
        draft["id"],
        BusinessAcceptanceRecordRequest(status="passed", note="草稿真实链路验收通过"),
    )

    validation = service.validate_capability_draft(draft["id"])
    assert validation["can_publish"] is True
    assert validation["release_gate"]["status"] == "ready"

    published = service.publish_capability_draft(
        draft["id"],
        BusinessCapabilityDraftPublishRequest(note="草稿验证通过，发布为默认版本"),
    )

    listed = {item["id"]: item for item in service.list_capabilities()}
    assert published["id"] == draft["id"]
    assert published["status"] == "active"
    assert published["is_default"] is True
    assert listed["biz_fission_old"]["is_default"] is False


def test_business_capability_update_switches_default(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
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
    service.record_acceptance(
        created["id"],
        BusinessAcceptanceRecordRequest(status="passed", note="切默认前验收通过"),
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
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
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
    service.record_acceptance(
        created["id"],
        BusinessAcceptanceRecordRequest(status="passed", note="测评通过"),
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


def test_business_capability_records_manual_acceptance(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    actor = User(
        id="admin_user_1",
        email="admin@example.com",
        username="admin",
        password_hash="x",
        role="admin",
        status="active",
    )

    accepted = service.record_acceptance(
        "biz_fission_old",
        BusinessAcceptanceRecordRequest(
            status="passed",
            note="测评端真实链路通过",
            evidenceRunId="run_acceptance_1",
            evidenceUrl="https://example.com/acceptance",
            checklist={"coze": True, "callback": True, "oss": True},
        ),
        actor=actor,
    )

    assert accepted["latest_acceptance"]["status"] == "passed"
    assert accepted["latest_acceptance"]["note"] == "测评端真实链路通过"
    assert accepted["latest_acceptance"]["evidenceRunId"] == "run_acceptance_1"
    assert accepted["latest_acceptance"]["actorUsername"] == "admin"
    assert accepted["acceptance_records"][0]["checklist"]["callback"] is True
    assert accepted["extra_metadata"]["latestAcceptance"]["status"] == "passed"
    assert accepted["release_gate"]["acceptancePassed"] is True

    listed = {item["id"]: item for item in service.list_capabilities()}
    assert listed["biz_fission_old"]["latest_acceptance"]["status"] == "passed"
    assert listed["biz_fission_old"]["release_gate"]["acceptancePassed"] is True
    actions = [item["action"] for item in service.list_operation_logs(business_key="fission")]
    assert "record_acceptance" in actions


def test_business_default_switch_requires_manual_acceptance(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="needs-acceptance",
            displayName="待验收图裂变",
            status="active",
            isDefault=False,
            primaryAbilityId="ability_openai_fission",
        )
    )

    with pytest.raises(HTTPException) as approval_exc:
        service.create_default_approval(
            created["id"],
            BusinessDefaultApprovalCreateRequest(note="未验收，不能申请切默认"),
        )
    assert approval_exc.value.status_code == 409
    assert approval_exc.value.detail == "BUSINESS_ACCEPTANCE_REQUIRED"

    with pytest.raises(HTTPException) as promote_exc:
        service.promote_capability(
            created["id"],
            BusinessCapabilityPromoteRequest(note="未验收，不能直接设默认"),
        )
    assert promote_exc.value.status_code == 409
    assert promote_exc.value.detail == "BUSINESS_ACCEPTANCE_REQUIRED"


def test_business_capability_rejects_invalid_acceptance_status(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with pytest.raises(HTTPException) as exc_info:
        service.record_acceptance(
            "biz_fission_old",
            BusinessAcceptanceRecordRequest(status="unknown"),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "BUSINESS_ACCEPTANCE_STATUS_INVALID"


def test_business_default_approval_approves_default_and_records_operation_log(monkeypatch) -> None:
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
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
    service.record_acceptance(
        created["id"],
        BusinessAcceptanceRecordRequest(status="passed", note="真实链路验收通过"),
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
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
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
    service.record_acceptance(
        created["id"],
        BusinessAcceptanceRecordRequest(status="passed", note="灰度验证通过"),
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
    install_business_db(monkeypatch, with_vendor_cost=True, with_vendor_key=True, with_vendor_acceptance=True)
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
    service.record_acceptance(
        created["id"],
        BusinessAcceptanceRecordRequest(status="passed", note="指定回滚前验收通过"),
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
    assert created["version_lineage"]["decision"] == "version_upgrade"
    assert "同一业务入口" in created["version_lineage"]["decisionNote"]
    assert created["orchestration_graph"]["summary"]["hasVlStep"] is True
    assert [edge["target"] for edge in created["orchestration_graph"]["edges"]] == ["vl", "primary", "result"]


def test_business_capability_lineage_infers_rollback_when_old_metadata_unknown(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    created = service.create_capability(
        BusinessCapabilityCreateRequest(
            businessKey="fission",
            version="rollback-e7-v1",
            displayName="图裂变 · E7 保底版",
            status="active",
            primaryAbilityId="ability_openai_fission",
            metadata={"versionLineage": {"decision": "unknown"}},
        )
    )

    assert created["version_lineage"]["decision"] == "rollback"
    assert created["version_lineage"]["decisionNote"] == "保底回滚版本，只在主线异常时切回，不作为新业务入口。"


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
    assert run["orchestration_graph"]["mode"] == "run"
    assert run["orchestration_graph"]["summary"]["currentNodeId"] == "primary"
    assert [node["id"] for node in run["orchestration_graph"]["nodes"]] == ["entry", "primary", "result"]


def test_business_admin_draft_run_uses_selected_draft_capability(monkeypatch) -> None:
    install_business_db(monkeypatch)

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_draft",
                business_key="fission",
                version="draft-v2",
                display_name="草稿图裂变",
                status="draft",
                is_default=False,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
            )
        )
        session.commit()

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert ability_id == "ability_openai_fission"
            assert payload.metadata["businessVersion"] == "draft-v2"
            assert payload.metadata["businessRoute"]["selectedBy"] == "admin_draft"
            return {"id": "task_draft_1", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    run = service.create_run_for_capability(
        capability_id="biz_fission_draft",
        payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", channel="admin-web"),
        user=None,
    )

    assert run["version"] == "draft-v2"
    assert run["business_version_id"] == "biz_fission_draft"
    assert run["source"] == "admin-draft-run"
    assert run["channel"] == "admin-web"
    assert run["request_payload"]["_route"]["selectedBy"] == "admin_draft"
    assert run["ability_task_id"] == "t1.fission.auto.task_draft_1"


def test_business_public_run_does_not_select_draft_version(monkeypatch) -> None:
    install_business_db(monkeypatch)

    with business_runs_module.get_session() as session:
        session.add(
            BusinessCapability(
                id="biz_fission_draft",
                business_key="fission",
                version="draft-v2",
                display_name="草稿图裂变",
                status="draft",
                is_default=False,
                recipe={
                    "mode": "single_ability_task",
                    "primaryAbilityId": "ability_openai_fission",
                    "steps": [{"id": "primary", "type": "ability_task", "abilityId": "ability_openai_fission"}],
                },
            )
        )
        session.commit()

    service = BusinessRunService()

    with pytest.raises(HTTPException) as exc_info:
        service.create_run(
            business_key="fission",
            payload=BusinessRunCreateRequest(imageUrl="https://example.com/a.png", version="draft-v2"),
            user=None,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "BUSINESS_CAPABILITY_NOT_FOUND"


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
    assert fetched["billing_status"] == "billable"
    assert fetched["chargeable"] is True
    assert fetched["no_charge_reason"] is None
    assert fetched["image_urls"] == ["https://example.com/result.png"]
    primary_step = fetched["steps"][0]
    assert primary_step["duration_ms"] == 3000
    assert primary_step["cost_amount"] == 0.24
    assert primary_step["quota_units"] == 12


def test_external_business_identity_does_not_write_platform_user_fk() -> None:
    service = BusinessRunService()
    payload = BusinessRunCreateRequest(
        imageUrl="https://example.com/input.png",
        tenantId="tenant-a",
        clientId="client-a",
        userId="external-user-1",
        metadata={"user_id": "external-user-2"},
        inputs={"account_id": "external-user-3"},
    )
    service_user = User(
        id="service",
        email="service@podi.internal",
        username="service",
        password_hash="",
        role="admin",
        status="active",
    )
    platform_user = User(
        id="platform-user-1",
        email="client@example.com",
        username="client",
        password_hash="",
        role="client",
        status="active",
    )

    assert (
        service._resolve_business_user_id(
            user=service_user,
            payload=payload,
            trace_context={"tenantId": "tenant-a", "clientId": "client-a"},
        )
        is None
    )
    assert (
        service._resolve_business_user_id(
            user=None,
            payload=payload,
            trace_context={"tenantId": "tenant-a", "clientId": "client-a"},
        )
        is None
    )
    assert (
        service._resolve_business_user_id(
            user=platform_user,
            payload=payload,
            trace_context={"tenantId": "tenant-a", "clientId": "client-a"},
        )
        == "platform-user-1"
    )


def test_internal_patrol_run_is_no_charge_even_when_costed(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    now = datetime.utcnow()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_internal_patrol_costed",
                business_key="fission",
                business_version_id="biz_fission_old",
                version="old",
                status="succeeded",
                source="business-api-patrol",
                channel="release-smoke",
                tenant_id="podi-internal-patrol",
                client_id="business-api-patrol",
                ability_id="ability_openai_fission",
                image_urls=["https://example.com/patrol.png"],
                cost_amount=0.12,
                currency="USD",
                quota_units=1,
                request_payload={
                    "metadata": {"patrol": True},
                    "_trace": {
                        "source": "business-api-patrol",
                        "tenantId": "podi-internal-patrol",
                        "clientId": "business-api-patrol",
                    },
                },
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    fetched = service.get_run(run_id="run_internal_patrol_costed", user=None)
    assert fetched["billing_status"] == "no_charge"
    assert fetched["chargeable"] is False
    assert fetched["no_charge_reason"] == "内部巡检任务，不进入业务收费账单"

    total, items = service.list_runs(business_key="fission", billing_status="no_charge", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_internal_patrol_costed"

    total, items = service.list_runs(business_key="fission", billing_status="billable", limit=20)
    assert total == 0
    assert items == []


def test_internal_realtest_run_is_no_charge_without_cost_policy(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    now = datetime.utcnow()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_internal_realtest_unpriced",
                business_key="fission_evaluate",
                business_version_id="biz_fission_evaluate_v1",
                version="v1",
                status="succeeded",
                source="partner-api",
                channel="open-api",
                tenant_id="podi-internal-realtest",
                client_id="codex-realtest",
                ability_id="vl_fission_generated_image_evaluate",
                texts=['{"decision":"pass","score":86}'],
                request_payload={
                    "_trace": {
                        "source": "partner-api",
                        "tenantId": "podi-internal-realtest",
                        "clientId": "codex-realtest",
                    },
                },
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    fetched = service.get_run(run_id="run_internal_realtest_unpriced", user=None)
    assert fetched["billing_status"] == "no_charge"
    assert fetched["chargeable"] is False
    assert fetched["no_charge_reason"] == "内部巡检任务，不进入业务收费账单"

    summary = service.usage_summary(window_hours=24, business_key="fission_evaluate")
    assert summary["unpriced"] == 0
    assert summary["no_charge"] == 1
    assert summary["unresolved_issues"] == []


def test_business_run_derives_cost_from_vendor_model_policy(monkeypatch) -> None:
    vendor_model_id = install_business_db(monkeypatch)

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert ability_id == "ability_openai_fission"
            return {"id": "task_policy_cost", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        model = session.get(VendorModelCatalog, vendor_model_id)
        model.cost_policy = {
            "billingUnit": "image",
            "unitPrice": 0.11,
            "currency": "USD",
            "quotaUnits": 3,
            "pricingVersion": "model-v1",
        }
        session.add(model)
        session.commit()

    run = service.create_run(
        business_key="fission",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/a.png",
            version="old",
            userId="user_policy_cost",
        ),
        user=None,
    )

    with business_runs_module.get_session() as session:
        session.add(
            AbilityTask(
                id="task_policy_cost",
                ability_id="ability_openai_fission",
                ability_name="GPT Image 2 图裂变",
                ability_provider="openai",
                capability_key="gpt_image_2_fission",
                status="succeeded",
                duration_ms=2000,
                result_payload={
                    "images": [
                        {"url": "https://example.com/result-a.png"},
                        {"url": "https://example.com/result-b.png"},
                    ],
                },
            )
        )
        session.commit()

    fetched = service.get_run(run_id=run["id"], user=None)

    assert fetched["billing_unit"] == "image"
    assert fetched["unit_price"] == 0.11
    assert fetched["cost_amount"] == 0.22
    assert fetched["currency"] == "USD"
    assert fetched["quota_units"] == 3
    assert fetched["billing_status"] == "billable"
    assert fetched["cost_breakdown"]["costPolicySource"] == "vendor_model"
    assert fetched["cost_breakdown"]["costPolicyQuantity"] == 2
    assert fetched["cost_breakdown"]["pricingVersion"] == "model-v1"


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
                    cost_amount=0.2,
                    currency="USD",
                    quota_units=1,
                    callback_status="success",
                ),
                BusinessRun(
                    id="run_fission_v2_fail",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="v2",
                    status="failed",
                    ability_id="ability_openai_fission",
                    cost_amount=0.1,
                    currency="USD",
                    quota_units=1,
                    callback_status="failed",
                    error_message="TASK_FAILED",
                ),
                BusinessRun(
                    id="run_fission_output_missing",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    source="coze",
                    ability_id="ability_openai_fission",
                ),
                BusinessRun(
                    id="run_fission_callback_fail",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    source="coze",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/callback.png"],
                    callback_status="failed",
                    callback_error="HTTP 500",
                ),
                BusinessRun(
                    id="run_fission_billing_unpriced",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="billing",
                    status="succeeded",
                    source="billing-test",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/billing.png"],
                ),
                BusinessRun(
                    id="run_fission_structured_ok",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="structured",
                    status="succeeded",
                    source="business-api",
                    ability_id="ability_openai_fission",
                    result_payload={"jsonOutput": {"tags": ["蓝色", "植物"]}},
                    cost_amount=0.1,
                    currency="USD",
                    quota_units=1,
                ),
                BusinessRun(
                    id="run_fission_resource_ok",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="resource",
                    status="succeeded",
                    source="business-api",
                    ability_id="ability_openai_fission",
                    result_payload={
                        "resources": ["https://example.com/export.zip"],
                        "assets": [{"type": "file", "ossUrl": "https://example.com/export.zip"}],
                    },
                    cost_amount=0.1,
                    currency="USD",
                    quota_units=1,
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
    assert items[0]["billing_status"] == "billable"
    assert items[0]["chargeable"] is True

    total, items = service.list_runs(
        business_key="fission",
        billing_status="no_charge",
        callback_status="failed",
        limit=20,
    )

    assert total == 1
    assert [item["id"] for item in items] == ["run_fission_v2_fail"]
    assert items[0]["billing_status"] == "no_charge"
    assert items[0]["chargeable"] is False
    assert items[0]["no_charge_reason"] == "任务失败，不向业务方计费"

    total, items = service.list_runs(business_key="fission", issue_category="output", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_fission_output_missing"
    assert items[0]["issue_category"] == "output"
    assert items[0]["flow_summary"]["issueLabel"] == "结果回填问题"

    total, items = service.list_runs(business_key="fission", issue_category="callback", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_fission_callback_fail"
    assert items[0]["issue_label"] == "业务回调问题"

    total, items = service.list_runs(business_key="fission", issue_category="billing", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_fission_billing_unpriced"
    assert items[0]["issue_label"] == "计费扣减问题"
    assert items[0]["issue_evidence"] == "任务成功但缺少定价，待确认计费口径"

    total, items = service.list_runs(business_key="fission", version="structured", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_fission_structured_ok"
    assert items[0]["issue_category"] == "none"
    assert items[0]["flow_summary"]["output"]["hasOutput"] is True
    assert items[0]["flow_summary"]["output"]["structuredCount"] == 1

    total, items = service.list_runs(business_key="fission", version="resource", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_fission_resource_ok"
    assert items[0]["issue_category"] == "none"
    assert items[0]["flow_summary"]["output"]["hasOutput"] is True
    assert items[0]["flow_summary"]["output"]["resourceCount"] == 1

    total, items = service.list_runs(business_key="fission", issue_category="executor", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_fission_v2_fail"


def test_business_run_list_marks_billable_user_without_settlement_as_billing_issue(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_billable_user_without_settlement",
                business_key="fission",
                business_version_id="biz_fission_old",
                version="v1",
                status="succeeded",
                source="business-api",
                ability_id="ability_openai_fission",
                user_id="tenant-a",
                image_urls=["https://example.com/result.png"],
                cost_amount=0.35,
                currency="CNY",
                quota_units=1,
            )
        )
        session.commit()

    total, items = service.list_runs(business_key="fission", issue_category="billing", limit=20)

    assert total == 1
    assert items[0]["id"] == "run_billable_user_without_settlement"
    assert items[0]["issue_label"] == "计费扣减问题"
    assert items[0]["issue_evidence"] == "任务应计费但未发现套餐或钱包扣减流水"


def test_business_run_callback_retry_and_bulk_ignore(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    class FakeResponse:
        status_code = 200
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    posted: list[dict] = []

    def fake_post(url, *, json, headers, timeout):
        posted.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(business_runs_module.httpx, "post", fake_post)

    with business_runs_module.get_session() as session:
        session.add_all(
            [
                BusinessRun(
                    id="run_callback_failed",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    source="coze",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/result.png"],
                    callback_url="https://callback.example.com/podi",
                    callback_headers={"x-token": "demo"},
                    callback_status="failed",
                    callback_error="HTTP_500",
                ),
                BusinessRun(
                    id="run_output_missing_for_ignore",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    source="coze",
                    ability_id="ability_openai_fission",
                ),
            ]
        )
        session.commit()

    retried = service.retry_callback("run_callback_failed")
    assert retried["callback_status"] == "success"
    assert retried["callback_error"] is None
    assert posted[0]["url"] == "https://callback.example.com/podi"
    assert posted[0]["json"]["runId"] == "run_callback_failed"

    bulk = service.bulk_retry_callbacks(["run_callback_failed"], only_failed=True)
    assert bulk["failed"] == 1
    assert bulk["items"][0]["status"] == "skipped"

    total, items = service.list_runs(business_key="fission", issue_category="output", limit=20)
    assert total == 1
    assert items[0]["id"] == "run_output_missing_for_ignore"

    ignored = service.mark_issues_ignored(["run_output_missing_for_ignore"], note="测试确认无需继续处理")
    assert ignored["succeeded"] == 1
    total, items = service.list_runs(business_key="fission", issue_category="none", limit=20)
    ignored_row = next(item for item in items if item["id"] == "run_output_missing_for_ignore")
    assert ignored_row["issue_label"] == "已标记无需处理"
    assert ignored_row["issue_action"] == "测试确认无需继续处理"


def test_business_run_issue_checklist_generates_markdown(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add_all(
            [
                BusinessRun(
                    id="run_executor_failed",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="failed",
                    source="coze",
                    ability_id="ability_openai_fission",
                    error_message="COMFYUI_EXECUTOR_UNREACHABLE",
                ),
                BusinessRun(
                    id="run_ok",
                    business_key="fission",
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    source="coze",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/result.png"],
                    cost_amount=0.2,
                    currency="USD",
                    quota_units=1,
                ),
            ]
        )
        session.commit()

    report = service.generate_issue_checklist(["run_executor_failed", "run_ok"], only_failed=True)

    assert report["total"] == 2
    assert report["issue_count"] == 1
    assert report["skipped_count"] == 1
    assert report["by_category"] == {"executor": 1}
    assert report["by_severity"] == {"danger": 1}
    assert report["items"][0]["run_id"] == "run_executor_failed"
    assert report["items"][0]["issue_label"] == "执行节点问题"
    assert "COMFYUI_EXECUTOR_UNREACHABLE" in report["markdown"]
    assert "检查执行节点健康" in report["markdown"]


def test_business_run_billing_retry_and_refund_are_idempotent(monkeypatch) -> None:
    install_business_db(monkeypatch)
    wallet_service.reset()
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_billing_retry",
                business_key="fission",
                business_version_id="biz_fission_old",
                version="old",
                status="succeeded",
                source="coze",
                tenant_id="tenant-a",
                client_id="client-web",
                user_id="user_billing_retry",
                ability_id="ability_openai_fission",
                image_urls=["https://example.com/result.png"],
                cost_amount=0.24,
                currency="USD",
            )
        )
        session.commit()

    settled = service.retry_billing("run_billing_retry")
    settlement = settled["cost_breakdown"]["walletSettlement"]
    assert settlement["status"] == "settled"
    assert settlement["points"] == 24
    assert settlement["idempotent"] is False

    repeated = service.retry_billing("run_billing_retry")
    repeated_settlement = repeated["cost_breakdown"]["walletSettlement"]
    assert repeated_settlement["status"] == "settled"
    assert repeated_settlement["idempotent"] is True

    ledger = wallet_service.ledger("user_billing_retry", page=1, page_size=10)
    assert ledger["total"] == 1
    assert ledger["items"][0]["points"] == -24
    assert ledger["items"][0]["traceId"] == "business_run:run_billing_retry"

    refunded = service.refund_billing("run_billing_retry")
    refund_settlement = refunded["cost_breakdown"]["walletSettlement"]
    assert refund_settlement["status"] == "refunded"
    assert refund_settlement["refundIdempotent"] is False

    repeated_refund = service.refund_billing("run_billing_retry")
    repeated_refund_settlement = repeated_refund["cost_breakdown"]["walletSettlement"]
    assert repeated_refund_settlement["status"] == "refunded"
    assert repeated_refund_settlement["refundIdempotent"] is True

    ledger_after_refund = wallet_service.ledger("user_billing_retry", page=1, page_size=10)
    assert ledger_after_refund["total"] == 2
    assert sum(item["points"] for item in ledger_after_refund["items"]) == 0

    rebilled = service.retry_billing("run_billing_retry")
    rebilled_settlement = rebilled["cost_breakdown"]["walletSettlement"]
    assert rebilled_settlement["status"] == "settled"
    assert rebilled_settlement["billingAttempt"] == 2
    assert rebilled_settlement["idempotent"] is False

    ledger_after_rebill = wallet_service.ledger("user_billing_retry", page=1, page_size=10)
    assert ledger_after_rebill["total"] == 3
    assert sum(item["points"] for item in ledger_after_rebill["items"]) == -24

    refunded_again = service.refund_billing("run_billing_retry")
    assert refunded_again["cost_breakdown"]["walletSettlement"]["refundIdempotent"] is False
    ledger_after_second_refund = wallet_service.ledger("user_billing_retry", page=1, page_size=10)
    assert ledger_after_second_refund["total"] == 4
    assert sum(item["points"] for item in ledger_after_second_refund["items"]) == 0

    logs = service.list_operation_logs(target_type="business_run", business_key="fission", limit=10)
    actions = [item["action"] for item in logs]
    assert "retry_billing" in actions
    assert "refund_billing" in actions


def test_business_run_billing_prefers_package_before_wallet(monkeypatch) -> None:
    install_business_db(monkeypatch)
    wallet_service.reset()
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        now = datetime.utcnow()
        session.add(
            PackageBalance(
                user_id="user_package_bill",
                package_key="fission-basic",
                package_name="图裂变基础包",
                business_key="fission",
                total_units=5,
                used_units=0,
                frozen_units=0,
                unit_name="次",
                status="active",
                source="manual",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            BusinessRun(
                id="run_package_billing",
                business_key="fission",
                business_version_id="biz_fission_old",
                version="old",
                status="succeeded",
                source="coze",
                tenant_id="tenant-a",
                client_id="client-web",
                user_id="user_package_bill",
                ability_id="ability_openai_fission",
                image_urls=["https://example.com/result.png"],
                quota_units=2,
                cost_amount=0.24,
                currency="USD",
            )
        )
        session.commit()

    settled = service.retry_billing("run_package_billing")
    package_settlement = settled["cost_breakdown"]["packageSettlement"]
    assert package_settlement["status"] == "settled"
    assert package_settlement["method"] == "package"
    assert package_settlement["units"] == 2
    assert settled["cost_breakdown"]["billingSettlement"]["method"] == "package"
    assert wallet_service.ledger("user_package_bill", page=1, page_size=10)["total"] == 0

    repeated = service.retry_billing("run_package_billing")
    assert repeated["cost_breakdown"]["packageSettlement"]["idempotent"] is True

    with business_runs_module.get_session() as session:
        balance = session.execute(
            select(PackageBalance).where(PackageBalance.user_id == "user_package_bill")
        ).scalars().first()
        assert balance.used_units == 2
        ledger_count = session.execute(
            select(func.count(PackageLedger.id)).where(PackageLedger.user_id == "user_package_bill")
        ).scalar_one()
        assert ledger_count == 1

    refunded = service.refund_billing("run_package_billing")
    refund_settlement = refunded["cost_breakdown"]["packageSettlement"]
    assert refund_settlement["status"] == "refunded"
    assert refund_settlement["refundIdempotent"] is False
    assert refunded["cost_breakdown"]["billingSettlement"]["status"] == "refunded"

    repeated_refund = service.refund_billing("run_package_billing")
    assert repeated_refund["cost_breakdown"]["packageSettlement"]["refundIdempotent"] is True

    with business_runs_module.get_session() as session:
        balance = session.execute(
            select(PackageBalance).where(PackageBalance.user_id == "user_package_bill")
        ).scalars().first()
        assert balance.used_units == 0
        ledger_count = session.execute(
            select(func.count(PackageLedger.id)).where(PackageLedger.user_id == "user_package_bill")
        ).scalar_one()
        assert ledger_count == 2

    rebilled = service.retry_billing("run_package_billing")
    rebilled_settlement = rebilled["cost_breakdown"]["packageSettlement"]
    assert rebilled_settlement["status"] == "settled"
    assert rebilled_settlement["billingAttempt"] == 2
    assert rebilled_settlement["idempotent"] is False

    with business_runs_module.get_session() as session:
        balance = session.execute(
            select(PackageBalance).where(PackageBalance.user_id == "user_package_bill")
        ).scalars().first()
        assert balance.used_units == 2
        ledger_count = session.execute(
            select(func.count(PackageLedger.id)).where(PackageLedger.user_id == "user_package_bill")
        ).scalar_one()
        assert ledger_count == 3

    refunded_again = service.refund_billing("run_package_billing")
    assert refunded_again["cost_breakdown"]["packageSettlement"]["refundIdempotent"] is False

    with business_runs_module.get_session() as session:
        balance = session.execute(
            select(PackageBalance).where(PackageBalance.user_id == "user_package_bill")
        ).scalars().first()
        assert balance.used_units == 0
        ledger_count = session.execute(
            select(func.count(PackageLedger.id)).where(PackageLedger.user_id == "user_package_bill")
        ).scalar_one()
        assert ledger_count == 4


def test_business_run_billing_errors(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add_all(
            [
                BusinessRun(
                    id="run_billing_unpriced",
                    business_key="fission",
                    version="old",
                    status="succeeded",
                    user_id="user_billing_unpriced",
                ),
                BusinessRun(
                    id="run_billing_failed",
                    business_key="fission",
                    version="old",
                    status="failed",
                    user_id="user_billing_failed",
                    cost_amount=0.2,
                    currency="USD",
                ),
                BusinessRun(
                    id="run_billing_no_user",
                    business_key="fission",
                    version="old",
                    status="succeeded",
                    cost_amount=0.2,
                    currency="USD",
                ),
            ]
        )
        session.commit()

    with pytest.raises(HTTPException) as unpriced_exc:
        service.retry_billing("run_billing_unpriced")
    assert unpriced_exc.value.status_code == 409
    assert unpriced_exc.value.detail == "BUSINESS_RUN_UNPRICED"

    with pytest.raises(HTTPException) as failed_exc:
        service.retry_billing("run_billing_failed")
    assert failed_exc.value.status_code == 409
    assert failed_exc.value.detail == "BUSINESS_RUN_NOT_BILLABLE"

    with pytest.raises(HTTPException) as no_user_exc:
        service.retry_billing("run_billing_no_user")
    assert no_user_exc.value.status_code == 400
    assert no_user_exc.value.detail == "BUSINESS_RUN_USER_REQUIRED"

    with pytest.raises(HTTPException) as refund_missing_exc:
        service.refund_billing("run_billing_failed")
    assert refund_missing_exc.value.status_code == 409
    assert refund_missing_exc.value.detail == "BUSINESS_WALLET_SETTLEMENT_NOT_FOUND"


def test_business_run_retest_creates_new_run_without_business_callback(monkeypatch) -> None:
    install_business_db(monkeypatch)
    captured_payloads = []

    class FakeAbilityTaskService:
        def enqueue(self, *, ability_id, payload, user):
            assert ability_id == "ability_openai_fission"
            captured_payloads.append(payload)
            return {"id": f"task_retest_{len(captured_payloads)}", "status": "queued"}

    monkeypatch.setattr(business_runs_module, "get_ability_task_service", lambda: FakeAbilityTaskService())
    service = BusinessRunService()

    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_need_retest",
                business_key="fission",
                business_version_id="biz_fission_old",
                version="old",
                status="failed",
                source="coze",
                channel="coze-workflow",
                trace_id="trace-old",
                request_id="request-old",
                tenant_id="tenant-a",
                client_id="client-a",
                ability_id="ability_openai_fission",
                request_payload={
                    "imageUrl": "https://example.com/input.png",
                    "version": "old",
                    "prompt": "复测这个图裂变",
                    "bili": 60,
                    "source": "coze",
                    "channel": "coze-workflow",
                    "tenantId": "tenant-a",
                    "clientId": "client-a",
                    "callbackUrl": "https://callback.example.com/old",
                    "callbackHeaders": {"x-token": "old"},
                    "metadata": {"scene": "workflow"},
                    "_trace": {"traceId": "trace-old"},
                },
                error_message="executor timeout",
            )
        )
        session.commit()

    retested = service.retest_run("run_need_retest")

    assert retested["id"] != "run_need_retest"
    assert retested["status"] == "queued"
    assert retested["source"] == "admin-retest"
    assert retested["channel"] == "manual-retest"
    assert retested["tenant_id"] == "tenant-a"
    assert retested["client_id"] == "client-a"
    assert retested["callback_status"] is None
    assert "callbackUrl" not in retested["request_payload"]
    assert "callbackHeaders" not in retested["request_payload"]
    assert retested["request_payload"]["metadata"]["adminRetest"]["sourceRunId"] == "run_need_retest"
    assert captured_payloads[0].imageUrl == "https://example.com/input.png"
    assert captured_payloads[0].inputs["bili"] == 60
    assert captured_payloads[0].metadata["source"] == "admin-retest"

    source_after_retest = service.get_run(run_id="run_need_retest")
    assert source_after_retest["retest_attempts"] == 1
    assert source_after_retest["retest_latest_run_id"] == retested["id"]
    assert source_after_retest["retest_latest_status"] == "queued"
    assert source_after_retest["retest_recovered"] is False
    assert retested["retest_source_run_id"] == "run_need_retest"

    summary = service.usage_summary(window_hours=24)
    assert summary["unresolved_issues"][0]["key"] == "executor"
    assert summary["unresolved_issues"][0]["retested"] == 1
    assert summary["recent_unresolved_issues"][0]["id"] == "run_need_retest"
    assert summary["recent_unresolved_issues"][0]["retest_latest_run_id"] == retested["id"]

    with business_runs_module.get_session() as session:
        row = session.get(BusinessRun, retested["id"])
        row.status = "succeeded"
        row.image_urls = ["https://example.com/retest-result.png"]
        row.finished_at = datetime.utcnow()
        session.add(row)
        session.commit()

    recovered_source = service.get_run(run_id="run_need_retest")
    assert recovered_source["retest_recovered"] is True
    summary_after_recovered = service.usage_summary(window_hours=24)
    assert all(item["id"] != "run_need_retest" for item in summary_after_recovered["recent_unresolved_issues"])

    bulk = service.bulk_retest_runs(["run_need_retest"], only_failed=True)
    assert bulk["failed"] == 1
    assert bulk["items"][0]["status"] == "skipped"


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
                    business_version_id="biz_fission_old",
                    version="old",
                    status="succeeded",
                    source="coze",
                    channel="coze-workflow",
                    tenant_id="tenant-a",
                    client_id="client-web",
                    trace_id="trace-usage-1",
                    ability_id="ability_openai_fission",
                    image_urls=["https://example.com/usage-ok.png"],
                    duration_ms=2000,
                    cost_amount=0.2,
                    currency="USD",
                    quota_units=1,
                    callback_status="success",
                    created_at=now - timedelta(minutes=10),
                ),
                BusinessRun(
                    id="run_usage_fail",
                    business_key="fission",
                    business_version_id="biz_fission_old",
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
                    callback_status="failed",
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
    assert summary["cost_by_currency"] == {"USD": 0.2}
    assert summary["actual_cost_by_currency"] == {"USD": 0.3}
    assert summary["quota_units"] == 1
    assert summary["actual_quota_units"] == 2
    assert summary["billable"] == 1
    assert summary["no_charge"] == 1
    assert summary["unpriced"] == 0
    assert summary["billing_pending"] == 0
    assert summary["callback_success"] == 1
    assert summary["callback_failed"] == 1
    assert summary["callback_running"] == 0
    assert summary["callback_missing"] == 0
    assert summary["by_business"][0]["key"] == "fission"
    assert summary["by_business"][0]["cost_by_currency"] == {"USD": 0.2}
    assert summary["by_business"][0]["actual_cost_by_currency"] == {"USD": 0.3}
    assert summary["by_source"][0]["key"] == "coze"
    assert summary["by_tenant"][0]["key"] == "tenant-a"
    assert summary["by_client"][0]["key"] == "client-web"
    assert {item["key"]: item["total"] for item in summary["by_issue"]} == {"executor": 1, "none": 1}
    assert summary["recent_failures"][0]["id"] == "run_usage_fail"
    validated = BusinessUsageSummaryResponse.model_validate(summary).model_dump(by_alias=False)
    assert validated["byIssue"][0]["label"] == "执行节点问题"
    assert validated["recentFailures"][0]["runId"] == "run_usage_fail"

    trace_summary = service.usage_summary(window_hours=24, trace_id="trace-usage-2")
    assert trace_summary["total"] == 1
    assert trace_summary["cost_by_currency"] == {}
    assert trace_summary["actual_cost_by_currency"] == {"USD": 0.1}
    assert trace_summary["no_charge"] == 1
    assert trace_summary["recent_failures"][0]["trace_id"] == "trace-usage-2"

    issue_summary = service.usage_summary(window_hours=24, issue_category="executor")
    assert issue_summary["total"] == 1
    assert issue_summary["recent_failures"][0]["id"] == "run_usage_fail"


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
    assert fetched["orchestration_graph"]["summary"]["status"] == "succeeded"
    assert fetched["orchestration_graph"]["summary"]["output"]["hasOutput"] is True
    assert [node["id"] for node in fetched["orchestration_graph"]["nodes"]] == ["entry", "primary", "result"]
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


def test_business_client_user_cannot_override_bound_tenant(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    user = User(
        id="client_user_1",
        email="client@example.com",
        username="client",
        password_hash="x",
        role="client",
        status="active",
        tenant_id="tenant-a",
        client_id="client-a",
    )

    with pytest.raises(HTTPException) as exc_info:
        service._resolve_trace_context(
            run_id="run_1",
            business_key="fission",
            payload=BusinessRunCreateRequest(
                imageUrl="https://example.com/a.png",
                tenantId="tenant-b",
                clientId="client-a",
            ),
            source="business-api",
            user=user,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "BUSINESS_USER_SCOPE_FORBIDDEN"


def test_business_client_user_scope_overrides_payload_when_matching(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    user = User(
        id="client_user_1",
        email="client@example.com",
        username="client",
        password_hash="x",
        role="client",
        status="active",
        tenant_id="tenant-a",
        client_id="client-a",
    )

    trace = service._resolve_trace_context(
        run_id="run_1",
        business_key="fission",
        payload=BusinessRunCreateRequest(
            imageUrl="https://example.com/a.png",
            tenantId="tenant-a",
            clientId="client-a",
            metadata={"tenantId": "tenant-a", "clientId": "client-a"},
        ),
        source="business-api",
        user=user,
    )

    assert trace["tenantId"] == "tenant-a"
    assert trace["clientId"] == "client-a"


def test_business_client_user_can_read_service_run_in_own_scope(monkeypatch) -> None:
    install_business_db(monkeypatch)
    service = BusinessRunService()
    user = User(
        id="client_user_1",
        email="client@example.com",
        username="client",
        password_hash="x",
        role="client",
        status="active",
        tenant_id="tenant-a",
        client_id="client-a",
    )
    with business_runs_module.get_session() as session:
        session.add(
            BusinessRun(
                id="run_service_scope",
                business_key="fission",
                status="succeeded",
                source="coze",
                trace_id="trace_1",
                request_id="req_1",
                tenant_id="tenant-a",
                client_id="client-a",
                user_id="client-a",
                image_urls=["https://example.com/result.png"],
            )
        )
        session.commit()

    run = service.get_run(run_id="run_service_scope", user=user)

    assert run["id"] == "run_service_scope"
    assert run["tenant_id"] == "tenant-a"


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
