from app.routers.admin_abilities import (
    _get_template_registry,
    _resolve_template_snapshot,
    _set_template_registry,
    _validate_template_payload,
)


def test_validate_template_payload_reports_missing_field_key() -> None:
    errors, warnings = _validate_template_payload(
        default_params={},
        input_schema={"fields": [{"type": "text"}]},
        metadata={"api_type": "market_image_to_image"},
    )
    assert "input_schema.fields[1] 缺少 key" in errors
    assert any("metadata.model_id" in item for item in warnings)


def test_validate_template_payload_warns_when_metadata_missing() -> None:
    errors, warnings = _validate_template_payload(
        default_params={},
        input_schema={"fields": [{"key": "prompt", "type": "text"}]},
        metadata={},
    )
    assert errors == []
    assert any("metadata.api_type" in item for item in warnings)


def test_template_registry_round_trip() -> None:
    metadata = {"api_type": "comfyui_workflow"}
    registry = {"current_template_id": "tpl_1", "history": [{"id": "tpl_1"}]}
    merged = _set_template_registry(metadata, registry)
    loaded = _get_template_registry(merged)
    assert loaded["current_template_id"] == "tpl_1"
    assert isinstance(loaded["history"], list) and len(loaded["history"]) == 1


def test_resolve_template_snapshot_uses_current_and_history_count() -> None:
    metadata = {
        "__template_registry": {
            "current_template_id": "tpl_live",
            "history": [{"id": "tpl_live"}, {"id": "tpl_old"}, {"foo": "bar"}],
        }
    }
    current, history_count = _resolve_template_snapshot(metadata)
    assert current == "tpl_live"
    assert history_count == 2
