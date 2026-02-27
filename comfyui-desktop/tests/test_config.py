from pathlib import Path

from agent_core.config import get_config_path, load_config, save_config
from agent_core.models import DesktopConfig


def test_config_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COMFYUI_DESKTOP_HOME", str(tmp_path))
    cfg = DesktopConfig(center_url="http://127.0.0.1:8099", agent_id="a1", comfyui_path="/opt/comfyui")
    save_config(cfg)
    loaded = load_config()
    assert loaded.center_url == "http://127.0.0.1:8099"
    assert loaded.agent_id == "a1"
    assert get_config_path().exists()
