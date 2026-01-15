"""Public endpoints for asynchronous ability tasks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.deps.auth import get_current_user
from app.models.user import User
from app.schemas import ability_tasks as schemas
from app.services.ability_task_service import ability_task_service

router = APIRouter(prefix="/api/ability-tasks", tags=["ability-tasks"])


@router.post("", response_model=schemas.AbilityTaskRead)
def submit_task(payload: schemas.AbilityTaskCreateRequest, user: User = Depends(get_current_user)):
    task = ability_task_service.enqueue(ability_id=payload.abilityId, payload=payload, user=user)
    return schemas.AbilityTaskRead.model_validate(task)


@router.get("", response_model=schemas.AbilityTaskListResponse)
def list_tasks(limit: int = Query(20, ge=1, le=200), user: User = Depends(get_current_user)):
    tasks = ability_task_service.list_tasks(user=user, limit=limit)
    items = [schemas.AbilityTaskRead.model_validate(task) for task in tasks]
    return schemas.AbilityTaskListResponse(items=items)


@router.get("/{task_id}", response_model=schemas.AbilityTaskRead)
def get_task(task_id: str, user: User = Depends(get_current_user)):
    task = ability_task_service.get_task(task_id=task_id, user=user)
    return schemas.AbilityTaskRead.model_validate(task)
