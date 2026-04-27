"""Seed built-in business capability versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.integration import BusinessCapability


def _field(
    name: str,
    label: str,
    *,
    field_type: str = "text",
    required: bool = False,
    default: Any = None,
    description: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name, "type": field_type, "label": label, "required": required}
    if default is not None:
        payload["default"] = default
    if description:
        payload["description"] = description
    return payload


def _image_generation_output_schema() -> dict[str, Any]:
    return {
        "fields": [
            {"name": "runId", "type": "text", "label": "业务任务 ID Business Run ID"},
            {"name": "status", "type": "text", "label": "任务状态 Status"},
            {"name": "imageUrls", "type": "array", "label": "结果图片 Result Images"},
            {"name": "error", "type": "text", "label": "错误信息 Error"},
        ]
    }


@dataclass(frozen=True)
class BusinessCapabilitySeed:
    id: str
    business_key: str
    version: str
    display_name: str
    description: str
    status: str
    is_default: bool
    release_time: datetime
    recipe: dict[str, Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    metadata: dict[str, Any]


DEFAULT_BUSINESS_CAPABILITY_SEEDS: list[BusinessCapabilitySeed] = [
    BusinessCapabilitySeed(
        id="biz_fission_v1_flux_strong_hq_softstyle",
        business_key="fission",
        version="v1",
        display_name="图裂变 · 高质量多元素花纹",
        description="面向业务侧的图裂变稳定入口，底层使用当前 05 FLUX Strong HQ SoftStyle ComfyUI 工作流。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 4, 24, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_flux_strong_hq_softstyle_fission",
            "steps": [
                {
                    "id": "fission",
                    "type": "ability_task",
                    "abilityId": "comfyui_flux_strong_hq_softstyle_fission",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧只需要传入可访问图片地址。"),
                _field("prompt", "裂变提示词 Prompt", field_type="textarea", required=False),
                _field("bili", "裂变幅度 Denoise/Bili", field_type="number", default=90),
                _field("width", "输出宽度 Width", field_type="number", default=1024),
                _field("height", "输出高度 Height", field_type="number", default=1024),
                _field("batch_size", "生成张数 Batch Size", field_type="number", default=1),
                _field("image_desc", "图像补充描述 Image Description", field_type="textarea", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_fission",
            "entry": "business-api",
            "coze_strategy": "Coze 只调用该业务入口，不再手搓底层节点。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_fission_rollback_e7_flux2_liebian",
        business_key="fission",
        version="rollback-e7-v1",
        display_name="图裂变 · E7 保底版",
        description="图裂变业务入口的保底版本，底层使用 E7 + FLUX2 裂变重绘工作流；用于默认版本异常时快速回滚，不作为日常默认版本。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 3, 28, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_e7_flux2_liebian",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "E7 + FLUX2 裂变重绘",
                    "abilityId": "comfyui_e7_flux2_liebian",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True, description="业务侧只需要传入可访问图片地址。"),
                _field("prompt", "裂变提示词 Prompt", field_type="textarea", required=False),
                _field("bili", "裂变幅度 Denoise/Bili", field_type="number", default=90),
                _field("width", "输出宽度 Width", field_type="number", required=False),
                _field("height", "输出高度 Height", field_type="number", required=False),
                _field("batch_size", "生成张数 Batch Size", field_type="number", default=1),
                _field("steps", "采样步数 Steps", field_type="number", default=8),
                _field("cfg", "提示词强度 CFG", field_type="number", default=1.0),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "image_fission",
            "entry": "business-api",
            "role": "rollback_safety",
            "rollbackSafety": True,
            "rollbackReason": "默认高质量裂变版本异常时，保留可直接切回的旧稳定执行链路。",
            "coze_strategy": "Coze 仍调用同一个业务入口，回滚只在中台切默认版本。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_outpaint_v1_flux2_klein_9b",
        business_key="outpaint",
        version="v1",
        display_name="扩图 · FLUX2-Klein 9B",
        description="面向业务侧的扩图稳定入口，底层使用当前 FLUX2-Klein 9B 扩图 ComfyUI 工作流。",
        status="active",
        is_default=True,
        release_time=datetime(2026, 4, 24, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_flux2_klein_9b_outpaint",
            "steps": [
                {
                    "id": "outpaint",
                    "type": "ability_task",
                    "abilityId": "comfyui_flux2_klein_9b_outpaint",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True),
                _field("prompt", "扩图说明 Prompt", field_type="textarea", required=False),
                _field("expand_left", "左侧扩展 Expand Left", field_type="number", default=408),
                _field("expand_right", "右侧扩展 Expand Right", field_type="number", default=408),
                _field("expand_top", "上侧扩展 Expand Top", field_type="number", default=0),
                _field("expand_bottom", "下侧扩展 Expand Bottom", field_type="number", default=0),
                _field("width", "输出宽度 Width", field_type="number", required=False),
                _field("height", "输出高度 Height", field_type="number", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "outpaint",
            "entry": "business-api",
            "coze_strategy": "Coze 只调用该业务入口，不再手搓底层节点。",
            "seed_version": 1,
        },
    ),
    BusinessCapabilitySeed(
        id="biz_outpaint_rollback_huawen_kuotu",
        business_key="outpaint",
        version="rollback-huawen-v1",
        display_name="扩图 · 花纹扩图保底版",
        description="扩图业务入口的保底版本，底层使用旧花纹扩图工作流；用于 FLUX2-Klein 扩图异常时快速回滚，不作为日常默认版本。",
        status="active",
        is_default=False,
        release_time=datetime(2026, 3, 28, 0, 0, 0),
        recipe={
            "mode": "single_ability_task",
            "primaryAbilityId": "comfyui_huawen_kuotu",
            "steps": [
                {
                    "id": "primary",
                    "type": "ability_task",
                    "role": "primary",
                    "displayName": "花纹扩图",
                    "abilityId": "comfyui_huawen_kuotu",
                }
            ],
            "vlAssist": {"enabled": False, "abilityId": "vl_analyze_image"},
        },
        input_schema={
            "fields": [
                _field("imageUrl", "原图 URL Image URL", required=True),
                _field("prompt", "扩图说明 Prompt", field_type="textarea", required=False),
                _field("expand_left", "左侧扩展 Expand Left", field_type="number", default=200),
                _field("expand_right", "右侧扩展 Expand Right", field_type="number", default=200),
                _field("expand_top", "上侧扩展 Expand Top", field_type="number", default=0),
                _field("expand_bottom", "下侧扩展 Expand Bottom", field_type="number", default=0),
                _field("width", "输出宽度 Width", field_type="number", required=False),
                _field("height", "输出高度 Height", field_type="number", required=False),
            ]
        },
        output_schema=_image_generation_output_schema(),
        metadata={
            "category": "outpaint",
            "entry": "business-api",
            "role": "rollback_safety",
            "rollbackSafety": True,
            "rollbackReason": "默认 FLUX2-Klein 扩图版本异常时，保留可直接切回的旧稳定执行链路。",
            "coze_strategy": "Coze 仍调用同一个业务入口，回滚只在中台切默认版本。",
            "seed_version": 1,
        },
    ),
]


def ensure_default_business_capabilities(session: Session) -> bool:
    changed = False
    for seed in DEFAULT_BUSINESS_CAPABILITY_SEEDS:
        existing = session.get(BusinessCapability, seed.id)
        if existing:
            next_metadata = {**(seed.metadata or {}), **(existing.extra_metadata or {})}
            if int((seed.metadata or {}).get("seed_version") or 0) > int((existing.extra_metadata or {}).get("seed_version") or 0):
                existing.display_name = seed.display_name
                existing.description = seed.description
                existing.recipe = seed.recipe
                existing.input_schema = seed.input_schema
                existing.output_schema = seed.output_schema
                next_metadata = seed.metadata
                changed = True
            if existing.extra_metadata != next_metadata:
                existing.extra_metadata = next_metadata
                changed = True
            if existing.release_time is None:
                existing.release_time = seed.release_time
                changed = True
            continue

        active_default_exists = bool(
            session.execute(
                select(BusinessCapability.id)
                .where(
                    BusinessCapability.business_key == seed.business_key,
                    BusinessCapability.status == "active",
                    BusinessCapability.is_default.is_(True),
                )
                .limit(1)
            ).scalar_one_or_none()
        )
        should_be_default = seed.is_default and not active_default_exists
        if should_be_default:
            session.execute(
                update(BusinessCapability)
                .where(BusinessCapability.business_key == seed.business_key)
                .values(is_default=False)
            )
        session.add(
            BusinessCapability(
                id=seed.id,
                business_key=seed.business_key,
                version=seed.version,
                display_name=seed.display_name,
                description=seed.description,
                status=seed.status,
                is_default=should_be_default,
                release_time=seed.release_time,
                recipe=seed.recipe,
                input_schema=seed.input_schema,
                output_schema=seed.output_schema,
                extra_metadata=seed.metadata,
            )
        )
        changed = True

    # Enforce one active default per business key without overwriting an admin's chosen default.
    for seed in DEFAULT_BUSINESS_CAPABILITY_SEEDS:
        if not seed.is_default:
            continue
        rows = (
            session.execute(
                select(BusinessCapability)
                .where(BusinessCapability.business_key == seed.business_key)
                .order_by(BusinessCapability.created_at.asc())
            )
            .scalars()
            .all()
        )
        active_defaults = [row for row in rows if row.status == "active" and row.is_default]
        desired_default_id = active_defaults[0].id if active_defaults else seed.id
        for row in rows:
            desired = row.status == "active" and row.id == desired_default_id
            if row.is_default != desired:
                row.is_default = desired
                changed = True

    if changed:
        session.commit()
    return changed
