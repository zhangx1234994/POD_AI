from pathlib import Path

import pytest

from agent_core.models import DesktopConfig
from agent_core.state_store import StateStore
from agent_core.task_engine import TaskEngine, TaskError


class DummyClient:
    def report_event(self, task_id, token, payload):
        return {"ok": True}

    def verify_task_token(self, payload):
        return {"ok": True}

    def fetch_manifest(self, manifest_url, token):
        return {"version": "v1", "content": {"models": [], "plugins": [], "workflows": []}}

    def report_complete(self, task_id, token, payload):
        return {"ok": True}

    def report_failed(self, task_id, token, payload):
        return {"ok": True}


def test_normalize_actions_dict(tmp_path: Path) -> None:
    cfg = DesktopConfig(agent_id="a1", comfyui_path=str(tmp_path))
    engine = TaskEngine(config=cfg, store=StateStore(tmp_path / "state.db"), client=DummyClient())
    merged = engine._normalize_actions({"sync_models": False, "restart": True})
    assert merged["sync_models"] is False
    assert merged["restart"] is True


def test_parse_payload_requires_task_id(tmp_path: Path) -> None:
    cfg = DesktopConfig(agent_id="a1", comfyui_path=str(tmp_path))
    engine = TaskEngine(config=cfg, store=StateStore(tmp_path / "state.db"), client=DummyClient())
    with pytest.raises(TaskError):
        engine.execute({"token": "x", "manifest_url": "http://example.com"})
