"""Public ability catalogue & invocation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.core.db import get_session
from app.deps.auth import get_current_user
from app.models.integration import Ability
from app.models.user import User
from app.schemas import abilities as schemas
from app.schemas import admin_abilities as admin_schemas
from app.services.ability_deprecation import resolve_ability_deprecation
from app.services.ability_governance import build_business_status, resolve_ability_governance
from app.services.ability_presentation import (
    build_ability_presentation_sort_key,
    is_ability_visible_for_surface,
    resolve_ability_presentation,
)
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_seed import ensure_default_abilities

router = APIRouter(prefix="/api/abilities", tags=["abilities"])


def _serialize_governance(ability: Ability) -> admin_schemas.AbilityGovernance:
    return admin_schemas.AbilityGovernance(
        **resolve_ability_governance(status=ability.status, metadata=ability.extra_metadata)
    )


def _serialize_business_status(ability: Ability) -> admin_schemas.AbilityBusinessStatus:
    return admin_schemas.AbilityBusinessStatus(
        **build_business_status(resolve_ability_governance(status=ability.status, metadata=ability.extra_metadata))
    )


def _serialize_presentation(ability: Ability) -> admin_schemas.AbilityPresentation:
    return admin_schemas.AbilityPresentation(
        **resolve_ability_presentation(
            status=ability.status,
            provider=ability.provider,
            category=ability.category,
            capability_key=ability.capability_key,
            ability_type=ability.ability_type,
            metadata=ability.extra_metadata,
        )
    )


def _serialize_deprecation(ability: Ability) -> admin_schemas.AbilityDeprecation:
    payload = resolve_ability_deprecation(status=ability.status, metadata=ability.extra_metadata) or {}
    return admin_schemas.AbilityDeprecation(**payload)


def _ability_sort_key(ability: Ability) -> tuple[int, str, str, str]:
    return build_ability_presentation_sort_key(
        status=ability.status,
        provider=ability.provider,
        category=ability.category,
        capability_key=ability.capability_key,
        ability_type=ability.ability_type,
        display_name=ability.display_name,
        metadata=ability.extra_metadata,
    )


@router.get("", response_model=schemas.AbilityListResponse)
def list_abilities(surface: str | None = Query(default=None)) -> schemas.AbilityListResponse:
    items = ability_invocation_service.list_public_abilities(surface=surface)
    return schemas.AbilityListResponse(items=items)


@router.get("/options", response_model=admin_schemas.AbilityOptionListResponse)
def list_ability_options_public(
    status: str | None = Query(default="active"),
    provider: str | None = Query(default=None),
    surface: str | None = Query(default=None),
    visible_only: bool = Query(default=True),
) -> admin_schemas.AbilityOptionListResponse:
    with get_session() as session:
        ensure_default_abilities(session)
        stmt = select(Ability)
        if status:
            stmt = stmt.where(Ability.status == status)
        if provider:
            stmt = stmt.where(Ability.provider == provider)
        abilities = session.execute(stmt).scalars().all()
        if visible_only:
            abilities = [
                ability
                for ability in abilities
                if is_ability_visible_for_surface(
                    status=ability.status,
                    provider=ability.provider,
                    category=ability.category,
                    capability_key=ability.capability_key,
                    ability_type=ability.ability_type,
                    metadata=ability.extra_metadata,
                    surface=surface,
                )
            ]
        abilities.sort(key=_ability_sort_key)
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
                    governance=_serialize_governance(ability),
                    presentation=_serialize_presentation(ability),
                    deprecation=_serialize_deprecation(ability),
                    business_status=_serialize_business_status(ability),
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
