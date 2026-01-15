"""Public ability catalogue & invocation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps.auth import get_current_user
from app.models.user import User
from app.schemas import abilities as schemas
from app.services.ability_invocation import ability_invocation_service

router = APIRouter(prefix="/api/abilities", tags=["abilities"])


@router.get("", response_model=schemas.AbilityListResponse)
def list_abilities() -> schemas.AbilityListResponse:
    items = ability_invocation_service.list_public_abilities()
    return schemas.AbilityListResponse(items=items)


@router.get("/{ability_id}", response_model=schemas.AbilityPublicInfo)
def get_ability(ability_id: str) -> schemas.AbilityPublicInfo:
    return ability_invocation_service.get_public_ability(ability_id)


@router.post("/{ability_id}/invoke", response_model=schemas.AbilityInvokeResponse)
def invoke_ability(
    ability_id: str,
    payload: schemas.AbilityInvokeRequest,
    user: User = Depends(get_current_user),
) -> schemas.AbilityInvokeResponse:
    return ability_invocation_service.invoke(ability_id=ability_id, payload=payload, user=user)
