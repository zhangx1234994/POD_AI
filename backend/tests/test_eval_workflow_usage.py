from app.services.eval_workflow_usage import (
    enrich_metadata_with_eval_workflow_usage,
    resolve_eval_workflow_usage,
)


def test_resolve_eval_workflow_usage_for_lora_batch_workflow() -> None:
    usage = resolve_eval_workflow_usage(
        category="花纹提取类",
        parameters_schema={
            "fields": [
                {"name": "url"},
                {"name": "prompt"},
                {"name": "lora", "resourceType": "lora"},
                {"name": "count", "defaultValue": "3"},
            ]
        },
        metadata={
            "presentation": {
                "supports_batch": True,
                "result_mode": "callback_image",
            }
        },
    )

    assert usage == {
        "single_run_enabled": True,
        "batch_enabled": True,
        "docs_enabled": True,
        "recommended_entry": "lora_batch",
        "supports_annotation": True,
        "requires_resource_options": True,
        "resource_option_types": ["lora"],
    }


def test_enrich_eval_workflow_usage_preserves_existing_metadata() -> None:
    enriched = enrich_metadata_with_eval_workflow_usage(
        {
            "presentation": {"supports_batch": False, "result_mode": "text"},
            "parameter_defaults": {"bili": "50"},
        },
        category="通用类",
        parameters_schema={"fields": [{"name": "prompt"}]},
        usage_override={
            "recommended_entry": "parameter_form",
            "docs_enabled": False,
        },
    )

    assert enriched["parameter_defaults"] == {"bili": "50"}
    assert enriched["usage"] == {
        "single_run_enabled": True,
        "batch_enabled": False,
        "docs_enabled": False,
        "recommended_entry": "parameter_form",
        "supports_annotation": False,
        "requires_resource_options": False,
        "resource_option_types": [],
    }
