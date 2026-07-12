from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.models.integration import Ability
from app.models.user import User  # noqa: F401 - register FK tables
from app.services.ability_catalog_cleanup import get_cleanup_overrides
from app.services.ability_seed import ensure_default_abilities


def test_cleanup_registry_returns_known_overrides() -> None:
    huawen = get_cleanup_overrides(provider="comfyui", capability_key="huawen_kuotu")
    assert huawen["governance"]["release_status"] == "deprecated"
    assert huawen["deprecation"]["replacement_capability_key"] == "flux2_klein_9b_outpaint"

    internal = get_cleanup_overrides(provider="podi", capability_key="expand_mask_color")
    assert internal["governance"]["scopes"] == ["internal", "admin"]
    assert internal["presentation"]["visible"] is False

    set_dpi = get_cleanup_overrides(provider="podi", capability_key="set_dpi")
    assert set_dpi["governance"]["scopes"] == ["internal", "admin"]
    assert set_dpi["presentation"]["operation_label"] == "内部 DPI 处理"

    upscale_resize = get_cleanup_overrides(provider="podi", capability_key="upscale_resize")
    assert upscale_resize["governance"]["scopes"] == ["internal", "admin"]
    assert upscale_resize["presentation"]["operation_label"] == "内部尺寸处理"

    seamless = get_cleanup_overrides(provider="podi", capability_key="seamless_production_normalize")
    assert seamless["governance"]["scopes"] == ["internal", "admin", "business-workflow"]
    assert seamless["presentation"]["visible"] is False


def test_seed_applies_cleanup_for_overridden_abilities() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ensure_default_abilities(session)
        abilities = {
            row.capability_key: row
            for row in session.execute(select(Ability)).scalars().all()
            if row.capability_key in {
                "huawen_kuotu",
                "expand_mask_color",
                "set_dpi",
                "upscale_resize",
                "seamless_production_normalize",
            }
        }

    huawen = abilities["huawen_kuotu"]
    huawen_metadata = huawen.extra_metadata or {}
    assert huawen_metadata["governance"]["release_status"] == "deprecated"
    assert huawen_metadata["deprecation"]["replacement_capability_key"] == "flux2_klein_9b_outpaint"
    assert huawen_metadata["presentation"]["visible"] is False

    expand_mask = abilities["expand_mask_color"]
    expand_mask_metadata = expand_mask.extra_metadata or {}
    assert expand_mask_metadata["governance"]["scopes"] == ["internal", "admin"]
    assert expand_mask_metadata["presentation"]["visible"] is False

    set_dpi = abilities["set_dpi"]
    set_dpi_metadata = set_dpi.extra_metadata or {}
    assert set_dpi_metadata["governance"]["scopes"] == ["internal", "admin"]
    assert set_dpi_metadata["presentation"]["visible"] is False
    assert set_dpi_metadata["presentation"]["operation_label"] == "内部 DPI 处理"
    assert set_dpi_metadata["execution_target"] == "image_ops"
    assert set_dpi_metadata["image_ops"]["operation"] == "set-dpi"
    assert set_dpi_metadata["image_ops"]["heavy"] is False

    upscale_resize = abilities["upscale_resize"]
    upscale_resize_metadata = upscale_resize.extra_metadata or {}
    assert upscale_resize_metadata["governance"]["scopes"] == ["internal", "admin"]
    assert upscale_resize_metadata["presentation"]["visible"] is False
    assert upscale_resize_metadata["presentation"]["operation_label"] == "内部尺寸处理"
    assert upscale_resize_metadata["execution_target"] == "image_ops"
    assert upscale_resize_metadata["image_ops"]["operation"] == "upscale-resize"
    assert upscale_resize_metadata["image_ops"]["heavy"] is True

    seamless = abilities["seamless_production_normalize"]
    seamless_metadata = seamless.extra_metadata or {}
    assert seamless_metadata["governance"]["scopes"] == ["internal", "admin", "business-workflow"]
    assert seamless_metadata["presentation"]["visible"] is False
    assert seamless_metadata["presentation"]["operation_label"] == "连续图生产锁边"


def test_seed_retires_unconfigured_openai_and_seedream_image_routes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ensure_default_abilities(session)
        records = {
            (row.provider, row.capability_key): row.status
            for row in session.execute(select(Ability)).scalars().all()
        }

    assert records[("openai", "gpt_image_2_generate")] == "inactive"
    assert records[("openai", "gpt_image_2_edit")] == "inactive"
    assert records[("volcengine", "doubao_seedream_4_5")] == "inactive"
    assert records[("volcengine", "doubao_seedream_4_0")] == "inactive"
    assert records[("openai_compatible", "gpt_image_2_generate")] == "active"
    assert records[("openai_compatible", "gpt_image_2_edit")] == "active"


def test_seed_repairs_stale_comfyui_allowed_executor_ids() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Ability(
                id="comfyui_yinhua_tiqu",
                provider="comfyui",
                category="image_generation",
                capability_key="yinhua_tiqu",
                display_name="印花提取",
                description="stale route metadata",
                status="active",
                ability_type="comfyui",
                workflow_id="workflow_comfyui_yinhua_tiqu_v1",
                default_params={},
                input_schema={},
                extra_metadata={
                    "seed_version": 999,
                    "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
                    "routing_policy": "queue",
                    "custom_note": "keep me",
                },
            )
        )
        session.commit()

        ensure_default_abilities(session)

        refreshed = session.execute(
            select(Ability).where(Ability.provider == "comfyui", Ability.capability_key == "yinhua_tiqu")
        ).scalar_one()
        metadata = refreshed.extra_metadata or {}

    assert metadata["allowed_executor_ids"] == [
        "executor_comfyui_seamless_117",
        "executor_comfyui_pattern_extract_158",
    ]
    assert metadata["routing_policy"] == "queue"
    assert metadata["routing"]["allowed_executor_ids"] == [
        "executor_comfyui_seamless_117",
        "executor_comfyui_pattern_extract_158",
    ]
    assert metadata["routing"]["selection_policy"] == "queue"
    assert metadata["custom_note"] == "keep me"


def test_seed_refreshes_controlled_description_when_seed_version_increases() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Ability(
                id="comfyui_flux2_9b_liebian_sifang",
                provider="comfyui",
                category="image_generation",
                capability_key="flux2_9b_liebian_sifang",
                display_name="旧名称",
                description="旧文案：最终拼缝结果。",
                status="active",
                ability_type="comfyui",
                default_params={},
                input_schema={},
                extra_metadata={"seed_version": 3},
            )
        )
        session.commit()

        ensure_default_abilities(session)

        refreshed = session.get(Ability, "comfyui_flux2_9b_liebian_sifang")
        assert refreshed is not None
        metadata = refreshed.extra_metadata or {}

    assert refreshed.display_name == "ComfyUI · FLUX2裂变+四方"
    assert "连续图候选" in refreshed.description
    assert metadata["seed_version"] == 3
    assert metadata["catalog_text_seed_version"] == 3


def test_seed_repairs_empty_schema_field_list() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Ability(
                id="baidu_colourize",
                provider="baidu",
                category="image_process",
                capability_key="colourize",
                display_name="百度 · 老照片上色",
                description="stale empty schema",
                status="active",
                ability_type="api",
                default_params={},
                input_schema={"fields": []},
                extra_metadata={},
            )
        )
        session.commit()

        ensure_default_abilities(session)

        refreshed = session.execute(
            select(Ability).where(Ability.provider == "baidu", Ability.capability_key == "colourize")
        ).scalar_one()
        fields = (refreshed.input_schema or {}).get("fields")

    assert isinstance(fields, list)
    assert [field.get("name") for field in fields] == ["image_url"]
