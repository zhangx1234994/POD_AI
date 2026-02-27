from pathlib import Path

from agent_core.state_store import StateStore


def test_state_store_task_upsert(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.upsert_task(task_id="t1", status="running", message="start")
    row = store.get_task("t1")
    assert row is not None
    assert row["status"] == "running"

    store.upsert_task(task_id="t1", status="success", message="done")
    row2 = store.get_task("t1")
    assert row2 is not None
    assert row2["status"] == "success"


def test_state_store_update_state_roundtrip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.set_update_state(
        current_version="0.1.0",
        target_version="0.2.0",
        status="update_available",
        payload={"release": {"version": "0.2.0"}},
    )
    state = store.get_update_state()
    assert state is not None
    assert state["current_version"] == "0.1.0"
    assert state["target_version"] == "0.2.0"
    assert state["status"] == "update_available"
