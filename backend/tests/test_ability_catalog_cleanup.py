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


def test_seed_applies_cleanup_for_huawen_kuotu_and_expand_mask_color() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ensure_default_abilities(session)
        abilities = {
            row.capability_key: row
            for row in session.execute(select(Ability)).scalars().all()
            if row.capability_key in {"huawen_kuotu", "expand_mask_color"}
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
