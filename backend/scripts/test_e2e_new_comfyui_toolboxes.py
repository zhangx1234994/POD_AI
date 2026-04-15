#!/usr/bin/env python3
"""End-to-end smoke test for the 4 new ComfyUI standalone toolboxes.

Directly submits prompt graphs to ComfyUI executor nodes and polls /history
until completion. This verifies that:
1. Workflow JSON is valid on the executor.
2. Node overrides (url, prompt, bili->denoise, etc.) are applied correctly.
3. The output nodes produce image filenames.
"""

from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.executors.comfyui import ComfyUIExecutorAdapter
from app.services.executors.base import ExecutionContext


TEST_IMAGE_URL = "http://httpbin.org/image/png"
BASE_URL_117 = "http://117.50.216.233:8079"
BASE_URL_158 = "http://117.50.80.158:8079"


def _make_context(workflow_key: str, graph: dict, base_url: str):
    workflow = SimpleNamespace(
        definition={"graph": graph, "workflow_key": workflow_key},
        extra_metadata={"workflow_key": workflow_key},
    )
    executor = SimpleNamespace(base_url=base_url, config={})
    task = SimpleNamespace(user_id="tester")
    return ExecutionContext(task=task, workflow=workflow, executor=executor, payload={})


def _load_graph(workflow_key: str) -> dict:
    path = Path(__file__).resolve().parent.parent / "app" / "workflows" / "comfyui" / f"{workflow_key}.json"
    data = json.loads(path.read_text())
    return data.get("graph", data)


def _submit_and_poll(base_url: str, graph: dict, output_node_ids: list[str], timeout: int = 180) -> dict:
    prompt_id = f"e2e-{secrets.token_hex(8)}"
    resp = httpx.post(f"{base_url}/prompt", json={"prompt": graph, "prompt_id": prompt_id}, timeout=30)
    resp.raise_for_status()
    print(f"  Submitted {prompt_id} to {base_url}")

    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            r = httpx.get(f"{base_url}/history/{prompt_id}", timeout=15)
            if r.status_code == 404:
                time.sleep(2)
                continue
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError:
            time.sleep(2)
            continue

        entry = data.get(prompt_id) if isinstance(data, dict) else None
        if not isinstance(entry, dict):
            time.sleep(2)
            continue

        status = entry.get("status")
        outputs = entry.get("outputs") or {}
        images: list[dict] = []
        if isinstance(outputs, dict):
            for node_id, info in outputs.items():
                if not isinstance(info, dict):
                    continue
                if output_node_ids and str(node_id) not in output_node_ids:
                    continue
                imgs = info.get("images")
                if isinstance(imgs, list):
                    images.extend(imgs)

        if status and status.get("status_str") == "error":
            return {"success": False, "error": entry}

        if images:
            return {"success": True, "images": images, "entry": entry}

        time.sleep(3)

    return {"success": False, "error": "TIMEOUT"}


def test_beijing_koutu():
    print("\n[1/4] Testing beijing_koutu (background remove)")
    graph = _load_graph("beijing_koutu")
    context = _make_context("beijing_koutu", graph, BASE_URL_117)
    adapter = ComfyUIExecutorAdapter()
    overrides, err = adapter._build_background_remove_inputs(
        {"image_url": TEST_IMAGE_URL}, context, context.workflow.definition
    )
    assert err is None, err
    _apply_overrides(graph, overrides)
    result = _submit_and_poll(BASE_URL_117, graph, ["4"], timeout=60)
    assert result["success"], f"Failed: {result}"
    print(f"  OK -> {result['images']}")


def test_toubu_kouxiang():
    print("\n[2/4] Testing toubu_kouxiang (head extract)")
    graph = _load_graph("toubu_kouxiang")
    context = _make_context("toubu_kouxiang", graph, BASE_URL_158)
    adapter = ComfyUIExecutorAdapter()
    overrides, err = adapter._build_head_extract_inputs(
        {"image_url": TEST_IMAGE_URL}, context, context.workflow.definition
    )
    assert err is None, err
    _apply_overrides(graph, overrides)
    result = _submit_and_poll(BASE_URL_158, graph, ["140"], timeout=60)
    assert result["success"], f"Failed: {result}"
    print(f"  OK -> {result['images']}")


def test_flux2_9b_liebian_sifang():
    print("\n[3/4] Testing flux2_9b_liebian_sifang")
    graph = _load_graph("flux2_9b_liebian_sifang")
    context = _make_context("flux2_9b_liebian_sifang", graph, BASE_URL_158)
    adapter = ComfyUIExecutorAdapter()
    overrides, err = adapter._build_flux2_9b_liebian_sifang_inputs(
        {"image_url": TEST_IMAGE_URL, "prompt": "a beautiful pattern"},
        context,
        context.workflow.definition,
    )
    assert err is None, err
    _apply_overrides(graph, overrides)
    result = _submit_and_poll(BASE_URL_158, graph, ["111"], timeout=300)
    assert result["success"], f"Failed: {result}"
    print(f"  OK -> {result['images']}")


def test_qwen2512_print_shape_text_enhance():
    print("\n[4/4] Testing qwen2512_print_shape_text_enhance")
    graph = _load_graph("qwen2512_print_shape_text_enhance")
    context = _make_context("qwen2512_print_shape_text_enhance", graph, BASE_URL_158)
    adapter = ComfyUIExecutorAdapter()
    overrides, err = adapter._build_qwen2512_print_shape_text_enhance_inputs(
        {"image_url": TEST_IMAGE_URL, "prompt": "enhanced text print", "bili": 50, "seed": 424242},
        context,
        context.workflow.definition,
    )
    assert err is None, err
    _apply_overrides(graph, overrides)
    result = _submit_and_poll(BASE_URL_158, graph, ["29"], timeout=300)
    assert result["success"], f"Failed: {result}"
    print(f"  OK -> {result['images']}")


def _apply_overrides(graph: dict, overrides: dict[str, dict] | None) -> None:
    if not overrides:
        return
    for node_id, values in overrides.items():
        node = graph.setdefault(node_id, {})
        inputs = node.setdefault("inputs", {})
        inputs.update(values)


if __name__ == "__main__":
    test_beijing_koutu()
    test_toubu_kouxiang()
    test_flux2_9b_liebian_sifang()
    test_qwen2512_print_shape_text_enhance()
    print("\nAll e2e tests passed!")
