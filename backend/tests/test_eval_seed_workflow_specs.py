from app.services.eval_seed import (
    DEFAULT_EVAL_WORKFLOW_BY_ID,
    DEPRECATED_EVAL_WORKFLOW_IDS,
    FISSION_WORKFLOW_IDS,
    IP_OUTPUT_WORKFLOW_IDS,
    PROMPT_OUTPUT_WORKFLOW_IDS,
)
from app.services.eval_workflow_presentation import resolve_eval_workflow_presentation


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
    assert _field_by_name(with_prompt, "bili").get("label") == "重绘幅度(%)"
    assert "denoise" in str(_field_by_name(with_prompt, "bili").get("description") or "")
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
    assert bili.get("label") == "重绘幅度(%)"
    assert "相似度" not in str(bili)
    assert bili.get("required") is True

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


def test_20260512_native_eval_entries_are_visible_and_badged():
    gpt = DEFAULT_EVAL_WORKFLOW_BY_ID["business_fission_gpt_image2_vl_v1"]
    comfy = DEFAULT_EVAL_WORKFLOW_BY_ID["business_fission_comfyui_vl_control_v1"]
    evaluator = DEFAULT_EVAL_WORKFLOW_BY_ID["ability_fission_generated_image_evaluate_v1"]

    assert gpt["category"] == "图裂变"
    assert comfy["category"] == "图裂变"
    assert evaluator["category"] == "图像理解"
    assert gpt["metadata"]["eval_execution"] == {
        "mode": "business_run",
        "business_key": "fission",
        "version": "gpt-image2-vl-v2",
    }
    assert comfy["metadata"]["eval_execution"] == {
        "mode": "business_run",
        "business_key": "fission",
        "version": "comfyui-vl-control-v2",
    }
    assert evaluator["metadata"]["eval_execution"]["mode"] == "ability_task"
    assert evaluator["metadata"]["eval_execution"]["ability_id"] == "vl_fission_generated_image_evaluate"
    assert "新版" not in gpt["name"]
    assert "新版" not in comfy["name"]
    assert "新版" not in evaluator["name"]
    assert "已优化" in gpt["metadata"]["presentation"]["badges"]
    assert "已优化" in comfy["metadata"]["presentation"]["badges"]
    assert "新版" not in gpt["metadata"]["presentation"]["badges"]
    assert "新版" not in comfy["metadata"]["presentation"]["badges"]
    assert "新版" in evaluator["metadata"]["presentation"]["badges"]
    assert gpt["metadata"].get("isNewVersion") is False
    assert comfy["metadata"].get("isNewVersion") is False
    assert gpt["metadata"]["presentation"]["release_time"] == "2026-05-12"
    assert gpt["metadata"]["presentation"]["update_time"] == "2026-05-13"
    assert comfy["metadata"]["presentation"]["release_time"] == "2026-05-12"
    assert comfy["metadata"]["presentation"]["update_time"] == "2026-05-14"
    assert "底层升级" in gpt["metadata"]["presentation"]["update_note"]
    assert "颜色锁定" in comfy["metadata"]["presentation"]["update_note"]
    gpt_fields = [f.get("name") for f in (gpt["parameters_schema"]["fields"] or []) if isinstance(f, dict)]
    comfy_fields = [f.get("name") for f in (comfy["parameters_schema"]["fields"] or []) if isinstance(f, dict)]
    assert "count" not in gpt_fields
    assert "count" not in comfy_fields
    assert _field_by_name(gpt, "variation_strength").get("defaultValue") == "same_series"
    assert _field_by_name(comfy, "bili").get("defaultValue") == "80%"
    assert _field_by_name(comfy, "profile").get("defaultValue") == "pattern_risk_routed_v4"
    assert _field_by_name(comfy, "reference_lock").get("defaultValue") == "0.42"
    assert _field_by_name(comfy, "color_lock").get("defaultValue") == "0.90"
    presets = comfy["metadata"]["presentation"].get("variation_presets")
    assert isinstance(presets, list)
    assert [item.get("key") for item in presets] == ["default-high", "safe", "object-strong", "color-free"]
    assert presets[0]["values"]["profile"] == "pattern_risk_routed_v4"
    assert "business_fission_gpt_image2_vl_v2" not in DEFAULT_EVAL_WORKFLOW_BY_ID
    assert "business_fission_comfyui_vl_colorlock_v2" not in DEFAULT_EVAL_WORKFLOW_BY_ID
    assert "business_fission_gpt_image2_vl_v2" in DEPRECATED_EVAL_WORKFLOW_IDS
    assert "business_fission_comfyui_vl_colorlock_v2" in DEPRECATED_EVAL_WORKFLOW_IDS
    assert "business_fission_gpt_image2_vl_v2" not in FISSION_WORKFLOW_IDS
    assert "business_fission_gpt_image2_vl_v1" not in FISSION_WORKFLOW_IDS
    assert "business_fission_comfyui_vl_control_v1" not in FISSION_WORKFLOW_IDS
    assert "business_fission_comfyui_vl_colorlock_v2" not in FISSION_WORKFLOW_IDS


def test_text_fission_user_editable_eval_entry_is_two_step_business_api():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["business_text_fission_qwen2512_text2img_user_editable_v1"]

    assert workflow["category"] == "图裂变"
    assert workflow["name"] == "文字强化裂变 · Qwen 文生图可编辑提示词版"
    assert workflow["metadata"]["eval_execution"] == {
        "mode": "business_run",
        "business_key": "text_fission",
        "version": "qwen2512-text2img-v1",
    }

    fields = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    names = [field.get("name") for field in fields if isinstance(field, dict)]
    assert names == [
        "url",
        "editable_prompt",
        "editable_negative_prompt",
        "width",
        "height",
    ]
    assert "count" not in names
    assert "bili" not in names
    assert _field_by_name(workflow, "editable_prompt").get("required") is True
    assert workflow["metadata"]["presentation"]["supports_batch"] is False


def test_eval_presentation_keeps_new_as_badge_not_name():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["business_fission_gpt_image2_vl_v1"]
    presentation = resolve_eval_workflow_presentation(
        status=workflow["status"],
        category=workflow["category"],
        workflow_id=workflow["workflow_id"],
        name=workflow["name"],
        parameters_schema=workflow["parameters_schema"],
        output_schema=workflow["output_schema"],
        metadata=workflow["metadata"],
    )

    assert presentation["variant_label"] == "GPT Image 2 + VL 控制版"
    assert "新版" not in presentation["variant_label"]
    assert "新版" not in presentation["badges"]
    assert "已优化" in presentation["badges"]
    assert presentation["release_time"] == "2026-05-12"
    assert presentation["update_time"] == "2026-05-13"


def test_gpt_image2_vl_eval_exposes_size_presets():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["business_fission_gpt_image2_vl_v1"]
    size = _field_by_name(workflow, "size")

    assert size.get("type") == "select"
    assert size.get("label") == "比例尺寸"
    assert size.get("defaultValue") == "auto"
    values = {str(item.get("value")) for item in (size.get("options") or []) if isinstance(item, dict)}
    assert {
        "auto",
        "1024x1024",
        "1536x1024",
        "1024x1536",
        "2048x2048",
        "2048x1152",
        "3840x2160",
        "2160x3840",
    } <= values


def test_20260512_image_tagging_workflow_is_visible_image_analysis_entry():
    workflow = DEFAULT_EVAL_WORKFLOW_BY_ID["7625930748914040832"]

    assert workflow["category"] == "图像理解"
    assert workflow["name"] == "图片打标签 · 结构化打标版"
    assert workflow["status"] == "active"

    params = ((workflow.get("parameters_schema") or {}).get("fields") or [])
    assert [field.get("name") for field in params if isinstance(field, dict)] == ["url"]
    assert _field_by_name(workflow, "url").get("type") == "image"

    presentation = resolve_eval_workflow_presentation(
        status=workflow["status"],
        category=workflow["category"],
        workflow_id=workflow["workflow_id"],
        name=workflow["name"],
        parameters_schema=workflow["parameters_schema"],
        output_schema=workflow["output_schema"],
        metadata=workflow["metadata"],
    )
    assert presentation["operation_label"] == "图片打标签"
    assert presentation["variant_label"] == "结构化打标版"
    assert presentation["result_mode"] == "structured_json"
