"""Utility helpers to seed the ability catalog with built-in entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants.abilities import (
    BAIDU_IMAGE_ABILITIES,
    COMFYUI_ABILITIES,
    KIE_MARKET_ABILITIES,
    VOLCENGINE_IMAGE_ABILITIES,
    VOLCENGINE_LLM_ABILITIES,
    VOLCENGINE_VIDEO_ABILITIES,
)
from app.models.integration import Ability


@dataclass(frozen=True)
class AbilitySeed:
    id: str
    provider: str
    category: str
    capability_key: str
    display_name: str
    description: str
    status: str = "inactive"
    ability_type: str = "api"
    workflow_id: str | None = None
    default_params: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


def _as_int(value: Any | None) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _build_default_seeds() -> list[AbilitySeed]:
    seeds: list[AbilitySeed] = []
    for capability_key, definition in BAIDU_IMAGE_ABILITIES.items():
        seeds.append(
            AbilitySeed(
                id=f"baidu_{capability_key}",
                provider="baidu",
                category=definition.get("category", "image_process"),
                capability_key=capability_key,
                display_name=definition.get("display_name") or f"百度 · {capability_key}",
                description=definition.get("description") or "",
                status="active",
                default_params=definition.get("defaults") or None,
                input_schema=definition.get("input_schema"),
                metadata=definition.get("metadata") or {"executor_type": "baidu"},
            )
        )
    for capability_key, definition in VOLCENGINE_LLM_ABILITIES.items():
        seeds.append(
            AbilitySeed(
                id=f"volcengine_{capability_key}",
                provider="volcengine",
                category=definition.get("category", "text_generation"),
                capability_key=capability_key,
                display_name=definition.get("display_name") or f"Doubao {capability_key}",
                description=definition.get("description") or "",
                status="active",
                default_params=definition.get("defaults") or None,
                input_schema=definition.get("input_schema"),
                metadata=definition.get("metadata"),
            )
        )
    for capability_key, definition in VOLCENGINE_IMAGE_ABILITIES.items():
        seeds.append(
            AbilitySeed(
                id=f"volcengine_{capability_key}",
                provider="volcengine",
                category=definition.get("category", "image_generation"),
                capability_key=capability_key,
                display_name=definition.get("display_name") or f"Doubao {capability_key}",
                description=definition.get("description") or "",
                status="active",
                default_params=definition.get("defaults") or None,
                input_schema=definition.get("input_schema"),
                metadata=definition.get("metadata"),
            )
        )
    for capability_key, definition in VOLCENGINE_VIDEO_ABILITIES.items():
        seeds.append(
            AbilitySeed(
                id=f"volcengine_{capability_key}",
                provider="volcengine",
                category=definition.get("category", "video_generation"),
                capability_key=capability_key,
                display_name=definition.get("display_name") or f"Doubao {capability_key}",
                description=definition.get("description") or "",
                status="active",
                default_params=definition.get("defaults") or None,
                input_schema=definition.get("input_schema"),
                metadata=definition.get("metadata"),
            )
        )
    for capability_key, definition in KIE_MARKET_ABILITIES.items():
        seeds.append(
            AbilitySeed(
                id=f"kie_{capability_key}",
                provider="kie",
                category=definition.get("category", "image_generation"),
                capability_key=capability_key,
                display_name=definition.get("display_name") or capability_key,
                description=definition.get("description") or "",
                status="active",
                default_params=definition.get("defaults") or None,
                input_schema=definition.get("input_schema"),
                metadata=definition.get("metadata"),
            )
        )
    for capability_key, definition in COMFYUI_ABILITIES.items():
        seeds.append(
            AbilitySeed(
                id=f"comfyui_{capability_key}",
                provider="comfyui",
                category=definition.get("category", "image_generation"),
                capability_key=capability_key,
                display_name=definition.get("display_name") or capability_key,
                description=definition.get("description") or "",
                status="active",
                ability_type="comfyui",
                workflow_id=definition.get("workflow_id"),
                default_params=definition.get("defaults") or None,
                input_schema=definition.get("input_schema"),
                metadata=definition.get("metadata"),
            )
        )
    return seeds


DEFAULT_ABILITY_SEEDS: list[AbilitySeed] = _build_default_seeds()


def ensure_default_abilities(session: Session) -> bool:
    """Ensure built-in abilities exist; return True if new records were created."""

    created = False
    changed = False
    for seed in DEFAULT_ABILITY_SEEDS:
        stmt = select(Ability).where(
            Ability.provider == seed.provider,
            Ability.capability_key == seed.capability_key,
        )
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            updated = False
            seed_version = _as_int((seed.metadata or {}).get("seed_version"))
            existing_metadata = existing.extra_metadata if isinstance(existing.extra_metadata, dict) else {}
            existing_version = _as_int(existing_metadata.get("seed_version"))
            if seed_version and seed_version > existing_version:
                if seed.input_schema:
                    existing.input_schema = seed.input_schema
                if seed.default_params:
                    existing.default_params = seed.default_params
                merged_metadata = {**existing_metadata, **(seed.metadata or {})}
                existing.extra_metadata = merged_metadata
                updated = True
            elif seed.metadata and not existing_metadata:
                existing.extra_metadata = seed.metadata
                updated = True
            if updated:
                session.add(existing)
                changed = True
            continue
        ability = Ability(
            id=seed.id,
            provider=seed.provider,
            category=seed.category,
            capability_key=seed.capability_key,
            display_name=seed.display_name,
            description=seed.description,
            status=seed.status,
            ability_type=seed.ability_type or "api",
            executor_id=None,
            workflow_id=seed.workflow_id,
            default_params=seed.default_params,
            input_schema=seed.input_schema,
            extra_metadata=seed.metadata,
        )
        session.add(ability)
        created = True
        changed = True

    if changed:
        session.commit()
    return created
