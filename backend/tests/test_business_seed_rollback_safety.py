from __future__ import annotations

import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.core.db import Base
from app.models.integration import Ability, BusinessCapability
from app.models.user import User as _User  # noqa: F401 - registers the users table for SQLAlchemy metadata.
from app.services.ability_seed import ensure_default_abilities
from app.services.business_seed import ensure_default_business_capabilities


def _testing_sessionmaker():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_business_seed_keeps_rollback_safety_versions_available() -> None:
    testing_session = _testing_sessionmaker()

    with testing_session() as session:
        ensure_default_abilities(session)
        assert ensure_default_business_capabilities(session) is True
        assert ensure_default_business_capabilities(session) is False

        for business_key in ("pattern_extract", "fission", "outpaint"):
            rows = (
                session.execute(
                    select(BusinessCapability)
                    .where(BusinessCapability.business_key == business_key)
                    .order_by(BusinessCapability.release_time.desc())
                )
                .scalars()
                .all()
            )
            defaults = [row for row in rows if row.status == "active" and row.is_default]
            rollback_versions = [
                row
                for row in rows
                if row.status == "active"
                and not row.is_default
                and isinstance(row.extra_metadata, dict)
                and row.extra_metadata.get("rollbackSafety") is True
            ]

            assert len(defaults) == 1
            assert rollback_versions
            assert rollback_versions[0].release_time < defaults[0].release_time

            primary_ability_id = rollback_versions[0].recipe["primaryAbilityId"]
            assert session.get(Ability, primary_ability_id) is not None

        fission_fallback = session.get(BusinessCapability, "biz_fission_rollback_e7_flux2_liebian")
        outpaint_fallback = session.get(BusinessCapability, "biz_outpaint_rollback_huawen_kuotu")
        pattern_extract_default = session.get(BusinessCapability, "biz_pattern_extract_v1_yinhua_tiqu")
        pattern_extract_fallback = session.get(BusinessCapability, "biz_pattern_extract_rollback_lora_8step")

        assert pattern_extract_default is not None
        assert pattern_extract_default.recipe["primaryAbilityId"] == "comfyui_yinhua_tiqu"
        assert pattern_extract_default.version == "v1"
        assert pattern_extract_default.is_default is True

        assert pattern_extract_fallback is not None
        assert pattern_extract_fallback.recipe["primaryAbilityId"] == "comfyui_yinhua_tiqu_lora_8step"
        assert pattern_extract_fallback.version == "rollback-lora-8step-v1"
        assert pattern_extract_fallback.is_default is False

        assert fission_fallback is not None
        assert fission_fallback.recipe["primaryAbilityId"] == "comfyui_e7_flux2_liebian"
        assert fission_fallback.version == "rollback-e7-v1"
        assert fission_fallback.is_default is False

        assert outpaint_fallback is not None
        assert outpaint_fallback.recipe["primaryAbilityId"] == "comfyui_huawen_kuotu"
        assert outpaint_fallback.version == "rollback-huawen-v1"
        assert outpaint_fallback.is_default is False
