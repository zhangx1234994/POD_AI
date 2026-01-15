"""Admin endpoints for ability catalog management."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.core.db import get_session
from app.deps.auth import require_admin
from app.models.integration import Ability, Executor, Workflow
from app.schemas import admin_abilities as schemas
from app.schemas import admin_ability_logs as log_schemas
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_logs import ability_log_service

router = APIRouter(prefix="/admin/abilities", dependencies=[Depends(require_admin)])


def _generate_id(existing_id: str | None) -> str:
    return existing_id or uuid4().hex


@router.get("", response_model=list[schemas.AbilityRead])
def list_abilities() -> list[Ability]:
    with get_session() as session:
        ensure_default_abilities(session)
        stmt = select(Ability).order_by(Ability.provider.asc(), Ability.capability_key.asc())
        return session.execute(stmt).scalars().all()


@router.post("", response_model=schemas.AbilityRead)
def create_ability(payload: schemas.AbilityCreate) -> Ability:
    with get_session() as session:
        ability = Ability(
            id=_generate_id(payload.id),
            provider=payload.provider,
            category=payload.category,
            capability_key=payload.capability_key,
            display_name=payload.display_name,
            description=payload.description,
            status=payload.status,
            ability_type=payload.ability_type or "api",
            executor_id=payload.executor_id,
            workflow_id=payload.workflow_id,
            default_params=payload.default_params,
            input_schema=payload.input_schema,
            extra_metadata=payload.metadata,
        )
        if ability.executor_id:
            executor = session.get(Executor, ability.executor_id)
            if not executor:
                raise HTTPException(status_code=400, detail="EXECUTOR_NOT_FOUND")
        if ability.workflow_id:
            workflow = session.get(Workflow, ability.workflow_id)
            if not workflow:
                raise HTTPException(status_code=400, detail="WORKFLOW_NOT_FOUND")
        session.add(ability)
        session.commit()
        session.refresh(ability)
        return ability


@router.put("/{ability_id}", response_model=schemas.AbilityRead)
def update_ability(ability_id: str, payload: schemas.AbilityUpdate) -> Ability:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        data = payload.model_dump(exclude_unset=True)
        if "metadata" in data:
            data["extra_metadata"] = data.pop("metadata")
        if "executor_id" in data and data["executor_id"]:
            executor = session.get(Executor, data["executor_id"])
            if not executor:
                raise HTTPException(status_code=400, detail="EXECUTOR_NOT_FOUND")
        if "workflow_id" in data and data["workflow_id"]:
            workflow = session.get(Workflow, data["workflow_id"])
            if not workflow:
                raise HTTPException(status_code=400, detail="WORKFLOW_NOT_FOUND")
        for key, value in data.items():
            setattr(ability, key, value)
        session.add(ability)
        session.commit()
        session.refresh(ability)
        return ability


@router.delete("/{ability_id}")
def delete_ability(ability_id: str) -> dict[str, str]:
    with get_session() as session:
        ability = session.get(Ability, ability_id)
        if not ability:
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        session.delete(ability)
        session.commit()
        return {"status": "deleted"}


@router.get("/{ability_id}/logs", response_model=log_schemas.AbilityInvocationLogListResponse)
def list_ability_logs(ability_id: str, limit: int = Query(20, ge=1, le=100)):
    entries = ability_log_service.list_logs(ability_id=ability_id, limit=limit)
    return {
        "items": [log_schemas.AbilityInvocationLogRead.model_validate(entry) for entry in entries],
    }


@router.get("/logs", response_model=log_schemas.AbilityInvocationLogListResponse)
def list_all_ability_logs(
    limit: int = Query(20, ge=1, le=200),
    ability_id: str | None = Query(default=None, alias="abilityId"),
    provider: str | None = Query(default=None),
    capability_key: str | None = Query(default=None, alias="capabilityKey"),
):
    entries = ability_log_service.list_logs(
        ability_id=ability_id,
        provider=provider,
        capability_key=capability_key,
        limit=limit,
    )
    return {
        "items": [log_schemas.AbilityInvocationLogRead.model_validate(entry) for entry in entries],
    }
