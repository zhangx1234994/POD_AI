from app.services.eval_workflow_presentation import (
    build_eval_workflow_presentation_sort_key,
    enrich_metadata_with_eval_workflow_presentation,
    is_eval_workflow_visible,
    resolve_eval_workflow_presentation,
)


def test_resolve_eval_workflow_presentation_for_fission_workflow() -> None:
    presentation = resolve_eval_workflow_presentation(
        status="active",
        category="图裂变",
        workflow_id="7629024620879806464",
        name="文字增强 · qwen2512_print_shape_text_enhance",
        parameters_schema={
            "fields": [
                {"name": "url"},
                {"name": "prompt"},
                {"name": "bili"},
                {"name": "count", "defaultValue": "4"},
            ]
        },
        output_schema={
            "fields": [
                {"name": "output", "description": "回调 task id"},
                {"name": "prompt", "description": "提示词反馈"},
                {"name": "ip", "description": "执行节点 IP"},
            ]
        },
        metadata={},
    )

    assert presentation == {
        "visible": True,
        "sort_order": 4000,
        "category_label": "图裂变",
        "usage_hint": "适合先验证单张结果，再决定是否进入批量裂变",
        "operation_label": "图像裂变",
        "variant_label": "文字增强版",
        "entry_mode": "single_image",
        "result_mode": "callback_image",
        "supports_batch": True,
        "recommended_repeat_count": 4,
    }


def test_enrich_eval_workflow_presentation_preserves_parameter_defaults() -> None:
    enriched = enrich_metadata_with_eval_workflow_presentation(
        {"parameter_defaults": {"bili": "50"}},
        status="active",
        category="图延伸类",
        workflow_id="7631174682116358144",
        name="扩图 · flux2_klein_9b_outpaint",
        parameters_schema={"fields": [{"name": "url"}, {"name": "expand_left"}]},
        output_schema={"fields": [{"name": "output"}, {"name": "ip"}]},
        presentation_override={
            "sort_order": 2105,
            "usage_hint": "适合验证不同方向的扩边效果",
            "operation_label": "扩图",
        },
    )

    assert enriched["parameter_defaults"] == {"bili": "50"}
    assert enriched["presentation"] == {
        "visible": True,
        "sort_order": 2105,
        "category_label": "图延伸类",
        "usage_hint": "适合验证不同方向的扩边效果",
        "operation_label": "扩图",
        "variant_label": "当前扩图主线",
        "entry_mode": "single_image",
        "result_mode": "image",
        "supports_batch": False,
        "recommended_repeat_count": 1,
    }


def test_eval_workflow_presentation_labels_tagging_as_image_analysis() -> None:
    presentation = resolve_eval_workflow_presentation(
        status="active",
        category="通用类",
        workflow_id="7597767702970630144",
        name="图片打标签 · Biaoqian_tiqu",
        parameters_schema={"fields": [{"name": "url", "label": "图片 URL"}]},
        output_schema={"fields": [{"name": "output", "type": "json", "description": "JSON 标签"}]},
        metadata={},
    )

    assert presentation["operation_label"] == "图片打标签"
    assert presentation["variant_label"] == "小参数标签版"
    assert presentation["result_mode"] == "structured_json"


def test_eval_workflow_presentation_detects_image_url_outputs() -> None:
    presentation = resolve_eval_workflow_presentation(
        status="active",
        category="通用类",
        workflow_id="7597760543788630016",
        name="8K 高清放大",
        parameters_schema={"fields": [{"name": "url", "label": "图片 URL"}]},
        output_schema={"fields": [{"name": "output", "type": "text", "description": "图片 URL"}]},
        metadata={},
    )

    assert presentation["operation_label"] == "图像原子处理"
    assert presentation["variant_label"] == "8K 高清放大"
    assert presentation["result_mode"] == "image_url"


def test_eval_workflow_presentation_normalizes_stale_auxiliary_metadata() -> None:
    presentation = resolve_eval_workflow_presentation(
        status="active",
        category="通用类",
        workflow_id="7600254097513512960",
        name="图片打标签 · Biaoqian_tiqu_3",
        parameters_schema={"fields": [{"name": "url", "label": "图片 URL"}]},
        output_schema={"fields": [{"name": "output", "type": "text", "description": "标签文本"}]},
        metadata={
            "presentation": {
                "operation_label": "花纹提取",
                "variant_label": "旧标签",
                "result_mode": "text",
            }
        },
    )

    assert presentation["operation_label"] == "图片打标签"
    assert presentation["variant_label"] == "Lits 标签版"
    assert presentation["result_mode"] == "structured_json"


def test_eval_workflow_presentation_normalizes_stale_image_url_metadata() -> None:
    presentation = resolve_eval_workflow_presentation(
        status="active",
        category="通用类",
        workflow_id="7598589746561941504",
        name="DPI 增分",
        parameters_schema={"fields": [{"name": "url", "label": "图片 URL"}]},
        output_schema={"fields": [{"name": "output", "type": "text", "description": "图片 URL"}]},
        metadata={
            "presentation": {
                "operation_label": "通用处理",
                "variant_label": "旧标签",
                "result_mode": "text",
            }
        },
    )

    assert presentation["operation_label"] == "图像原子处理"
    assert presentation["variant_label"] == "DPI 增分"
    assert presentation["result_mode"] == "image_url"


def test_eval_workflow_visibility_and_sort_follow_presentation() -> None:
    metadata = enrich_metadata_with_eval_workflow_presentation(
        {},
        status="inactive",
        category="通用类",
        workflow_id="7597535455856295936",
        name="提示词提取 · tishici_tiqu",
        parameters_schema={"fields": [{"name": "url"}]},
        output_schema={"fields": [{"name": "output"}]},
        presentation_override={"visible": True, "sort_order": 5050},
    )

    assert is_eval_workflow_visible(
        status="inactive",
        category="通用类",
        workflow_id="7597535455856295936",
        name="提示词提取 · tishici_tiqu",
        parameters_schema={"fields": [{"name": "url"}]},
        output_schema={"fields": [{"name": "output"}]},
        metadata=metadata,
    )
    assert build_eval_workflow_presentation_sort_key(
        status="inactive",
        category="通用类",
        workflow_id="7597535455856295936",
        name="提示词提取 · tishici_tiqu",
        parameters_schema={"fields": [{"name": "url"}]},
        output_schema={"fields": [{"name": "output"}]},
        metadata=metadata,
    ) == (5050, "通用类", "7597535455856295936", "提示词提取 · tishici_tiqu")
