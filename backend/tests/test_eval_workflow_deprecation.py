from app.services.eval_workflow_deprecation import (
    enrich_metadata_with_eval_workflow_deprecation,
    resolve_eval_workflow_deprecation,
)
from app.services.eval_workflow_presentation import is_eval_workflow_visible


def test_resolve_eval_workflow_deprecation_payload() -> None:
    metadata = enrich_metadata_with_eval_workflow_deprecation(
        {},
        status="active",
        deprecation_override={
            "replacement_workflow_id": "7631174682116358144",
            "replacement_display_name": "扩图 · flux2_klein_9b_outpaint",
            "reason": "统一扩图入口",
            "retirement_mode": "hide_public",
        },
    )

    assert resolve_eval_workflow_deprecation(status="active", metadata=metadata) == {
        "is_deprecated": True,
        "replacement_workflow_id": "7631174682116358144",
        "replacement_display_name": "扩图 · flux2_klein_9b_outpaint",
        "reason": "统一扩图入口",
        "retirement_mode": "hide_public",
    }


def test_deprecated_eval_workflow_is_hidden_from_public_list() -> None:
    metadata = enrich_metadata_with_eval_workflow_deprecation(
        {"presentation": {"visible": True}},
        status="active",
        deprecation_override={
            "replacement_workflow_id": "7631174682116358144",
            "retirement_mode": "hide_public",
        },
    )

    assert not is_eval_workflow_visible(
        status="active",
        category="图延伸类",
        workflow_id="7598587935331450880",
        name="ComfyUI 扩图 · comfyuo_tukuozhan",
        parameters_schema={"fields": [{"name": "url"}]},
        output_schema={"fields": [{"name": "output"}]},
        metadata=metadata,
    )
