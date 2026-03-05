from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.db import Base, get_db
from app.models.eval import EvalBatchAsset, EvalBatchRunItem, EvalBatchSession
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
