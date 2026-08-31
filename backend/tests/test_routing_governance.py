from app.services.routing_governance import (
    build_executor_business_status,
    enrich_ability_metadata_with_routing,
    enrich_executor_config_with_routing,
    normalize_ability_routing,
    normalize_executor_routing,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.models.integration import Executor
from app.models.user import User  # noqa: F401 - ensure users table is registered for FK resolution
from app.services.executor_seed import ensure_default_executors


def test_normalize_executor_routing_derives_defaults_and_tags() -> None:
    config = {"tags": ["ComfyUI", "pattern_extract"]}
    routing = normalize_executor_routing(config, max_concurrency=3)
    assert routing == {
        "routing_enabled": True,
        "fallback_only": False,
        "selection_policy": "auto",
        "tags": ["comfyui", "pattern_extract"],
        "allowed_workflow_keys": [],
        "blocked_workflow_keys": [],
        "concurrency_limit": 3,
    }


def test_enrich_executor_config_with_routing_embeds_normalized_block() -> None:
    config = enrich_executor_config_with_routing(
        {
            "baseUrl": "http://127.0.0.1:8079",
            "routing": {"selection_policy": "queue", "fallback_only": True},
            "tag": "seamless",
        },
        max_concurrency=2,
    )
    assert config["routing"] == {
        "routing_enabled": True,
        "fallback_only": True,
        "selection_policy": "queue",
        "tags": ["seamless"],
        "allowed_workflow_keys": [],
        "blocked_workflow_keys": [],
        "concurrency_limit": 2,
    }
    assert build_executor_business_status(config["routing"])["execution_mode_code"] == "fallback_only"


def test_normalize_ability_routing_supports_legacy_keys() -> None:
    metadata = {
        "routing_policy": "round_robin",
        "required_tags": ["seamless"],
        "allowed_executor_ids": ["executor_a", "executor_b"],
        "fallback_to_default": False,
        "action": "generic",
        "workflow_key": "sifang_lianxu",
    }
    routing = normalize_ability_routing(metadata)
    assert routing == {
        "selection_policy": "round_robin",
        "required_executor_tags": ["seamless"],
        "allowed_executor_ids": ["executor_a", "executor_b"],
        "fallback_to_default": False,
        "action": "generic",
        "workflow_key": "sifang_lianxu",
    }


def test_normalize_ability_routing_defaults_comfyui_to_general_lane() -> None:
    routing = normalize_ability_routing(
        {
            "executor_type": "comfyui",
            "workflow_key": "flux_strong_hq_softstyle_fission",
            "routing_policy": "queue",
        }
    )
    assert routing == {
        "selection_policy": "queue",
        "required_executor_tags": ["comfyui-general"],
        "allowed_executor_ids": [],
        "fallback_to_default": True,
        "action": "generic",
        "workflow_key": "flux_strong_hq_softstyle_fission",
    }


def test_enrich_ability_metadata_with_routing_persists_normalized_block() -> None:
    metadata = enrich_ability_metadata_with_routing(
        {
            "executor_type": "comfyui",
            "routing": {
                "selection_policy": "fixed",
                "required_executor_tags": "pattern_extract",
                "allowed_executor_ids": "executor_comfyui_pattern_extract_158",
            },
        }
    )
    assert metadata["routing"] == {
        "selection_policy": "fixed",
        "required_executor_tags": ["pattern_extract"],
        "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
        "fallback_to_default": True,
        "action": "generic",
        "workflow_key": None,
    }


def test_executor_seed_persists_routing_block_to_config() -> None:
    """执行器 seed 应保留 233 历史记录但标记 inactive，同时保持 158 为活动生产节点。"""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        changed = ensure_default_executors(session)
        assert changed in {True, False}
        rows = session.execute(select(Executor)).scalars().all()
        assert rows
        for row in rows:
            routing = (row.config or {}).get("routing")
            assert isinstance(routing, dict)
            assert routing["concurrency_limit"] == max(1, int(row.max_concurrency or 1))
            assert "selection_policy" in routing
            if row.type == "comfyui":
                assert "comfyui-general" in (routing.get("tags") or [])
        by_id = {row.id: row for row in rows}
        node_233 = by_id["executor_comfyui_seamless_117"]
        node_158 = by_id["executor_comfyui_pattern_extract_158"]
        assert node_233.name == "ComfyUI 4090 · 233 · 117.50.216.233"
        assert node_158.name == "ComfyUI 5090 · 158 · 117.50.80.158"
        assert node_233.status == "inactive"
        assert node_158.status == "active"
        assert {"gpu:4090", "host:233", "comfyui-233"}.issubset(set(node_233.config["tags"]))
        assert {"gpu:5090", "host:158", "comfyui-158"}.issubset(set(node_158.config["tags"]))


def test_executor_seed_repairs_comfyui_display_name_and_tags() -> None:
    """seed 修复 233 展示信息时也必须同步 inactive，不能因修复旧记录而重新启用节点。"""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Executor(
                id="executor_comfyui_seamless_117",
                name="ComfyUI 四方连续 · 117.50.216.233",
                type="comfyui",
                base_url="http://117.50.216.233:8079",
                status="active",
                weight=1,
                max_concurrency=10,
                config={"baseUrl": "http://117.50.216.233:8079", "tags": ["comfyui-general"]},
            )
        )
        session.commit()

        changed = ensure_default_executors(session)
        refreshed = session.get(Executor, "executor_comfyui_seamless_117")

        assert changed is True
        assert refreshed is not None
        assert refreshed.name == "ComfyUI 4090 · 233 · 117.50.216.233"
        assert refreshed.status == "inactive"
        assert {"gpu:4090", "host:233", "comfyui-233"}.issubset(set(refreshed.config["tags"]))
