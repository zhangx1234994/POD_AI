"""Seed helpers for built-in workflows and action bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import Executor, Workflow, WorkflowBinding
from app.workflows import load_comfy_workflow


@dataclass(frozen=True)
class WorkflowSeed:
    id: str
    action: str
    name: str
    version: str
    type: str
    status: str
    workflow_key: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkflowBindingSeed:
    id: str
    action: str
    workflow_id: str
    executor_id: str
    priority: int = 0
    enabled: bool = True
    metadata: dict[str, Any] | None = None


def _build_workflow_seeds() -> list[WorkflowSeed]:
    return [
        WorkflowSeed(
            id="workflow_comfyui_sifang_lianxu_v1",
            action="seamless",
            name="四方连续 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="sifang_lianxu",
            metadata={
                "workflow_key": "sifang_lianxu",
                "description": "ComfyUI JSON workflow stored under app/workflows/comfyui.",
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_huawen_kuotu_v1",
            action="pattern_expand",
            name="花纹扩图 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="huawen_kuotu",
            metadata={
                "workflow_key": "huawen_kuotu",
                "description": "ComfyUI workflow for pattern outpainting / expansion.",
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_yinhua_tiqu_v2",
            action="pattern_extract",
            name="印花提取 · ComfyUI",
            version="v2",
            type="comfyui",
            status="active",
            workflow_key="yinhua_tiqu",
            metadata={
                "workflow_key": "yinhua_tiqu",
                "description": "ComfyUI workflow for pattern extraction / design flattening.",
            },
        ),
    ]


def _build_binding_seeds() -> list[WorkflowBindingSeed]:
    return [
        WorkflowBindingSeed(
            id="binding_seamless_comfyui_v1",
            action="seamless",
            workflow_id="workflow_comfyui_sifang_lianxu_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI seamless pattern workflow"},
        ),
        WorkflowBindingSeed(
            id="binding_pattern_expand_comfyui_v1",
            action="pattern_expand",
            workflow_id="workflow_comfyui_huawen_kuotu_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI 花纹扩图 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_pattern_extract_comfyui_v2",
            action="pattern_extract",
            workflow_id="workflow_comfyui_yinhua_tiqu_v2",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI 印花提取 workflow (117.50.80.158:8079)"},
        ),
    ]


DEFAULT_WORKFLOW_SEEDS = _build_workflow_seeds()
DEFAULT_BINDING_SEEDS = _build_binding_seeds()


def ensure_default_workflows(session: Session) -> bool:
    """Insert built-in workflows if missing."""

    created = False
    for seed in DEFAULT_WORKFLOW_SEEDS:
        if session.get(Workflow, seed.id):
            continue
        definition = {
            "workflow_key": seed.workflow_key,
            "graph": load_comfy_workflow(seed.workflow_key),
        }
        workflow = Workflow(
            id=seed.id,
            action=seed.action,
            name=seed.name,
            version=seed.version,
            type=seed.type,
            status=seed.status,
            definition=definition,
            extra_metadata=seed.metadata or {"workflow_key": seed.workflow_key},
        )
        session.add(workflow)
        created = True
    if created:
        session.commit()
    return created


def ensure_default_bindings(session: Session) -> bool:
    """Insert default bindings (action → workflow → executor)."""

    created = False
    for seed in DEFAULT_BINDING_SEEDS:
        stmt = select(WorkflowBinding).where(WorkflowBinding.id == seed.id)
        if session.execute(stmt).scalar_one_or_none():
            continue
        workflow = session.get(Workflow, seed.workflow_id)
        executor = session.get(Executor, seed.executor_id)
        if not workflow or not executor:
            continue
        binding = WorkflowBinding(
            id=seed.id,
            action=seed.action,
            workflow_id=seed.workflow_id,
            executor_id=seed.executor_id,
            priority=seed.priority,
            enabled=seed.enabled,
            extra_metadata=seed.metadata,
        )
        session.add(binding)
        created = True
    if created:
        session.commit()
    return created
