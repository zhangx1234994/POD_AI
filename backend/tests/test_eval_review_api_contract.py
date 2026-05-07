from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import Base, get_db
from app.models.eval import EvalAnnotation, EvalBatchAsset, EvalBatchRunItem, EvalBatchSession, EvalRun, EvalWorkflowVersion
from app.models.integration import Ability, AbilityInvocationLog, AbilityTask
from app.routers import evals_public


@pytest.fixture
def eval_review_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker], None, None]:
    monkeypatch.setenv("EVAL_PUBLIC_ENABLED", "true")
    monkeypatch.delenv("EVAL_PUBLIC_TOKEN", raising=False)
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(evals_public.router)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, testing_session_local
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        get_settings.cache_clear()


def _create_batch(
    db: Session,
    *,
    status: str,
    with_asset: bool = False,
    with_terminal_run_item: bool = False,
) -> str:
    batch_id = f"batch_{uuid4().hex[:16]}"
    batch = EvalBatchSession(
        id=batch_id,
        created_by="tester",
        status=status,
        repeat_count=1,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()
    asset_id: str | None = None
    if with_asset:
        asset_id = f"asset_{uuid4().hex[:16]}"
        db.add(
            EvalBatchAsset(
                id=asset_id,
                batch_session_id=batch_id,
                source_key="source_001",
                file_name="sample.png",
                oss_url="https://example.com/sample.png",
                upload_status="uploaded",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    if with_terminal_run_item and asset_id:
        db.add(
            EvalBatchRunItem(
                id=f"run_item_{uuid4().hex[:16]}",
                batch_session_id=batch_id,
                asset_id=asset_id,
                repeat_index=1,
                status="succeeded",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    db.commit()
    return batch_id


def test_eval_runs_expose_readonly_cost_fields(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    with testing_session_local() as db:
        now = datetime.utcnow()
        db.add(
            EvalWorkflowVersion(
                id="wf_v1",
                category="图裂变",
                name="图裂变主线",
                version="v1",
                workflow_id="workflow_1",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            Ability(
                id="ability_fission",
                provider="comfyui",
                category="image",
                capability_key="fission",
                version="v1",
                display_name="图裂变",
                status="active",
                ability_type="workflow",
                created_at=now,
                updated_at=now,
            )
        )
        log = AbilityInvocationLog(
            ability_id="ability_fission",
            ability_provider="comfyui",
            capability_key="fission",
            source="eval",
            status="succeeded",
            billing_unit="image",
            unit_price=0.12,
            currency="USD",
            cost_amount=0.24,
            created_at=now,
            updated_at=now,
        )
        db.add(log)
        db.flush()
        db.add(
            AbilityTask(
                id="task_cost_1",
                ability_id="ability_fission",
                ability_provider="comfyui",
                capability_key="fission",
                status="succeeded",
                log_id=log.id,
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            EvalRun(
                id="run_cost_1",
                workflow_version_id="wf_v1",
                status="succeeded",
                podi_task_id="task_cost_1",
                created_by="tester",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()

    resp = client.get("/api/evals/runs")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["billing_unit"] == "image"
    assert item["unit_price"] == 0.12
    assert item["currency"] == "USD"
    assert item["cost_amount"] == 0.24


def test_workflow_metrics_expose_recent_runtime_health(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    now = datetime.utcnow()
    with testing_session_local() as db:
        db.add_all(
            [
                EvalWorkflowVersion(
                    id="wf_runtime",
                    category="图裂变",
                    name="图裂变主线",
                    version="v1",
                    workflow_id="workflow_runtime",
                    status="active",
                    created_at=now,
                    updated_at=now,
                ),
                EvalWorkflowVersion(
                    id="wf_failed",
                    category="图裂变",
                    name="失败样本",
                    version="v1",
                    workflow_id="workflow_failed",
                    status="active",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.add_all(
            [
                EvalRun(
                    id="run_success",
                    workflow_version_id="wf_runtime",
                    status="succeeded",
                    podi_task_id="task_success",
                    result_image_urls_json=["https://example.com/result.png"],
                    created_by="tester",
                    created_at=now - timedelta(hours=1),
                    updated_at=now - timedelta(hours=1),
                ),
                EvalRun(
                    id="run_no_output",
                    workflow_version_id="wf_runtime",
                    status="succeeded",
                    podi_task_id="task_no_output",
                    created_by="tester",
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                ),
                EvalRun(
                    id="run_failed",
                    workflow_version_id="wf_failed",
                    status="failed",
                    error_message="INTERNAL_ONLY",
                    created_by="tester",
                    created_at=now - timedelta(minutes=30),
                    updated_at=now - timedelta(minutes=30),
                ),
            ]
        )
        db.add(
            EvalAnnotation(
                id="annotation_success",
                run_id="run_success",
                rating=4,
                created_by="tester",
                created_at=now,
            )
        )
        db.commit()

    resp = client.get("/api/evals/metrics/workflows", params={"recent_hours": 72})
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    assert metrics["wf_runtime"]["runCount"] == 2
    assert metrics["wf_runtime"]["ratingCount"] == 1
    assert metrics["wf_runtime"]["avgRating"] == 4.0
    assert metrics["wf_runtime"]["recentSuccessCount"] == 1
    assert metrics["wf_runtime"]["recentRunningCount"] == 1
    assert metrics["wf_runtime"]["recentNoOutputCount"] == 1
    assert metrics["wf_runtime"]["lastRunStatus"] == "success"
    assert metrics["wf_failed"]["recentFailureCount"] == 1
    assert metrics["wf_failed"]["lastRunStatus"] == "failed"
    assert metrics["wf_failed"]["lastErrorCode"] == "INTERNAL_ONLY"


def test_workflow_metrics_treats_non_image_outputs_as_valid_results(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    now = datetime.utcnow()
    with testing_session_local() as db:
        db.add(
            EvalWorkflowVersion(
                id="wf_non_image",
                category="通用类",
                name="VL 分析",
                version="v1",
                workflow_id="workflow_non_image",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        db.add_all(
            [
                EvalRun(
                    id="run_text_output",
                    workflow_version_id="wf_non_image",
                    status="succeeded",
                    podi_task_id="task_text",
                    result_output_json={"texts": ["主体是蓝色花纹"]},
                    created_by="tester",
                    created_at=now - timedelta(minutes=30),
                    updated_at=now - timedelta(minutes=30),
                ),
                EvalRun(
                    id="run_structured_output",
                    workflow_version_id="wf_non_image",
                    status="succeeded",
                    podi_task_id="task_structured",
                    result_output_json={"objects": [{"name": "flower"}]},
                    created_by="tester",
                    created_at=now - timedelta(minutes=20),
                    updated_at=now - timedelta(minutes=20),
                ),
            ]
        )
        db.commit()

    resp = client.get("/api/evals/metrics/workflows", params={"recent_hours": 72})
    assert resp.status_code == 200
    metric = resp.json()["metrics"]["wf_non_image"]
    assert metric["recentSuccessCount"] == 2
    assert metric["recentRunningCount"] == 0
    assert metric["recentNoOutputCount"] == 0
    assert metric["recentOutputKindCounts"]["text"] == 1
    assert metric["recentOutputKindCounts"]["structured"] == 1
    assert metric["lastRunHasOutput"] is True


def test_review_groups_returns_not_ready_for_running_batch(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    with testing_session_local() as db:
        batch_id = _create_batch(db, status="running")

    resp = client.get(f"/api/evals/batches/{batch_id}/review-groups", params={"page": 1, "page_size": 20})
    assert resp.status_code == 409
    assert resp.json().get("detail") == "BATCH_REVIEW_NOT_READY"


def test_review_groups_returns_page_invalid_when_out_of_range(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    with testing_session_local() as db:
        batch_id = _create_batch(db, status="succeeded", with_asset=True, with_terminal_run_item=True)

    resp = client.get(f"/api/evals/batches/{batch_id}/review-groups", params={"page": 2, "page_size": 20})
    assert resp.status_code == 400
    assert resp.json().get("detail") == "BATCH_REVIEW_PAGE_INVALID"


def test_review_groups_forces_page_size_to_20(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    with testing_session_local() as db:
        batch_id = _create_batch(db, status="succeeded", with_asset=True, with_terminal_run_item=True)

    resp = client.get(f"/api/evals/batches/{batch_id}/review-groups", params={"page": 1, "page_size": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["page_size"] == 20
    assert data["review_progress"]["page_size"] == 20


def test_review_progress_rejects_completed_page_gt_current(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    with testing_session_local() as db:
        batch_id = _create_batch(db, status="succeeded", with_asset=True, with_terminal_run_item=True)

    resp = client.post(
        f"/api/evals/batches/{batch_id}/review-progress",
        json={"current_page": 2, "completed_page": 3, "page_size": 20},
    )
    assert resp.status_code == 400
    assert resp.json().get("detail") == "BATCH_REVIEW_PAGE_INVALID"


def test_review_progress_returns_not_ready_for_running_batch(
    eval_review_client: tuple[TestClient, sessionmaker],
) -> None:
    client, testing_session_local = eval_review_client
    with testing_session_local() as db:
        batch_id = _create_batch(db, status="running")

    resp = client.post(
        f"/api/evals/batches/{batch_id}/review-progress",
        json={"current_page": 1, "completed_page": 0, "page_size": 20},
    )
    assert resp.status_code == 409
    assert resp.json().get("detail") == "BATCH_REVIEW_NOT_READY"
