from __future__ import annotations

from app.services.ability_governance import (
    build_business_status,
    enrich_metadata_with_governance,
    resolve_ability_governance,
)


def test_resolve_governance_prefers_surface_scopes_and_queue_policy() -> None:
    metadata = {
        "presentation": {"surfaces": {"admin": True, "eval": True, "coze": False}},
        "routing_policy": "queue",
    }

    governance = resolve_ability_governance(status="active", metadata=metadata)

    assert governance == {
        "scopes": ["admin", "eval"],
        "release_status": "eval_ready",
        "route_policy": "queue_aware",
        "quality_status": "usable",
    }


def test_resolve_governance_uses_explicit_override_when_present() -> None:
    metadata = {
        "presentation": {"surfaces": {"client": True}},
        "governance": {
            "scopes": ["internal", "coze"],
            "release_status": "published",
            "route_policy": "fixed",
            "quality_status": "needs_optimization",
        },
    }

    governance = resolve_ability_governance(status="active", metadata=metadata)

    assert governance == {
        "scopes": ["internal", "coze"],
        "release_status": "published",
        "route_policy": "fixed",
        "quality_status": "needs_optimization",
    }


def test_enrich_metadata_with_governance_preserves_existing_metadata() -> None:
    metadata = {
        "presentation": {"surfaces": {"coze": True}},
        "model_id": "foo-model",
    }

    enriched = enrich_metadata_with_governance(metadata, status="active")

    assert enriched["model_id"] == "foo-model"
    assert enriched["presentation"] == {"surfaces": {"coze": True}}
    assert enriched["governance"] == {
        "scopes": ["coze"],
        "release_status": "published",
        "route_policy": "fixed",
        "quality_status": "usable",
    }


def test_build_business_status_returns_business_facing_labels() -> None:
    business_status = build_business_status(
        {
            "scopes": ["admin", "eval", "coze"],
            "release_status": "published",
            "quality_status": "needs_optimization",
        }
    )

    assert business_status == {
        "availability_code": "available",
        "availability_label": "可用",
        "stability_code": "optimizing",
        "stability_label": "优化中",
        "surface_labels": ["管理端", "测评端", "Coze"],
    }
