from app.services.workflow_seed import DEFAULT_BINDING_SEEDS, DEFAULT_WORKFLOW_SEEDS, load_comfy_workflow


PRODUCTION_COMFYUI_EXECUTORS = {"executor_comfyui_pattern_extract_158"}
RETIRED_COMFYUI_EXECUTOR = "executor_comfyui_seamless_117"

WORKFLOWS_WITH_RETIRED_233_HISTORY = {
    "workflow_comfyui_sifang_lianxu_v1",
    "workflow_comfyui_huawen_kuotu_v1",
    "workflow_comfyui_flux2_9b_liebian_sifang_v1",
}


def test_new_comfyui_workflow_seeds_exist_with_expected_output_nodes():
    workflows = {seed.workflow_key: seed for seed in DEFAULT_WORKFLOW_SEEDS}

    assert workflows["flux2_klein_9b_outpaint"].metadata["output_node_ids"] == ["9"]
    assert workflows["beijing_koutu"].metadata["output_node_ids"] == ["4"]
    assert workflows["toubu_kouxiang"].metadata["output_node_ids"] == ["140"]
    assert workflows["flux2_9b_liebian_sifang"].metadata["output_node_ids"] == ["111"]
    assert workflows["qwen2512_print_shape_text_enhance"].metadata["output_node_ids"] == ["29"]
    assert workflows["qwen2512_text2img_text_allowed"].metadata["output_node_ids"] == ["21"]
    assert workflows["flux_strong_hq_softstyle_fission"].metadata["output_node_ids"] == ["31"]


def test_new_comfyui_bindings_keep_233_history_but_enable_only_158():
    """233 的历史 binding 必须保留，但生产路由只能启用 158，避免发布后丢失审计或误发新任务。"""
    binding_pairs = {(seed.workflow_id, seed.executor_id) for seed in DEFAULT_BINDING_SEEDS}
    bindings_by_pair = {(seed.workflow_id, seed.executor_id): seed for seed in DEFAULT_BINDING_SEEDS}

    assert (
        "workflow_comfyui_flux2_klein_9b_outpaint_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_flux2_klein_9b_outpaint_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert (
        "workflow_comfyui_beijing_koutu_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_beijing_koutu_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert (
        "workflow_comfyui_toubu_kouxiang_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_toubu_kouxiang_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert (
        "workflow_comfyui_flux2_9b_liebian_sifang_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_flux2_9b_liebian_sifang_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert (
        "workflow_comfyui_qwen2512_print_shape_text_enhance_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_qwen2512_print_shape_text_enhance_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert (
        "workflow_comfyui_qwen2512_text2img_text_allowed_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_qwen2512_text2img_text_allowed_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert (
        "workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
        "executor_comfyui_seamless_117",
    ) in binding_pairs
    assert (
        "workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
        "executor_comfyui_pattern_extract_158",
    ) in binding_pairs
    assert bindings_by_pair[
        (
            "workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
            "executor_comfyui_seamless_117",
        )
    ].enabled is False
    for workflow_id in WORKFLOWS_WITH_RETIRED_233_HISTORY:
        assert bindings_by_pair[(workflow_id, "executor_comfyui_seamless_117")].enabled is False
        assert bindings_by_pair[(workflow_id, "executor_comfyui_pattern_extract_158")].enabled is True
    assert all(seed.enabled is False for seed in DEFAULT_BINDING_SEEDS if seed.executor_id == RETIRED_COMFYUI_EXECUTOR)


def test_core_comfyui_workflows_route_only_to_158():
    """所有生产 ComfyUI 工作流只启用 158；233 即使保留记录也不能进入候选集合。"""
    executors_by_workflow: dict[str, set[str]] = {}
    for seed in DEFAULT_BINDING_SEEDS:
        if seed.enabled:
            executors_by_workflow.setdefault(seed.workflow_id, set()).add(seed.executor_id)

    production_workflows = {
        "workflow_comfyui_yinhua_tiqu_v2",
        "workflow_comfyui_yinhua_tiqu_lora_8step_v1",
        "workflow_comfyui_duotu_ronghe_v1",
        "workflow_comfyui_e7_flux2_liebian_v1",
        "workflow_comfyui_flux2_klein_9b_outpaint_v1",
        "workflow_comfyui_beijing_koutu_v1",
        "workflow_comfyui_toubu_kouxiang_v1",
        "workflow_comfyui_qwen2512_print_shape_text_enhance_v1",
        "workflow_comfyui_qwen2512_text2img_text_allowed_v1",
        "workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
        *WORKFLOWS_WITH_RETIRED_233_HISTORY,
    }

    for workflow_id in production_workflows:
        assert executors_by_workflow[workflow_id] == PRODUCTION_COMFYUI_EXECUTORS


def test_high_frequency_flux_strong_fission_routes_only_to_158():
    """高频裂变能力同样必须遵守 158-only 白名单，不能因历史高频配置继续命中 233。"""
    from app.constants.abilities import COMFYUI_ABILITIES

    for ability_key, definition in COMFYUI_ABILITIES.items():
        metadata = definition.get("metadata") or {}
        if metadata.get("workflow_key") != "flux_strong_hq_softstyle_fission":
            continue

        assert metadata.get("allowed_executor_ids") == ["executor_comfyui_pattern_extract_158"], ability_key
        assert "String" not in (metadata.get("required_node_keys") or []), ability_key


def test_qwen2512_text_enhance_negative_prompt_does_not_suppress_text():
    graph = load_comfy_workflow("qwen2512_print_shape_text_enhance")
    negative_prompt = str(graph["16"]["inputs"]["text"])

    assert "text" not in negative_prompt.lower()
    assert "illegible lettering" in negative_prompt
    assert "broken glyphs" in negative_prompt


def test_flux2_klein_9b_outpaint_uses_20260525_scale_route():
    graph = load_comfy_workflow("flux2_klein_9b_outpaint")

    assert graph["9"]["inputs"]["filename_prefix"] == "Flux2-Klein"
    assert graph["76"]["class_type"] == "LoadImage"
    assert graph["102"]["class_type"] == "ImagePadForOutpaint"
    assert graph["102"]["inputs"]["feathering"] == 20
    assert graph["104"]["class_type"] == "DrawMaskOnImage"
    assert graph["104"]["inputs"]["device"] == "gpu"
    assert graph["104"]["inputs"]["opacity"] == 0.5
    assert graph["121"]["class_type"] == "ImageScaleToTotalPixels"
    assert graph["119"]["inputs"]["image"] == ["121", 0]
    assert graph["125"]["inputs"]["pixels"] == ["121", 0]
    assert graph["130"]["inputs"]["image"] == ["109", 0]
    assert "123" not in graph
    assert "133" not in graph
    assert "ColorMatch" not in {node.get("class_type") for node in graph.values()}


def test_flux_strong_hq_softstyle_fission_workflow_is_stored_with_output_node():
    graph = load_comfy_workflow("flux_strong_hq_softstyle_fission")

    assert graph["31"]["inputs"]["filename_prefix"] == "05_FluxStrongHQSoftStyle"
    assert graph["10"]["class_type"] == "LoadImage"
    assert graph["30"]["class_type"] == "ColorMatch"
