from app.services.eval_seed import (
    DEFAULT_EVAL_WORKFLOW_BY_ID,
    DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID,
    FISSION_WORKFLOW_IDS,
    IP_OUTPUT_WORKFLOW_IDS,
    OUTPAINTING_WORKFLOW_IDS,
    PROMPT_OUTPUT_WORKFLOW_IDS,
)


def _field_by_name(workflow: dict, name: str) -> dict:
    fields = ((workflow or {}).get("parameters_schema") or {}).get("fields") or []
    for field in fields:
        if isinstance(field, dict) and field.get("name") == name:
            return field
    return {}


def test_shengtu_workflow_supports_banana2_and_reference_images():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7602916576198656000"]

    moxing = _field_by_name(workflow, "moxing")
    options = moxing.get("options") or []
    values = {str(item.get("value")) for item in options if isinstance(item, dict)}
    assert {"1", "2", "3", "4"} <= values

    cankaotu = _field_by_name(workflow, "cankaotu")
    assert cankaotu.get("type") == "textarea"
    assert cankaotu.get("supportedModels") == ["1", "2", "4"]

    aspect_ratio = _field_by_name(workflow, "aspect_ratio")
    resolution = _field_by_name(workflow, "resolution")
    assert isinstance(aspect_ratio.get("modelOptions"), dict)
    assert isinstance(resolution.get("modelOptions"), dict)
    assert "4" in aspect_ratio.get("modelOptions")
    assert "4" in resolution.get("modelOptions")


def test_lora_query_workflow_output_contract():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7612002440056930304"]

    params = ((workflow or {}).get("parameters_schema") or {}).get("fields") or []
    assert params == []

    outputs = ((workflow or {}).get("output_schema") or {}).get("fields") or []
    names = [field.get("name") for field in outputs if isinstance(field, dict)]
    assert names == ["items", "lora_names"]


def test_new_fission_workflows_exist_under_fission_category():
    with_prompt = DEFAULT_EVAL_WORKFLOW_BY_ID["7622190276932534272"]
    without_prompt = DEFAULT_EVAL_WORKFLOW_BY_ID["7622193261276299264"]

    assert with_prompt["category"] == "图裂变"
    assert without_prompt["category"] == "图裂变"
    assert "7622190276932534272" in FISSION_WORKFLOW_IDS
    assert "7622193261276299264" in FISSION_WORKFLOW_IDS

    with_prompt_fields = ((with_prompt.get("parameters_schema") or {}).get("fields") or [])
    without_prompt_fields = ((without_prompt.get("parameters_schema") or {}).get("fields") or [])

    with_names = [f.get("name") for f in with_prompt_fields if isinstance(f, dict)]
    without_names = [f.get("name") for f in without_prompt_fields if isinstance(f, dict)]

    assert with_names == ["url", "height", "width", "bili", "prompt", "count"]
    assert without_names == ["url", "height", "width", "bili", "count"]
    for field in with_prompt_fields + without_prompt_fields:
        if not isinstance(field, dict):
            continue
        if field.get("name") in {"height", "width"}:
            assert field.get("required") is False
            assert field.get("defaultValue") == ""


def test_duotu_ronghe_workflow_matches_current_coze_contract():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7615600173695107072"]
    fields = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in fields if isinstance(f, dict)]

    assert names == ["url", "image_url_2", "image_url_3", "width", "height", "negative_prompt", "prompt", "seed"]
    assert "lora" not in names

    width = _field_by_name(workflow, "width")
    height = _field_by_name(workflow, "height")
    assert width.get("required") is False
    assert height.get("required") is False
    assert width.get("defaultValue") == ""
    assert height.get("defaultValue") == ""


def test_new_flux2_outpaint_workflow_matches_legacy_outpaint_contract():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7631174682116358144"]
    assert workflow["category"] == "图延伸类"
    assert workflow["workflow_id"] == "7631174682116358144"
    assert "7631174682116358144" in OUTPAINTING_WORKFLOW_IDS
    assert "7631174682116358144" in IP_OUTPUT_WORKFLOW_IDS
    assert "7631174682116358144" not in PROMPT_OUTPUT_WORKFLOW_IDS

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in params if isinstance(f, dict)]
    assert names == ["url", "expand_left", "expand_right", "expand_top", "expand_bottom"]

    outputs = ((workflow.get("output_schema") or {}).get("fields") or [])
    output_names = [f.get("name") for f in outputs if isinstance(f, dict)]
    assert output_names == ["output", "ip"]


def test_eval_workflow_metadata_defaults_exist_for_outpaint_and_fission() -> None:
    outpaint_metadata = DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID["7631174682116358144"]
    fission_metadata = DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID["7629024620879806464"]
    softstyle_fission_metadata = DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID["7631838631375667200"]
    legacy_outpaint_metadata = DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID["7598587935331450880"]
    queue_monitor_metadata = DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID["7601054603211177984"]
    callback_metadata = DEFAULT_EVAL_WORKFLOW_METADATA_BY_ID["7597556718159003648"]

    assert outpaint_metadata["presentation"]["visible"] is True
    assert outpaint_metadata["presentation"]["category_label"] == "图延伸类"
    assert isinstance(outpaint_metadata["presentation"]["sort_order"], int)
    assert outpaint_metadata["presentation"]["operation_label"] == "图像延伸"
    assert outpaint_metadata["presentation"]["entry_mode"] == "single_image"
    assert outpaint_metadata["presentation"]["result_mode"] == "callback_image"
    assert outpaint_metadata["presentation"]["supports_batch"] is False
    assert outpaint_metadata["parameter_defaults"] == {}
    assert outpaint_metadata["usage"] == {
        "single_run_enabled": True,
        "batch_enabled": False,
        "docs_enabled": True,
        "recommended_entry": "single_image",
        "supports_annotation": True,
        "requires_resource_options": False,
        "resource_option_types": [],
    }

    assert fission_metadata["presentation"]["visible"] is True
    assert fission_metadata["presentation"]["category_label"] == "图裂变"
    assert isinstance(fission_metadata["presentation"]["sort_order"], int)
    assert fission_metadata["presentation"]["operation_label"] == "图像裂变"
    assert fission_metadata["presentation"]["entry_mode"] == "single_image"
    assert fission_metadata["presentation"]["result_mode"] == "callback_image"
    assert fission_metadata["presentation"]["supports_batch"] is True
    assert fission_metadata["presentation"]["recommended_repeat_count"] == 4
    assert fission_metadata["usage"] == {
        "single_run_enabled": True,
        "batch_enabled": True,
        "docs_enabled": True,
        "recommended_entry": "single_image",
        "supports_annotation": True,
        "requires_resource_options": False,
        "resource_option_types": [],
    }

    assert softstyle_fission_metadata["presentation"]["visible"] is True
    assert softstyle_fission_metadata["presentation"]["category_label"] == "图裂变"
    assert softstyle_fission_metadata["presentation"]["sort_order"] == 4010
    assert softstyle_fission_metadata["presentation"]["operation_label"] == "图像裂变"
    assert softstyle_fission_metadata["presentation"]["entry_mode"] == "single_image"
    assert softstyle_fission_metadata["presentation"]["result_mode"] == "callback_image"
    assert softstyle_fission_metadata["presentation"]["supports_batch"] is True
    assert softstyle_fission_metadata["presentation"]["recommended_repeat_count"] == 4
    assert (
        softstyle_fission_metadata["presentation"]["usage_hint"]
        == "适合多元素花纹类默认高质量裂变，先看单张结果再决定是否批量放量。"
    )
    assert softstyle_fission_metadata["usage"] == {
        "single_run_enabled": True,
        "batch_enabled": True,
        "docs_enabled": True,
        "recommended_entry": "single_image",
        "supports_annotation": True,
        "requires_resource_options": False,
        "resource_option_types": [],
    }

    assert legacy_outpaint_metadata["presentation"]["visible"] is False
    assert legacy_outpaint_metadata["presentation"]["operation_label"] == "旧版扩图"
    assert legacy_outpaint_metadata["deprecation"]["replacement_workflow_id"] == "7631174682116358144"
    assert legacy_outpaint_metadata["deprecation"]["retirement_mode"] == "hide_public"

    assert queue_monitor_metadata["presentation"]["visible"] is False
    assert queue_monitor_metadata["presentation"]["operation_label"] == "内部监控"
    assert queue_monitor_metadata["deprecation"]["retirement_mode"] == "admin_only"
    assert queue_monitor_metadata["deprecation"]["reason"] == "内部排障工作流，不应作为业务评测入口暴露。"

    assert callback_metadata["presentation"]["visible"] is False
    assert callback_metadata["presentation"]["operation_label"] == "内部回调"
    assert callback_metadata["deprecation"]["retirement_mode"] == "admin_only"
    assert callback_metadata["deprecation"]["reason"] == "内部回调/排障工作流，不应作为业务评测入口暴露。"


def test_beijing_koutu_workflow_is_general_with_url_only():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7629023903431524352"]
    assert workflow["category"] == "通用类"
    assert workflow["workflow_id"] == "7629023903431524352"

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in params if isinstance(f, dict)]
    assert names == ["url"]

    outputs = ((workflow.get("output_schema") or {}).get("fields") or [])
    output_names = [f.get("name") for f in outputs if isinstance(f, dict)]
    assert "output" in output_names
    assert "ip" in output_names
    assert "7629023903431524352" in IP_OUTPUT_WORKFLOW_IDS


def test_toubu_kouxiang_workflow_is_general_with_url_only():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7629023041988591616"]
    assert workflow["category"] == "通用类"
    assert workflow["workflow_id"] == "7629023041988591616"

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in params if isinstance(f, dict)]
    assert names == ["url"]

    outputs = ((workflow.get("output_schema") or {}).get("fields") or [])
    output_names = [f.get("name") for f in outputs if isinstance(f, dict)]
    assert "output" in output_names
    assert "ip" in output_names
    assert "7629023041988591616" in IP_OUTPUT_WORKFLOW_IDS


def test_qwen2512_print_shape_text_enhance_is_fission_with_prompt_and_bili():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7629024620879806464"]
    assert workflow["category"] == "图裂变"
    assert workflow["workflow_id"] == "7629024620879806464"
    assert "7629024620879806464" in FISSION_WORKFLOW_IDS
    assert "7629024620879806464" in PROMPT_OUTPUT_WORKFLOW_IDS
    assert "7629024620879806464" in IP_OUTPUT_WORKFLOW_IDS

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in params if isinstance(f, dict)]
    assert names == ["url", "prompt", "bili", "count"]

    bili = _field_by_name(workflow, "bili")
    assert bili.get("label") == "相似度(%)"
    assert bili.get("required") is True

    outputs = ((workflow.get("output_schema") or {}).get("fields") or [])
    output_names = [f.get("name") for f in outputs if isinstance(f, dict)]
    assert "output" in output_names
    assert "prompt" in output_names
    assert "ip" in output_names


def test_flux_strong_hq_softstyle_is_fission_with_bili_and_size_controls():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7631838631375667200"]
    assert workflow["category"] == "图裂变"
    assert workflow["workflow_id"] == "7631838631375667200"
    assert "7631838631375667200" in FISSION_WORKFLOW_IDS
    assert "7631838631375667200" in PROMPT_OUTPUT_WORKFLOW_IDS
    assert "7631838631375667200" in IP_OUTPUT_WORKFLOW_IDS

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in params if isinstance(f, dict)]
    assert names == ["url", "height", "width", "bili", "count"]

    bili = _field_by_name(workflow, "bili")
    assert bili.get("label") == "相似度(%)"
    assert bili.get("required") is True

    width = _field_by_name(workflow, "width")
    height = _field_by_name(workflow, "height")
    assert width.get("required") is False
    assert height.get("required") is False
    assert width.get("defaultValue") == ""
    assert height.get("defaultValue") == ""

    outputs = ((workflow.get("output_schema") or {}).get("fields") or [])
    output_names = [f.get("name") for f in outputs if isinstance(f, dict)]
    assert "output" in output_names
    assert "prompt" in output_names
    assert "ip" in output_names


def test_flux2_9b_liebian_sifang_is_fission_and_seamless():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7629026792103215104"]
    assert workflow["category"] == "图裂变"
    assert workflow["workflow_id"] == "7629026792103215104"
    assert "7629026792103215104" in FISSION_WORKFLOW_IDS
    assert "7629026792103215104" in PROMPT_OUTPUT_WORKFLOW_IDS
    assert "7629026792103215104" in IP_OUTPUT_WORKFLOW_IDS

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [f.get("name") for f in params if isinstance(f, dict)]
    assert names == ["url", "prompt", "count"]

    outputs = ((workflow.get("output_schema") or {}).get("fields") or [])
    output_names = [f.get("name") for f in outputs if isinstance(f, dict)]
    assert "output" in output_names
    assert "prompt" in output_names
    assert "ip" in output_names
