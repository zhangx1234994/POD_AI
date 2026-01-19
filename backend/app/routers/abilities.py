"""Public ability catalogue & invocation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.db import get_session
from app.deps.auth import get_current_user
from app.models.integration import Ability
from app.models.user import User
from app.schemas import abilities as schemas
from app.schemas import admin_abilities as admin_schemas
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_seed import ensure_default_abilities

router = APIRouter(prefix="/api/abilities", tags=["abilities"])


@router.get("", response_model=schemas.AbilityListResponse)
def list_abilities() -> schemas.AbilityListResponse:
    items = ability_invocation_service.list_public_abilities()
    return schemas.AbilityListResponse(items=items)


@router.get("/options", response_model=admin_schemas.AbilityOptionListResponse)
def list_ability_options_public(
    status: str | None = Query(default="active"),
    provider: str | None = Query(default=None),
) -> admin_schemas.AbilityOptionListResponse:
    with get_session() as session:
        ensure_default_abilities(session)
        stmt = select(Ability)
        if status:
            stmt = stmt.where(Ability.status == status)
        if provider:
            stmt = stmt.where(Ability.provider == provider)
        stmt = stmt.order_by(Ability.provider.asc(), Ability.capability_key.asc())
        abilities = session.execute(stmt).scalars().all()
        return admin_schemas.AbilityOptionListResponse(
            items=[
                admin_schemas.AbilityOption(
                    id=ability.id,
                    provider=ability.provider,
                    category=ability.category,
                    capability_key=ability.capability_key,
                    display_name=ability.display_name,
                    description=ability.description,
                    default_params=ability.default_params,
                    input_schema=ability.input_schema,
                    metadata=ability.extra_metadata,
                )
                for ability in abilities
            ]
        )


@router.get("/{ability_id}", response_model=schemas.AbilityPublicInfo)
def get_ability(ability_id: str) -> schemas.AbilityPublicInfo:
    return ability_invocation_service.get_public_ability(ability_id)


@router.post("/{ability_id}/invoke", response_model=schemas.AbilityInvokeResponse)
def invoke_ability(
    ability_id: str,
    payload: schemas.AbilityInvokeRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> schemas.AbilityInvokeResponse:
    return ability_invocation_service.invoke(ability_id=ability_id, payload=payload, user=user, request=request)
