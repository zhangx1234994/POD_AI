from fastapi import HTTPException

from app.models.eval import EvalBatchSession
from app.routers.evals_public import (
    _ensure_batch_owner,
    _get_batch_review_progress,
    _normalize_batch_review_progress,
    _parse_review_progress_updated_at,
    _require_batch_exists,
    _set_batch_review_progress,
)


def _make_batch(*, metadata: dict | None = None, created_by: str = "tester") -> EvalBatchSession:
    return EvalBatchSession(
        id="batch_test",
        created_by=created_by,
        status="succeeded",
        extra_metadata=metadata,
    )


def test_normalize_review_progress_clamps_and_forces_page_size() -> None:
    normalized = _normalize_batch_review_progress(
        {
            "page_size": 99,
            "current_page": 9,
            "completed_page": 12,
            "updated_at": "2026-03-05T12:00:00Z",
        },
        total_pages=6,
    )
    assert normalized["page_size"] == 20
    assert normalized["current_page"] == 6
    assert normalized["completed_page"] == 6
    assert normalized["updated_at"] == "2026-03-05T12:00:00Z"


def test_get_batch_review_progress_returns_defaults_when_missing() -> None:
    batch = _make_batch(metadata=None)
    progress = _get_batch_review_progress(batch, total_pages=0)
    assert progress == {
        "page_size": 20,
        "current_page": 1,
        "completed_page": 0,
        "updated_at": None,
    }


def test_set_batch_review_progress_persists_review_state() -> None:
    batch = _make_batch(metadata={"foo": "bar"})
    normalized = _set_batch_review_progress(batch, current_page=7, completed_page=5, total_pages=4)
    assert normalized["page_size"] == 20
    assert normalized["current_page"] == 4
    assert normalized["completed_page"] == 4
    assert isinstance(normalized["updated_at"], str) and normalized["updated_at"].endswith("Z")
    assert isinstance(batch.extra_metadata, dict)
    assert batch.extra_metadata["foo"] == "bar"
    assert batch.extra_metadata["review_state"]["current_page"] == 4


def test_parse_review_progress_updated_at_handles_invalid_value() -> None:
    assert _parse_review_progress_updated_at("2026-03-05T12:00:00Z") is not None
    assert _parse_review_progress_updated_at("invalid-datetime") is None
    assert _parse_review_progress_updated_at(None) is None


def test_require_batch_exists_raises_batch_not_found() -> None:
    try:
        _require_batch_exists(None)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "BATCH_NOT_FOUND"
    else:
        raise AssertionError("expected HTTPException when batch is missing")


def test_ensure_batch_owner_rejects_other_user() -> None:
    batch = _make_batch(created_by="owner_a")
    try:
        _ensure_batch_owner(batch, "owner_b")
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "BATCH_FORBIDDEN"
    else:
        raise AssertionError("expected HTTPException when owner mismatch")
