from __future__ import annotations

from app.models.integration import AbilityTask
from app.services.ability_task_service import AbilityTaskService
from app.services.production_canvas import ProductionCanvasResult, production_canvas_service


def _production_task() -> AbilityTask:
    return AbilityTask(
        id="task-production-canvas",
        ability_id="kie_gpt_image_2_image_to_image",
        ability_provider="kie",
        capability_key="gpt_image_2_image_to_image",
        status="running",
        user_id="user-production-canvas",
        request_payload={
            "metadata": {
                "productionCanvas": {
                    "enabled": True,
                    "targetWidth": 2717,
                    "targetHeight": 1476,
                    "targetDpi": 150,
                    "mode": "cover",
                    "purpose": "agent_design_surface",
                }
            }
        },
    )


def test_production_canvas_replaces_model_candidate_with_preflighted_asset(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_compose(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return ProductionCanvasResult(
            url="https://oss.example.test/production-canvas.png",
            object_key="production/task.png",
            width=2717,
            height=1476,
            dpi=150,
            mode="cover",
            source_width=1672,
            source_height=941,
        )

    monkeypatch.setattr(production_canvas_service, "compose", fake_compose)
    monkeypatch.setattr(
        production_canvas_service,
        "preflight",
        lambda **_: {"passed": True, "width": 2717, "height": 1476, "dpi": 150, "format": "PNG"},
    )

    service = object.__new__(AbilityTaskService)
    result, error = service._apply_production_canvas_if_requested(
        task=_production_task(),
        payload={"images": [{"url": "https://oss.example.test/model-output.png"}]},
    )

    assert error is None
    assert captured["source_url"] == "https://oss.example.test/model-output.png"
    assert captured["target_width"] == 2717
    assert captured["target_height"] == 1476
    assert result["imageUrls"] == ["https://oss.example.test/production-canvas.png"]
    assert result["_productionCanvas"]["status"] == "succeeded"
    assert result["_productionCanvas"]["preflight"]["passed"] is True


def test_production_canvas_is_not_applied_without_explicit_contract() -> None:
    task = _production_task()
    task.request_payload = {"metadata": {}}
    payload = {"images": [{"url": "https://oss.example.test/model-output.png"}]}

    result, error = object.__new__(AbilityTaskService)._apply_production_canvas_if_requested(task=task, payload=payload)

    assert error is None
    assert result == payload


def test_invalid_enabled_production_canvas_is_rejected_instead_of_silently_skipped() -> None:
    task = _production_task()
    task.request_payload = {"metadata": {"productionCanvas": {"enabled": True, "targetWidth": 0}}}

    result, error = object.__new__(AbilityTaskService)._apply_production_canvas_if_requested(
        task=task,
        payload={"images": [{"url": "https://oss.example.test/model-output.png"}]},
    )

    assert error == "PRODUCTION_CANVAS_CONFIG_INVALID"
    assert result["_productionCanvas"]["status"] == "failed"
