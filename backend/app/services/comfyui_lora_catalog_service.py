from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.eval import EvalWorkflowVersion
from app.models.integration import Ability, ComfyuiLora


def _as_non_empty_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _extract_lora_names_from_any(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, str):
        text = _as_non_empty_text(value)
        if text:
            names.append(text)
    elif isinstance(value, dict):
        for key in ("value", "name", "file_name", "fileName"):
            text = _as_non_empty_text(value.get(key))
            if text:
                names.append(text)
                break
    elif isinstance(value, list):
        for item in value:
            names.extend(_extract_lora_names_from_any(item))
    return names


def collect_functional_lora_names(session: Session) -> set[str]:
    """Collect LoRA names that are actually used by active abilities/eval workflows."""
    names: set[str] = set()

    ability_rows = (
        session.execute(select(Ability).where(Ability.status == "active", Ability.provider == "comfyui"))
        .scalars()
        .all()
    )
    for row in ability_rows:
        defaults = row.default_params or {}
        metadata = row.extra_metadata or {}

        for key in ("lora", "lora_name", "loraName"):
            text = _as_non_empty_text(defaults.get(key))
            if text:
                names.add(text)

        for key in ("default_lora", "lora_default"):
            text = _as_non_empty_text(metadata.get(key))
            if text:
                names.add(text)

        for key in ("allowed_lora_files", "allowed_loras", "lora_allow_files"):
            names.update(_extract_lora_names_from_any(metadata.get(key)))

        # lora_presets is usually a list[dict{name,value,...}]
        names.update(_extract_lora_names_from_any(metadata.get("lora_presets")))

    eval_rows = session.execute(select(EvalWorkflowVersion).where(EvalWorkflowVersion.status == "active")).scalars().all()
    for row in eval_rows:
        schema = row.parameters_schema or {}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if not isinstance(fields, list):
            continue
        for field in fields:
            if not isinstance(field, dict):
                continue
            if str(field.get("name") or "").strip() not in {"lora", "lora_name"}:
                continue
            text = _as_non_empty_text(field.get("defaultValue"))
            if text:
                names.add(text)
            names.update(_extract_lora_names_from_any(field.get("options")))

    return {name for name in names if name}


def sync_lora_catalog_with_functional_set(
    session: Session,
    *,
    functional_names: set[str],
    deactivate_others: bool = True,
) -> dict[str, int]:
    """Ensure functional LoRA entries are active and present in catalog.

    - Missing functional names will be inserted.
    - Existing functional rows are set to active.
    - Non-functional rows are set to inactive (when deactivate_others=True).
    """
    stats = {"inserted": 0, "activated": 0, "deactivated": 0, "kept_active": 0, "total": 0}
    rows = session.execute(select(ComfyuiLora)).scalars().all()
    stats["total"] = len(rows)
    by_name = {row.file_name: row for row in rows}

    for name in sorted(functional_names):
        row = by_name.get(name)
        if row is None:
            display = name.rsplit(".", 1)[0] if "." in name else name
            session.add(
                ComfyuiLora(
                    file_name=name,
                    display_name=display,
                    status="active",
                )
            )
            stats["inserted"] += 1
            continue
        if row.status != "active":
            row.status = "active"
            session.add(row)
            stats["activated"] += 1
        else:
            stats["kept_active"] += 1

    if deactivate_others:
        for row in rows:
            if row.file_name in functional_names:
                continue
            if row.status == "active":
                row.status = "inactive"
                session.add(row)
                stats["deactivated"] += 1

    return stats
