from __future__ import annotations

from datetime import datetime

from app.models.integration import Executor
from app.schemas.admin_integrations import ExecutorRead


def test_executor_exposes_normalized_tags_from_config_string() -> None:
    now = datetime.utcnow()
    executor = Executor(
        id="executor_upscale",
        name="高清放大节点",
        type="comfyui",
        base_url="http://example.test:8079",
        status="active",
        weight=1,
        max_concurrency=1,
        config={"tags": "upscale, high-mem; comfyui-general"},
        created_at=now,
        updated_at=now,
    )

    assert executor.tags == ["upscale", "high-mem", "comfyui-general"]
    payload = ExecutorRead.model_validate(executor).model_dump()
    assert payload["tags"] == ["upscale", "high-mem", "comfyui-general"]
