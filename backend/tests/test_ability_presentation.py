from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.models.integration import Ability
from app.models.user import User  # noqa: F401 - ensure users table is registered for FK resolution
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_presentation import (
    enrich_metadata_with_presentation,
    resolve_ability_presentation,
)
from app.services.ability_seed import ensure_default_abilities


def test_resolve_presentation_defaults_for_comfyui_outpaint() -> None:
    presentation = resolve_ability_presentation(
        status="active",
        provider="comfyui",
        category="image_generation",
        capability_key="flux2_klein_9b_outpaint",
        ability_type="comfyui",
        metadata={"governance": {"scopes": ["coze"], "release_status": "published"}},
    )

    assert presentation == {
        "visible": True,
        "sort_order": 200,
        "category_label": "图片生成",
        "usage_hint": "适合在 Coze 工作流中作为图像节点使用",
        "operation_label": "图像扩展",
    }


def test_enrich_presentation_preserves_existing_metadata_and_override() -> None:
    enriched = enrich_metadata_with_presentation(
        {"model_id": "seedream-4.5", "presentation": {"usage_hint": "旧说明"}},
        status="active",
        provider="volcengine",
        category="image_generation",
        capability_key="seedream_4_5",
        ability_type="api",
        presentation_override={"sort_order": 320, "category_label": "创意生成", "usage_hint": "适合快速做创意图"},
    )

    assert enriched["model_id"] == "seedream-4.5"
    assert enriched["presentation"] == {
        "visible": True,
        "sort_order": 320,
        "category_label": "创意生成",
        "usage_hint": "适合快速做创意图",
        "operation_label": "图片生成",
    }


def test_ability_seed_persists_presentation_block() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        changed = ensure_default_abilities(session)
        assert changed in {True, False}
        rows = session.execute(select(Ability)).scalars().all()
        assert rows
        sample = next(row for row in rows if row.provider == "comfyui")
        presentation = (sample.extra_metadata or {}).get("presentation")
        assert isinstance(presentation, dict)
        assert isinstance(presentation.get("visible"), bool)
        assert isinstance(presentation.get("sort_order"), int)
        assert isinstance(presentation.get("category_label"), str)
        assert isinstance(presentation.get("usage_hint"), str)
        assert isinstance(presentation.get("operation_label"), str)


def test_public_info_includes_business_presentation() -> None:
    ability = Ability(
        id="comfyui_flux2_klein_9b_outpaint",
        provider="comfyui",
        category="image_generation",
        capability_key="flux2_klein_9b_outpaint",
        display_name="FLUX2-Klein 扩图",
        description="测试能力",
        status="active",
        ability_type="comfyui",
        extra_metadata=enrich_metadata_with_presentation(
            {"governance": {"scopes": ["coze"], "release_status": "published"}, "requires_image_input": True},
            status="active",
            provider="comfyui",
            category="image_generation",
            capability_key="flux2_klein_9b_outpaint",
            ability_type="comfyui",
        ),
    )

    info = ability_invocation_service._to_public_info(ability)

    assert info.businessPresentation is not None
    assert info.businessPresentation.visible is True
    assert info.businessPresentation.categoryLabel == "图片生成"
    assert info.businessPresentation.operationLabel == "图像扩展"
    assert info.businessPresentation.usageHint == "适合在 Coze 工作流中作为图像节点使用"
