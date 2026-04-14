from app.services.workflow_seed import DEFAULT_BINDING_SEEDS, DEFAULT_WORKFLOW_SEEDS


def test_new_comfyui_workflow_seeds_exist_with_expected_output_nodes():
    workflows = {seed.workflow_key: seed for seed in DEFAULT_WORKFLOW_SEEDS}

    assert workflows["beijing_koutu"].metadata["output_node_ids"] == ["4"]
    assert workflows["toubu_kouxiang"].metadata["output_node_ids"] == ["140"]
    assert workflows["flux2_9b_liebian_sifang"].metadata["output_node_ids"] == ["111"]


def test_new_comfyui_bindings_cover_two_executors():
    binding_pairs = {(seed.workflow_id, seed.executor_id) for seed in DEFAULT_BINDING_SEEDS}

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
