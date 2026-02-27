"""FastAPI app for ComfyUI desktop agent."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent_core.runtime import AgentRuntime
from agent_core.models import DesktopConfig


runtime = AgentRuntime.create()


class BootstrapRequest(BaseModel):
    enroll_code: str = Field(alias="enrollCode")
    machine_name: str | None = Field(default=None, alias="machineName")
    host: str | None = None
    role: str | None = None
    base_url: str | None = Field(default=None, alias="baseUrl")
    preferred_agent_id: str | None = Field(default=None, alias="preferredAgentId")
    agent_version: str | None = Field(default=None, alias="agentVersion")
    comfyui_version: str | None = Field(default=None, alias="comfyuiVersion")
    payload: dict[str, Any] | None = None


class ConfigRequest(BaseModel):
    center_url: str = Field(alias="centerUrl")
    install_key: str | None = Field(default=None, alias="installKey")
    auto_bootstrap: bool = Field(default=True, alias="autoBootstrap")
    comfyui_path: str = Field(alias="comfyuiPath")
    comfyui_port: int = Field(default=8079, alias="comfyuiPort")
    agent_port: int = Field(default=18079, alias="agentPort")
    heartbeat_interval_sec: int = Field(default=60, alias="heartbeatIntervalSec")
    auto_update: bool = Field(default=True, alias="autoUpdate")
    log_level: str = Field(default="INFO", alias="logLevel")


app = FastAPI(title="ComfyUI Desktop Agent", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    try:
        runtime.try_auto_bootstrap()
    except Exception:
        # Keep service available even if bootstrap fails; GUI/user can retry manually.
        pass
    runtime.start_heartbeat()


@app.on_event("shutdown")
def _shutdown() -> None:
    runtime.stop_heartbeat()


@app.get("/health")
def health() -> dict[str, Any]:
    status = runtime.get_status()
    return {"status": "ok" if status["health"]["ok"] else "degraded", **status}


@app.get("/status")
def status() -> dict[str, Any]:
    return runtime.get_status()


@app.post("/tasks")
def handle_task(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return runtime.execute_task(payload)
    except Exception as exc:
        message = str(exc)
        if "busy with task" in message.lower():
            raise HTTPException(status_code=409, detail="busy") from exc
        raise HTTPException(status_code=400, detail=message) from exc


@app.post("/bootstrap/exchange")
def bootstrap_exchange(body: BootstrapRequest) -> dict[str, Any]:
    return runtime.bootstrap(body.model_dump(by_alias=True, exclude_none=True))


@app.post("/bootstrap/refresh-keys")
def bootstrap_refresh_keys() -> dict[str, Any]:
    return runtime.refresh_keys()


@app.post("/config")
def update_config(body: ConfigRequest) -> dict[str, Any]:
    old = runtime.config
    cfg = DesktopConfig(
        center_url=body.center_url,
        install_key=(body.install_key or old.install_key or "").strip(),
        auto_bootstrap=bool(body.auto_bootstrap),
        agent_id=old.agent_id,
        agent_token=old.agent_token,
        jwt_keys=old.jwt_keys,
        comfyui_path=body.comfyui_path,
        comfyui_port=body.comfyui_port,
        agent_port=body.agent_port,
        heartbeat_interval_sec=body.heartbeat_interval_sec,
        auto_update=body.auto_update,
        log_level=body.log_level.upper(),
    )
    runtime.update_config(cfg)
    return {"status": "ok"}


@app.get("/tasks/history")
def task_history(limit: int = 200) -> dict[str, Any]:
    return {"items": runtime.store.list_tasks(limit=max(1, min(2000, limit)))}


@app.get("/updates/state")
def update_state() -> dict[str, Any]:
    state = runtime.store.get_update_state()
    if not state:
        return {"status": "unknown"}
    return state


@app.post("/updates/check")
def check_updates() -> dict[str, Any]:
    return runtime.check_desktop_update(force=True)


@app.post("/updates/apply")
def apply_updates() -> dict[str, Any]:
    return runtime.apply_desktop_update(force=True)
