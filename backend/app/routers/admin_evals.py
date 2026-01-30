"""Admin API for AI ability evaluation."""

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.eval import (
    EvalWorkflowVersion,
    EvalDatasetItem,
    EvalRun,
    EvalAnnotation,
)
from app.schemas.eval import (
    EvalWorkflowVersionCreate,
    EvalWorkflowVersionUpdate,
    EvalWorkflowVersionResponse,
    EvalDatasetItemCreate,
    EvalDatasetItemResponse,
    EvalRunCreate,
    EvalRunResponse,
    EvalRunListResponse,
    EvalRunPurgeResponse,
    EvalAnnotationCreate,
    EvalAnnotationResponse,
)
from app.services.eval_service import get_eval_service
from app.services.eval_seed import ensure_default_eval_workflow_versions
from app.deps.auth import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/evals")


@router.post("/workflow-versions", response_model=EvalWorkflowVersionResponse)
async def create_workflow_version(
    workflow_version: EvalWorkflowVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new evaluation workflow version."""
    db_workflow_version = EvalWorkflowVersion(id=uuid4().hex, **workflow_version.model_dump())
    db.add(db_workflow_version)
    db.commit()
    db.refresh(db_workflow_version)
    return db_workflow_version


@router.get("/workflow-versions", response_model=List[EvalWorkflowVersionResponse])
async def list_workflow_versions(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all evaluation workflow versions."""
    # Keep admin UI in sync with repo-managed defaults.
    ensure_default_eval_workflow_versions(db)
    query = select(EvalWorkflowVersion)
    if category:
        query = query.where(EvalWorkflowVersion.category == category)
    if status:
        query = query.where(EvalWorkflowVersion.status == status)
    result = db.execute(query)
    return result.scalars().all()


@router.get("/workflow-versions/{workflow_version_id}", response_model=EvalWorkflowVersionResponse)
async def get_workflow_version(
    workflow_version_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific evaluation workflow version."""
    workflow_version = db.get(EvalWorkflowVersion, workflow_version_id)
    if not workflow_version:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    return workflow_version


@router.put("/workflow-versions/{workflow_version_id}", response_model=EvalWorkflowVersionResponse)
async def update_workflow_version(
    workflow_version_id: str,
    workflow_version_update: EvalWorkflowVersionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an evaluation workflow version."""
    workflow_version = db.get(EvalWorkflowVersion, workflow_version_id)
    if not workflow_version:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    update_data = workflow_version_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workflow_version, field, value)
    db.add(workflow_version)
    db.commit()
    db.refresh(workflow_version)
    return workflow_version


@router.post("/datasets", response_model=EvalDatasetItemResponse)
async def create_dataset_item(
    dataset_item: EvalDatasetItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a dataset item record.

    Note: the frontend can upload assets to OSS via `/api/media/*` first, then
    store the resulting OSS URL here.
    """
    db_dataset_item = EvalDatasetItem(
        id=uuid4().hex,
        **dataset_item.model_dump(),
        created_by=current_user.id
    )
    db.add(db_dataset_item)
    db.commit()
    db.refresh(db_dataset_item)
    return db_dataset_item


@router.get("/datasets", response_model=List[EvalDatasetItemResponse])
async def list_dataset_items(
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all dataset items."""
    query = select(EvalDatasetItem)
    if category:
        query = query.where(EvalDatasetItem.category == category)
    result = db.execute(query)
    return result.scalars().all()


@router.post("/runs", response_model=EvalRunResponse)
async def create_eval_run(
    eval_run: EvalRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new evaluation run."""
    try:
        db_eval_run = get_eval_service().create_eval_run(
            workflow_version_id=eval_run.workflow_version_id,
            dataset_item_id=eval_run.dataset_item_id,
            input_oss_urls=eval_run.input_oss_urls_json,
            parameters=eval_run.parameters_json,
            created_by=current_user.id,
            db=db
        )
        return db_eval_run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create evaluation run: {str(e)}")


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_runs(
    workflow_version_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=100),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all evaluation runs with pagination."""
    try:
        total, results = get_eval_service().list_eval_runs(
            db=db,
            workflow_version_id=workflow_version_id,
            status=status,
            limit=limit,
            offset=offset
        )
        return EvalRunListResponse(total=total, items=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list evaluation runs: {str(e)}")


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific evaluation run."""
    eval_run = db.get(EvalRun, run_id)
    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return eval_run


@router.post("/runs/{run_id}/annotations", response_model=EvalAnnotationResponse)
async def create_annotation(
    run_id: str,
    annotation: EvalAnnotationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an annotation for an evaluation run."""
    # Check if run exists
    eval_run = db.get(EvalRun, run_id)
    if not eval_run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    
    db_annotation = EvalAnnotation(
        **annotation.model_dump(),
        run_id=run_id,
        created_by=current_user.id
    )
    db.add(db_annotation)
    db.commit()
    db.refresh(db_annotation)
    return db_annotation


@router.get("/runs/{run_id}/annotations", response_model=List[EvalAnnotationResponse])
async def list_annotations(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all annotations for an evaluation run."""
    query = select(EvalAnnotation).where(EvalAnnotation.run_id == run_id)
    result = db.execute(query)
    return result.scalars().all()


@router.delete("/runs", response_model=EvalRunPurgeResponse)
async def purge_eval_runs(
    workflow_version_id: Optional[str] = Query(None),
    confirm: bool = Query(False),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete evaluation runs and related annotations.

    Use `confirm=true` to avoid accidental deletion.
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="CONFIRM_REQUIRED")

    filters = []
    if workflow_version_id:
        filters.append(EvalRun.workflow_version_id == workflow_version_id)

    subquery = select(EvalRun.id)
    if filters:
        subquery = subquery.where(*filters)

    deleted_annotations = db.execute(
        delete(EvalAnnotation).where(EvalAnnotation.run_id.in_(subquery))
    ).rowcount or 0
    delete_runs_stmt = delete(EvalRun)
    if filters:
        delete_runs_stmt = delete_runs_stmt.where(*filters)
    deleted_runs = db.execute(delete_runs_stmt).rowcount or 0
    db.commit()

    return EvalRunPurgeResponse(
        deleted_runs=int(deleted_runs),
        deleted_annotations=int(deleted_annotations),
    )
