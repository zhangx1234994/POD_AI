from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.db import get_session
from app.models.integration import BusinessCapability, BusinessRun, BusinessRunStep
from app.schemas.business import (
    BusinessQualityActionRuleCreateRequest,
    BusinessQualityActionRuleUpdateRequest,
    BusinessOutputReviewUpsertItem,
    BusinessOutputReviewUpsertRequest,
    BusinessQualitySampleCreateRequest,
    BusinessQualitySampleImportItem,
    BusinessQualitySampleImportRequest,
    BusinessQualitySampleUpdateRequest,
)
from app.services.business_runs import BusinessRunService


def _make_run_id() -> str:
    return f"test_run_{uuid4().hex}"


def _insert_business_run(
    run_id: str,
    *,
    business_key: str = "fission",
    version: str = "v-test",
    batch_id: str | None = None,
    sample_key: str | None = None,
    sample_label: str | None = None,
) -> None:
    request_payload = {}
    if batch_id or sample_key or sample_label:
        request_payload = {
            "metadata": {
                "qualitySample": {
                    "batchId": batch_id,
                    "sampleKey": sample_key,
                    "sampleLabel": sample_label,
                }
            }
        }
    with get_session() as session:
        session.add(
            BusinessRun(
                id=run_id,
                business_key=business_key,
                business_version_id=None,
                version=version,
                status="succeeded",
                source="pytest",
                request_payload=request_payload,
                image_urls=["https://example.com/output-1.png"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                finished_at=datetime.utcnow(),
            )
        )
        session.commit()


def test_business_output_reviews_upsert_list_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    run_id = _make_run_id()
    _insert_business_run(run_id, batch_id="batch-test", sample_key="dense-pattern", sample_label="满版图案")

    payload = BusinessOutputReviewUpsertRequest(
        items=[
            BusinessOutputReviewUpsertItem(
                outputIndex=0,
                qualityGrade="bad",
                inputTags=["满版图案", "颜色敏感"],
                issueTags=["结构偏移"],
                nextAction="route_split",
                note="主体结构明显偏移。",
            )
        ]
    )

    upserted = service.upsert_output_reviews(run_id=run_id, payload=payload)
    assert upserted["total"] == 1
    assert upserted["items"][0]["run_id"] == run_id
    assert upserted["items"][0]["quality_grade"] == "bad"
    assert upserted["items"][0]["output_url"] == "https://example.com/output-1.png"
    assert upserted["items"][0]["batch_id"] == "batch-test"
    assert upserted["items"][0]["sample_key"] == "dense-pattern"
    assert upserted["items"][0]["sample_label"] == "满版图案"

    listed = service.list_output_reviews(run_id=run_id)
    assert listed["total"] == 1
    assert listed["items"][0]["issue_tags"] == ["结构偏移"]

    summary = service.output_review_summary(window_hours=24, business_key="fission")
    assert summary["total"] >= 1
    assert any(item["key"] == "bad" and item["total"] >= 1 for item in summary["by_grade"])
    issue_bucket = next(item for item in summary["top_issue_tags"] if item["key"] == "结构偏移")
    assert issue_bucket["total"] >= 1
    assert issue_bucket["sample_reviews"][0]["run_id"] == run_id
    assert issue_bucket["sample_reviews"][0]["output_index"] == 0
    fission = next(item for item in summary["by_business"] if item["business_key"] == "fission")
    assert fission["bad"] >= 1
    assert fission["reviewed"] >= 1
    fission_issue_bucket = next(item for item in fission["top_issue_tags"] if item["key"] == "结构偏移")
    assert fission_issue_bucket["sample_reviews"][0]["run_id"] == run_id
    version_summary = next(item for item in summary["by_version"] if item["business_key"] == "fission" and item["version"] == "v-test")
    assert version_summary["bad"] >= 1
    assert version_summary["top_issue_tags"][0]["sample_reviews"][0]["run_id"] == run_id
    batch_summary = next(item for item in summary["by_batch"] if item["batch_id"] == "batch-test")
    assert batch_summary["sample_key"] == "dense-pattern"
    assert batch_summary["sample_label"] == "满版图案"
    assert batch_summary["risk"] >= 1
    assert batch_summary["versions"][0]["sample_reviews"][0]["run_id"] == run_id


def test_quality_read_paths_return_empty_when_optional_tables_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    run_id = _make_run_id()
    _insert_business_run(run_id)
    monkeypatch.setattr(service, "_optional_table_exists", lambda session, table_name: False)

    listed = service.list_output_reviews(run_id=run_id)
    assert listed == {"total": 0, "items": []}

    summary = service.output_review_summary(window_hours=24, business_key="fission")
    assert summary["total"] == 0
    assert summary["by_grade"] == []
    assert summary["recent_reviews"] == []

    exported = service.export_output_reviews(window_hours=24, business_key="fission")
    assert exported["total"] == 0
    assert exported["items"] == []

    assert service.list_quality_samples()["items"] == []
    assert service.list_quality_action_rules()["items"] == []


def test_business_output_reviews_export_filters_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    suffix = uuid4().hex[:8]
    batch_id = f"batch-export-{suffix}"
    included_run = _make_run_id()
    excluded_run = _make_run_id()
    _insert_business_run(
        included_run,
        business_key="fission",
        version="v-export-a",
        batch_id=batch_id,
        sample_key="dense-pattern",
        sample_label="满版图案",
    )
    _insert_business_run(
        excluded_run,
        business_key="fission",
        version="v-export-b",
        batch_id=f"batch-other-{suffix}",
        sample_key="line-art",
        sample_label="线稿",
    )

    service.upsert_output_reviews(
        run_id=included_run,
        payload=BusinessOutputReviewUpsertRequest(
            items=[
                BusinessOutputReviewUpsertItem(
                    outputIndex=0,
                    qualityGrade="usable",
                    inputTags=["满版图案"],
                    issueTags=[],
                    nextAction="accept",
                    note="同批可用。",
                )
            ]
        ),
    )
    service.upsert_output_reviews(
        run_id=excluded_run,
        payload=BusinessOutputReviewUpsertRequest(
            items=[BusinessOutputReviewUpsertItem(outputIndex=0, qualityGrade="bad", issueTags=["边缘脏污"])]
        ),
    )

    exported = service.export_output_reviews(window_hours=24, business_key="fission", batch_id=batch_id)
    assert exported["total"] == 1
    item = exported["items"][0]
    assert item["run_id"] == included_run
    assert item["batch_id"] == batch_id
    assert item["sample_key"] == "dense-pattern"
    assert item["sample_label"] == "满版图案"
    assert item["quality_grade"] == "usable"
    assert item["next_action"] == "accept"
    assert item["output_url"] == "https://example.com/output-1.png"


def test_business_output_reviews_reject_invalid_grade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    run_id = _make_run_id()
    _insert_business_run(run_id, business_key="image_edit")

    payload = BusinessOutputReviewUpsertRequest(
        items=[BusinessOutputReviewUpsertItem(outputIndex=0, qualityGrade="great")]
    )

    with pytest.raises(HTTPException) as exc:
        service.upsert_output_reviews(run_id=run_id, payload=payload)
    assert exc.value.status_code == 400
    assert exc.value.detail == "BUSINESS_OUTPUT_REVIEW_GRADE_INVALID"


def test_business_quality_samples_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    sample_key = f"dense-pattern-{uuid4().hex[:8]}"
    created = service.create_quality_sample(
        BusinessQualitySampleCreateRequest(
            businessKey="fission",
            sampleKey=sample_key,
            label="满版图案 A",
            imageUrl="https://example.com/dense.png",
            prompt="保持主体结构",
            inputTags=["满版图案"],
            defaultParams={"quality": "preview"},
            sortOrder=3,
        )
    )

    assert created["business_key"] == "fission"
    assert created["sample_key"] == sample_key
    assert created["image_url"] == "https://example.com/dense.png"
    assert created["default_params"] == {"quality": "preview"}

    listed = service.list_quality_samples(business_key="fission")
    assert listed["total"] >= 1
    assert any(item["id"] == created["id"] for item in listed["items"])

    updated = service.update_quality_sample(
        created["id"],
        BusinessQualitySampleUpdateRequest(
            label="满版图案 B",
            generatedImageUrl="https://example.com/generated.png",
            status="inactive",
        ),
    )
    assert updated["label"] == "满版图案 B"
    assert updated["generated_image_url"] == "https://example.com/generated.png"
    assert updated["status"] == "inactive"
    versions = service.list_quality_sample_versions(created["id"])
    assert versions["total"] == 2
    assert versions["items"][0]["change_type"] == "update"
    assert versions["items"][0]["version_no"] == 2
    assert versions["items"][1]["change_type"] == "create"

    archived = service.archive_quality_sample(created["id"])
    assert archived["status"] == "archived"
    archived_versions = service.list_quality_sample_versions(created["id"])
    assert archived_versions["items"][0]["change_type"] == "archive"
    active_only = service.list_quality_samples(business_key="fission")
    assert all(item["id"] != created["id"] for item in active_only["items"])
    with_archived = service.list_quality_samples(business_key="fission", include_archived=True)
    assert any(item["id"] == created["id"] for item in with_archived["items"])


def test_business_quality_samples_reject_invalid_url_and_duplicate_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()

    with pytest.raises(HTTPException) as invalid_url:
        service.create_quality_sample(
            BusinessQualitySampleCreateRequest(
                businessKey="image_edit",
                sampleKey="invalid-url",
                label="无效 URL",
                imageUrl="oss://private/image.png",
            )
        )
    assert invalid_url.value.status_code == 400
    assert invalid_url.value.detail == "BUSINESS_QUALITY_SAMPLE_IMAGE_URL_INVALID"

    duplicate_key = f"same-key-{uuid4().hex[:8]}"
    payload = BusinessQualitySampleCreateRequest(
        businessKey="image_edit",
        sampleKey=duplicate_key,
        label="样例",
        imageUrl="https://example.com/a.png",
    )
    service.create_quality_sample(payload)
    with pytest.raises(HTTPException) as duplicated:
        service.create_quality_sample(payload)
    assert duplicated.value.status_code == 409
    assert duplicated.value.detail == "BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED"


def test_business_quality_samples_import_upsert_and_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    sample_key = f"import-key-{uuid4().hex[:8]}"

    first = service.import_quality_samples(
        BusinessQualitySampleImportRequest(
            businessKey="fission",
            items=[
                BusinessQualitySampleImportItem(
                    sampleKey=sample_key,
                    label="导入样例 A",
                    imageUrl="https://example.com/import-a.png",
                    inputTags=["满版图案"],
                    defaultParams={"quality": "preview"},
                )
            ],
        )
    )
    assert first["created"] == 1
    assert first["updated"] == 0
    sample_id = first["items"][0]["sample_id"]

    second = service.import_quality_samples(
        BusinessQualitySampleImportRequest(
            businessKey="fission",
            changeNote="运营批量修订",
            items=[
                BusinessQualitySampleImportItem(
                    sampleKey=sample_key,
                    label="导入样例 B",
                    imageUrl="https://example.com/import-b.png",
                    status="inactive",
                ),
                BusinessQualitySampleImportItem(
                    sampleKey=sample_key,
                    label="重复样例",
                    imageUrl="https://example.com/import-c.png",
                ),
            ],
        )
    )
    assert second["created"] == 0
    assert second["updated"] == 1
    assert second["failed"] == 1
    assert second["items"][1]["error_code"] == "BUSINESS_QUALITY_SAMPLE_KEY_DUPLICATED"

    versions = service.list_quality_sample_versions(sample_id)
    assert versions["total"] == 2
    assert versions["items"][0]["change_type"] == "import_update"
    assert versions["items"][0]["change_note"] == "运营批量修订"
    assert versions["items"][0]["label"] == "导入样例 B"
    assert versions["items"][1]["change_type"] == "import_create"

    dry_run = service.import_quality_samples(
        BusinessQualitySampleImportRequest(
            businessKey="fission",
            dryRun=True,
            items=[
                BusinessQualitySampleImportItem(
                    sampleKey=f"dry-run-{uuid4().hex[:8]}",
                    label="预检查样例",
                    imageUrl="https://example.com/dry.png",
                )
            ],
        )
    )
    assert dry_run["dry_run"] is True
    assert dry_run["skipped"] == 1
    assert dry_run["items"][0]["action"] == "dry_run_create"


def test_business_quality_action_rules_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    suffix = uuid4().hex[:8]
    capability_id = f"cap_quality_rule_{suffix}"
    with get_session() as session:
        session.add(
            BusinessCapability(
                id=capability_id,
                business_key="fission",
                version=f"v-rule-{suffix}",
                display_name="图裂变候选 LoRA",
                status="draft",
                is_default=False,
                recipe={"workflowKey": "fission_candidate"},
                input_schema={},
                output_schema={},
                extra_metadata={"lora": "candidate-lora.safetensors"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        session.commit()

    created = service.create_quality_action_rule(
        BusinessQualityActionRuleCreateRequest(
            businessKey="fission",
            ruleKey=f"dense-pattern-{suffix}",
            title="满版图案切候选 LoRA",
            description="满版图案结构偏移时切候选 LoRA。",
            issueTags=["结构偏移"],
            inputTags=["满版图案"],
            actionType="switch_lora",
            targetBusinessVersionId=capability_id,
            targetRef="candidate-lora.safetensors",
            targetParams={"denoise": 0.48},
            sampleBatchId="batch-quality-rule",
            evidenceReviewIds=["review-1", "review-1", "review-2"],
            status="candidate",
            priority=2,
        )
    )

    assert created["business_key"] == "fission"
    assert created["rule_key"].startswith("dense-pattern")
    assert created["action_type"] == "switch_lora"
    assert created["target_business_version_id"] == capability_id
    assert created["target_capability"]["version"].startswith("v-rule-")
    assert created["evidence_review_ids"] == ["review-1", "review-2"]

    listed = service.list_quality_action_rules(business_key="fission", action_type="switch_lora")
    assert any(item["id"] == created["id"] for item in listed["items"])

    updated = service.update_quality_action_rule(
        created["id"],
        BusinessQualityActionRuleUpdateRequest(
            title="满版图案候选 workflow",
            actionType="switch_workflow",
            targetBusinessVersionId=None,
            targetRef="fission_workflow_v2",
            status="validated",
        ),
    )
    assert updated["title"] == "满版图案候选 workflow"
    assert updated["action_type"] == "switch_workflow"
    assert updated["target_business_version_id"] is None
    assert updated["target_ref"] == "fission_workflow_v2"
    assert updated["status"] == "validated"

    archived = service.archive_quality_action_rule(created["id"])
    assert archived["status"] == "archived"
    active_only = service.list_quality_action_rules(business_key="fission")
    assert all(item["id"] != created["id"] for item in active_only["items"])
    with_archived = service.list_quality_action_rules(business_key="fission", include_archived=True)
    assert any(item["id"] == created["id"] for item in with_archived["items"])


def test_business_quality_action_rules_reject_invalid_and_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    with pytest.raises(HTTPException) as invalid_action:
        service.create_quality_action_rule(
            BusinessQualityActionRuleCreateRequest(
                businessKey="outpaint",
                ruleKey="invalid-action",
                title="非法动作",
                actionType="magic",
            )
        )
    assert invalid_action.value.status_code == 400
    assert invalid_action.value.detail == "BUSINESS_QUALITY_ACTION_TYPE_INVALID"

    duplicate_key = f"same-rule-{uuid4().hex[:8]}"
    payload = BusinessQualityActionRuleCreateRequest(
        businessKey="outpaint",
        ruleKey=duplicate_key,
        title="扩图边缘破损观察",
        actionType="watch_only",
    )
    service.create_quality_action_rule(payload)
    with pytest.raises(HTTPException) as duplicated:
        service.create_quality_action_rule(payload)
    assert duplicated.value.status_code == 409
    assert duplicated.value.detail == "BUSINESS_QUALITY_ACTION_KEY_DUPLICATED"

    with pytest.raises(HTTPException) as missing_target:
        service.create_quality_action_rule(
            BusinessQualityActionRuleCreateRequest(
                businessKey="outpaint",
                ruleKey=f"missing-target-{uuid4().hex[:8]}",
                title="目标版本不存在",
                actionType="switch_workflow",
                targetBusinessVersionId="not-exists",
            )
        )
    assert missing_target.value.status_code == 404
    assert missing_target.value.detail == "BUSINESS_QUALITY_ACTION_TARGET_VERSION_NOT_FOUND"


def test_business_usage_summary_includes_flow_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(BusinessRunService, "_start_finalize_thread", lambda self: None)
    service = BusinessRunService()
    run_id = _make_run_id()
    now = datetime.utcnow()
    capability_id = f"cap_flow_evidence_{uuid4().hex[:8]}"
    with get_session() as session:
        session.add(
            BusinessRun(
                id=run_id,
                business_key="fission",
                business_version_id=capability_id,
                version="v-flow-candidate",
                status="succeeded",
                source="pytest",
                request_payload={
                    "_route": {
                        "selectedBy": "quality_rule",
                        "businessVersionId": capability_id,
                        "selectedCapabilityId": capability_id,
                        "version": "v-flow-candidate",
                        "workflowKey": "fission_workflow_v2",
                        "lora": "candidate-lora.safetensors",
                    }
                },
                result_payload={"assets": [{"url": "https://example.com/output.png"}]},
                image_urls=["https://example.com/output.png"],
                duration_ms=5200,
                created_at=now,
                updated_at=now,
                started_at=now + timedelta(milliseconds=300),
                finished_at=now + timedelta(milliseconds=5500),
            )
        )
        session.add_all(
            [
                BusinessRunStep(
                    id=f"{run_id}_preprocess",
                    run_id=run_id,
                    step_order=1,
                    step_type="vl_analyze",
                    role="preprocess",
                    display_name="输入理解",
                    status="succeeded",
                    request_payload={"imageUrl": "https://example.com/input.png"},
                    result_payload={"tags": ["满版图案"]},
                    duration_ms=700,
                    created_at=now,
                    updated_at=now,
                    started_at=now + timedelta(milliseconds=400),
                    finished_at=now + timedelta(milliseconds=1100),
                ),
                BusinessRunStep(
                    id=f"{run_id}_primary",
                    run_id=run_id,
                    step_order=2,
                    step_type="comfyui_workflow",
                    role="primary",
                    display_name="候选 LoRA 出图",
                    status="succeeded",
                    request_payload={
                        "workflowKey": "fission_workflow_v2",
                        "loraName": "candidate-lora.safetensors",
                    },
                    result_payload={"images": [{"url": "https://example.com/output.png"}]},
                    duration_ms=4100,
                    created_at=now,
                    updated_at=now,
                    started_at=now + timedelta(milliseconds=1200),
                    finished_at=now + timedelta(milliseconds=5300),
                ),
            ]
        )
        session.commit()

    summary = service.usage_summary(window_hours=24, business_key="fission")
    flow = summary["flow_evidence"]
    stage_by_key = {item["key"]: item for item in flow["stage_evidence"]}
    assert stage_by_key["entry"]["total"] >= 1
    assert stage_by_key["entry"]["avg_duration_ms"] is not None
    assert stage_by_key["preprocess"]["avg_duration_ms"] is not None
    assert stage_by_key["primary"]["avg_duration_ms"] is not None
    assert any(item["key"] == "quality_rule" for item in flow["route_hits"])
    assert any(item["key"] == capability_id for item in flow["candidate_hits"])
    assert any(item["key"] == "candidate-lora.safetensors" for item in flow["lora_hits"])
    assert any(item["key"] == "fission_workflow_v2" for item in flow["workflow_hits"])
