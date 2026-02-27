from pathlib import Path
import threading

from agent_core.models import DesktopConfig
from agent_core.runtime import AgentRuntime
from agent_core.state_store import StateStore
from agent_core.task_engine import TaskEngine


class DummyCenterClient:
    def list_desktop_releases(self, agent_token, *, channel, os_type, arch, status, limit):
        return [
            {
                "id": 2,
                "version": "0.2.0",
                "status": "active",
                "publishedAt": "2026-02-27T10:00:00Z",
                "downloadUrl": "https://example.com/agent-0.2.0.exe",
            },
            {
                "id": 1,
                "version": "0.1.0",
                "status": "active",
                "publishedAt": "2026-02-20T10:00:00Z",
                "downloadUrl": "https://example.com/agent-0.1.0.exe",
            },
        ]


def _build_runtime(tmp_path: Path) -> AgentRuntime:
    cfg = DesktopConfig(
        center_url="http://127.0.0.1:8099",
        agent_id="agent-test",
        agent_token="token-test",
        comfyui_path=str(tmp_path),
    )
    store = StateStore(tmp_path / "state.db")
    client = DummyCenterClient()
    engine = TaskEngine(config=cfg, store=store, client=client)  # type: ignore[arg-type]
    return AgentRuntime(
        config=cfg,
        store=store,
        client=client,  # type: ignore[arg-type]
        engine=engine,
        _heartbeat_stop=threading.Event(),
    )


def test_compare_versions() -> None:
    assert AgentRuntime._compare_versions("0.2.0", "0.1.9") > 0
    assert AgentRuntime._compare_versions("0.1.0", "0.1.0") == 0
    assert AgentRuntime._compare_versions("0.1.0", "0.2.0") < 0


def test_check_desktop_update_records_state(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    result = runtime.check_desktop_update(force=True)
    assert result["status"] in {"update_available", "up_to_date"}
    state = runtime.store.get_update_state()
    assert state is not None
    assert state["status"] in {"update_available", "up_to_date"}
    assert state["current_version"]


def test_apply_desktop_update_not_supported_non_windows(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    result = runtime.apply_desktop_update(force=True)
    assert result["status"] == "apply_not_supported"


def test_apply_desktop_update_windows_flow(tmp_path: Path, monkeypatch) -> None:
    runtime = _build_runtime(tmp_path)
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    fake_installer = tmp_path / "agent-update.exe"
    fake_installer.write_bytes(b"dummy")
    monkeypatch.setattr(runtime, "_download_update_installer", lambda url, ver: fake_installer)
    monkeypatch.setattr(runtime, "_sha256", lambda _path: "abc123")
    monkeypatch.setattr(
        runtime,
        "_launch_installer",
        lambda _path: {"script_path": "apply.ps1", "command": ["powershell"]},
    )

    # patch release checksum to match mocked file hash
    runtime.client.list_desktop_releases = lambda *args, **kwargs: [  # type: ignore[method-assign]
        {
            "id": 2,
            "version": "9.9.9",
            "status": "active",
            "publishedAt": "2026-02-27T10:00:00Z",
            "downloadUrl": "https://example.com/agent.exe",
            "sha256": "abc123",
        }
    ]

    result = runtime.apply_desktop_update(force=True)
    assert result["status"] == "apply_started"


def test_check_desktop_update_marks_applied_when_target_reached(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    runtime.store.set_update_state(
        current_version="0.1.0",
        target_version="0.1.0",
        status="apply_started",
        payload={"release": {"version": "0.1.0"}},
    )
    runtime.client.list_desktop_releases = lambda *args, **kwargs: [  # type: ignore[method-assign]
        {
            "id": 1,
            "version": "0.1.0",
            "status": "active",
            "publishedAt": "2026-02-27T10:00:00Z",
            "downloadUrl": "https://example.com/agent.exe",
            "sha256": "abc123",
        }
    ]
    result = runtime.check_desktop_update(force=True)
    assert result["status"] == "applied"


def test_heartbeat_payload_contains_update_summary(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    runtime.store.set_update_state(
        current_version="0.1.0",
        target_version="0.2.0",
        status="update_available",
        payload={"release": {"version": "0.2.0"}},
    )
    payload = runtime._build_heartbeat_payload()
    assert payload["runtime"]["desktopVersion"]
    assert payload["updateState"]["status"] == "update_available"
