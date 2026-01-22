"""Public evaluation APIs (no login) for internal testers.

This router is intended for internal usage on a trusted network. You can:
- enable it with `EVAL_PUBLIC_ENABLED=true`
- optionally protect it with `EVAL_PUBLIC_TOKEN`
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.eval import EvalAnnotation, EvalRun, EvalWorkflowVersion
from app.schemas.eval import (
    EvalAnnotationCreate,
    EvalAnnotationResponse,
    EvalRunCreate,
    EvalRunListResponse,
    EvalRunResponse,
    EvalWorkflowVersionResponse,
)
from app.services.eval_seed import ensure_default_eval_workflow_versions
from app.services.eval_service import eval_service


router = APIRouter(prefix="/api/evals", tags=["evals-public"])


def _require_public_enabled(request: Request) -> None:
    settings = get_settings()
    if not settings.eval_public_enabled:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    if settings.eval_public_token:
        token = request.headers.get("X-Eval-Token") or request.query_params.get("token")
        if token != settings.eval_public_token:
            raise HTTPException(status_code=401, detail="UNAUTHORIZED")


def _get_or_set_rater_id(request: Request, response: Response) -> str:
    rid = request.cookies.get("podi_eval_rater")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    rid = uuid4().hex
    response.set_cookie(
        "podi_eval_rater",
        rid,
        max_age=3600 * 24 * 365,
        httponly=False,
        samesite="lax",
    )
    return rid


@router.get("/me")
def get_me(request: Request, response: Response) -> dict[str, Any]:
    _require_public_enabled(request)
    rid = _get_or_set_rater_id(request, response)
    return {"raterId": rid}


@router.get("/workflow-versions", response_model=list[EvalWorkflowVersionResponse])
def list_workflow_versions(
    request: Request,
    response: Response,
    category: str | None = Query(None),
    status: str | None = Query("active"),
    db: Session = Depends(get_db),
) -> list[EvalWorkflowVersion]:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    ensure_default_eval_workflow_versions(db)
    stmt = select(EvalWorkflowVersion)
    if category:
        stmt = stmt.where(EvalWorkflowVersion.category == category)
    if status:
        stmt = stmt.where(EvalWorkflowVersion.status == status)
    return db.execute(stmt.order_by(EvalWorkflowVersion.category.asc(), EvalWorkflowVersion.created_at.desc())).scalars().all()


@router.post("/runs", response_model=EvalRunResponse)
def create_run(
    request: Request,
    response: Response,
    payload: EvalRunCreate,
    db: Session = Depends(get_db),
) -> EvalRun:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    run = eval_service.create_eval_run(
        workflow_version_id=payload.workflow_version_id,
        dataset_item_id=payload.dataset_item_id,
        input_oss_urls=payload.input_oss_urls_json,
        parameters=payload.parameters_json,
        created_by=created_by,
        db=db,
    )
    return run


@router.get("/runs", response_model=EvalRunListResponse)
def list_runs(
    request: Request,
    response: Response,
    workflow_version_id: str | None = Query(None),
    status: str | None = Query(None),
    unrated: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
) -> EvalRunListResponse:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)

    stmt = select(EvalRun)
    count_stmt = select(func.count()).select_from(EvalRun)
    if workflow_version_id:
        stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
    if status:
        stmt = stmt.where(EvalRun.status == status)
        count_stmt = count_stmt.where(EvalRun.status == status)
    if unrated:
        subq = select(EvalAnnotation.id).where(EvalAnnotation.run_id == EvalRun.id)
        stmt = stmt.where(~exists(subq))
        count_stmt = count_stmt.where(~exists(subq))

    total = int(db.execute(count_stmt).scalar_one())
    items = db.execute(stmt.order_by(EvalRun.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    return EvalRunListResponse(total=total, items=items)


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_run(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> EvalRun:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return run


@router.post("/runs/{run_id}/annotations", response_model=EvalAnnotationResponse)
def create_annotation(
    run_id: str,
    request: Request,
    response: Response,
    payload: EvalAnnotationCreate,
    db: Session = Depends(get_db),
) -> EvalAnnotation:
    _require_public_enabled(request)
    created_by = _get_or_set_rater_id(request, response)
    run = db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="RUN_NOT_FOUND")
    ann = EvalAnnotation(
        id=uuid4().hex,
        run_id=run_id,
        rating=payload.rating,
        tags_json=payload.tags_json,
        comment=payload.comment,
        created_by=created_by,
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


@router.get("/runs/{run_id}/annotations", response_model=list[EvalAnnotationResponse])
def list_run_annotations(
    run_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> list[EvalAnnotation]:
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    stmt = select(EvalAnnotation).where(EvalAnnotation.run_id == run_id).order_by(EvalAnnotation.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/metrics/workflows")
def workflow_metrics(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return per-workflow aggregate rating metrics for business comparison."""
    _require_public_enabled(request)
    _get_or_set_rater_id(request, response)
    # avg rating + count per workflow_version_id
    rows = db.execute(
        select(
            EvalRun.workflow_version_id,
            func.count(EvalAnnotation.id).label("rating_count"),
            func.avg(EvalAnnotation.rating).label("avg_rating"),
        )
        .select_from(EvalRun)
        .join(EvalAnnotation, EvalAnnotation.run_id == EvalRun.id, isouter=True)
        .group_by(EvalRun.workflow_version_id)
    ).all()
    metrics: dict[str, Any] = {}
    for workflow_version_id, rating_count, avg_rating in rows:
        if not workflow_version_id:
            continue
        metrics[str(workflow_version_id)] = {
            "ratingCount": int(rating_count or 0),
            "avgRating": float(avg_rating) if avg_rating is not None else None,
        }
    return {"metrics": metrics}
