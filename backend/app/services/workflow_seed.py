"""Seed helpers for built-in workflows and action bindings."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
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
                "required_node_keys": ["String", "StringConcatenate", "SaveImage"],
                "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
                "routing_note": "2026-07-13: 连续图主链路固定到 158/5090/117.50.80.158；禁止静默回退 233/4090。",
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
                "required_node_keys": ["String", "SaveImage"],
                "allowed_executor_ids": ["executor_comfyui_seamless_117", "executor_comfyui_pattern_extract_158"],
                "routing_note": "2026-05-16: 233 String/Text/Get Image Size nodes restored and forced 233 run passed; use queue routing across 233/158.",
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_flux2_klein_9b_outpaint_v1",
            action="outpaint",
            name="FLUX2-Klein 扩图 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="flux2_klein_9b_outpaint",
            metadata={
                "workflow_key": "flux2_klein_9b_outpaint",
                "description": "ComfyUI workflow for FLUX2-Klein 9b outpainting. 2026-05-25 updated to the ImageScaleToTotalPixels route from the ComfyUI team.",
                "output_node_ids": ["9"],
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_beijing_koutu_v1",
            action="background_remove",
            name="背景抠图 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="beijing_koutu",
            metadata={
                "workflow_key": "beijing_koutu",
                "description": "ComfyUI workflow for background removal.",
                "output_node_ids": ["4"],
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_toubu_kouxiang_v1",
            action="head_extract",
            name="头部抠像 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="toubu_kouxiang",
            metadata={
                "workflow_key": "toubu_kouxiang",
                "description": "ComfyUI workflow for head extraction / portrait cutout.",
                "output_node_ids": ["140"],
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_flux2_9b_liebian_sifang_v1",
            action="image_fission",
            name="FLUX2裂变+四方 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="flux2_9b_liebian_sifang",
            metadata={
                "workflow_key": "flux2_9b_liebian_sifang",
                "description": "ComfyUI workflow for FLUX2-9b image fission + four-way repeat candidate generation. Production requires deterministic seamless normalization after generation.",
                "output_node_ids": ["111"],
                "required_node_keys": ["String", "SaveImage"],
                "allowed_executor_ids": ["executor_comfyui_pattern_extract_158"],
                "routing_note": "2026-07-11: Flux2 8-step candidate generation is pinned to 158/5090; production requires deterministic seamless normalization after generation.",
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_qwen2512_print_shape_text_enhance_v1",
            action="image_fission",
            name="裂变文字强化 · ComfyUI",
            version="v2",
            type="comfyui",
            status="active",
            workflow_key="qwen2512_print_shape_text_enhance",
            metadata={
                "workflow_key": "qwen2512_print_shape_text_enhance",
                "description": "ComfyUI workflow for prompt-strengthened print-shape fission with text-friendly negative prompt.",
                "output_node_ids": ["29"],
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_qwen2512_text2img_text_allowed_v1",
            action="text_to_image",
            name="文字强化文生图 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="qwen2512_text2img_text_allowed",
            metadata={
                "workflow_key": "qwen2512_text2img_text_allowed",
                "description": "Qwen2512 text-to-image workflow using user-editable prompt from VL.",
                "output_node_ids": ["21"],
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
            action="image_fission",
            name="多元素花纹裂变 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="flux_strong_hq_softstyle_fission",
            metadata={
                "workflow_key": "flux_strong_hq_softstyle_fission",
                "description": "ComfyUI workflow for FLUX strong HQ softstyle pattern fission.",
                "output_node_ids": ["31"],
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
        WorkflowSeed(
            id="workflow_comfyui_yinhua_tiqu_lora_8step_v1",
            action="pattern_extract",
            name="8步加速可换LoRA · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="yinhua_tiqu_lora_8step",
            metadata={
                "workflow_key": "yinhua_tiqu_lora_8step",
                "description": "ComfyUI workflow for 8-step pattern extraction with adjustable effect LoRA.",
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_duotu_ronghe_v1",
            action="multi_image_fusion",
            name="多图融合 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="duotu_ronghe",
            metadata={
                "workflow_key": "duotu_ronghe",
                "description": "ComfyUI workflow for multi-image fusion / compositing.",
                "output_node_ids": ["357"],
            },
        ),
        WorkflowSeed(
            id="workflow_comfyui_e7_flux2_liebian_v1",
            action="image_fission",
            name="E7裂变重绘 · ComfyUI",
            version="v1",
            type="comfyui",
            status="active",
            workflow_key="e7_flux2_liebian",
            metadata={
                "workflow_key": "e7_flux2_liebian",
                "description": "ComfyUI workflow for E7 FLUX2 image fission / redraw.",
                "output_node_ids": ["27"],
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
            enabled=False,
            metadata={"notes": "Disabled 2026-07-13: 233/4090 已移交，不再承接连续图主链路。"},
        ),
        WorkflowBindingSeed(
            id="binding_seamless_comfyui_158_v1",
            action="seamless",
            workflow_id="workflow_comfyui_sifang_lianxu_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=200,
            enabled=True,
            metadata={"notes": "Active binding for ComfyUI seamless pattern workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_pattern_expand_comfyui_v1",
            action="pattern_expand",
            workflow_id="workflow_comfyui_huawen_kuotu_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=100,
            enabled=True,
            metadata={"notes": "Restored 2026-05-16: 233 custom String/Text/Get Image Size dependencies recovered and forced 233 pattern expand run passed."},
        ),
        WorkflowBindingSeed(
            id="binding_pattern_expand_comfyui_158_v1",
            action="pattern_expand",
            workflow_id="workflow_comfyui_huawen_kuotu_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Active binding for ComfyUI 花纹扩图 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_flux2_klein_9b_outpaint_comfyui_158_v1",
            action="outpaint",
            workflow_id="workflow_comfyui_flux2_klein_9b_outpaint_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for FLUX2-Klein 扩图 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_flux2_klein_9b_outpaint_comfyui_117_v1",
            action="outpaint",
            workflow_id="workflow_comfyui_flux2_klein_9b_outpaint_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=95,
            enabled=True,
            metadata={"notes": "Fallback binding for FLUX2-Klein 扩图 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_background_remove_comfyui_117_v1",
            action="background_remove",
            workflow_id="workflow_comfyui_beijing_koutu_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI 背景抠图 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_background_remove_comfyui_158_v1",
            action="background_remove",
            workflow_id="workflow_comfyui_beijing_koutu_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=95,
            enabled=True,
            metadata={"notes": "Fallback binding for ComfyUI 背景抠图 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_head_extract_comfyui_117_v1",
            action="head_extract",
            workflow_id="workflow_comfyui_toubu_kouxiang_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI 头部抠像 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_head_extract_comfyui_158_v1",
            action="head_extract",
            workflow_id="workflow_comfyui_toubu_kouxiang_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=95,
            enabled=True,
            metadata={"notes": "Fallback binding for ComfyUI 头部抠像 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_flux2_9b_liebian_sifang_comfyui_117_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_flux2_9b_liebian_sifang_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=98,
            enabled=False,
            metadata={"notes": "2026-07-11: disabled. 233/4090 is not a reliable fallback execution surface for production-bound continuous-pattern candidates."},
        ),
        WorkflowBindingSeed(
            id="binding_flux2_9b_liebian_sifang_comfyui_158_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_flux2_9b_liebian_sifang_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for FLUX2裂变+四方 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_qwen2512_print_shape_text_enhance_comfyui_117_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_qwen2512_print_shape_text_enhance_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=98,
            enabled=True,
            metadata={"notes": "Secondary binding for 裂变文字强化 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_qwen2512_print_shape_text_enhance_comfyui_158_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_qwen2512_print_shape_text_enhance_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for 裂变文字强化 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_qwen2512_text2img_text_allowed_comfyui_117_v1",
            action="text_to_image",
            workflow_id="workflow_comfyui_qwen2512_text2img_text_allowed_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=98,
            enabled=True,
            metadata={"notes": "Secondary binding for 文字强化文生图 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_qwen2512_text2img_text_allowed_comfyui_158_v1",
            action="text_to_image",
            workflow_id="workflow_comfyui_qwen2512_text2img_text_allowed_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for 文字强化文生图 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_flux_strong_hq_softstyle_fission_comfyui_117_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=95,
            enabled=True,
            metadata={
                "notes": "Secondary binding for 多元素花纹裂变 workflow (117.50.216.233:8079); CLIPVision/IPAdapter assets verified."
            },
        ),
        WorkflowBindingSeed(
            id="binding_flux_strong_hq_softstyle_fission_comfyui_158_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_flux_strong_hq_softstyle_fission_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for 多元素花纹裂变 workflow (117.50.80.158:8079)"},
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
        WorkflowBindingSeed(
            id="binding_pattern_extract_comfyui_117_v2",
            action="pattern_extract",
            workflow_id="workflow_comfyui_yinhua_tiqu_v2",
            executor_id="executor_comfyui_seamless_117",
            priority=95,
            enabled=True,
            metadata={"notes": "Fallback binding for ComfyUI 印花提取 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_pattern_extract_lora_8step_comfyui_v1",
            action="pattern_extract",
            workflow_id="workflow_comfyui_yinhua_tiqu_lora_8step_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=95,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI 8步加速可换LoRA workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_pattern_extract_lora_8step_comfyui_117_v1",
            action="pattern_extract",
            workflow_id="workflow_comfyui_yinhua_tiqu_lora_8step_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=90,
            enabled=True,
            metadata={"notes": "Fallback binding for ComfyUI 8步加速可换LoRA workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_multi_image_fusion_comfyui_v1",
            action="multi_image_fusion",
            workflow_id="workflow_comfyui_duotu_ronghe_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI 多图融合 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_multi_image_fusion_comfyui_117_v1",
            action="multi_image_fusion",
            workflow_id="workflow_comfyui_duotu_ronghe_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=95,
            enabled=True,
            metadata={"notes": "Fallback binding for ComfyUI 多图融合 workflow (117.50.216.233:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_image_fission_comfyui_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_e7_flux2_liebian_v1",
            executor_id="executor_comfyui_pattern_extract_158",
            priority=100,
            enabled=True,
            metadata={"notes": "Default binding for ComfyUI E7 裂变重绘 workflow (117.50.80.158:8079)"},
        ),
        WorkflowBindingSeed(
            id="binding_image_fission_comfyui_117_v1",
            action="image_fission",
            workflow_id="workflow_comfyui_e7_flux2_liebian_v1",
            executor_id="executor_comfyui_seamless_117",
            priority=95,
            enabled=True,
            metadata={"notes": "Fallback binding for ComfyUI E7 裂变重绘 workflow (117.50.216.233:8079)"},
        ),
    ]


DEFAULT_WORKFLOW_SEEDS = _build_workflow_seeds()
DEFAULT_BINDING_SEEDS = _build_binding_seeds()
_WORKFLOW_SEED_LOCK = RLock()


def ensure_default_workflows(session: Session) -> bool:
    """Insert or refresh built-in workflows."""

    with _WORKFLOW_SEED_LOCK:
        return _ensure_default_workflows(session)


def _ensure_default_workflows(session: Session) -> bool:
    changed = False
    for seed in DEFAULT_WORKFLOW_SEEDS:
        definition = {
            "workflow_key": seed.workflow_key,
            "graph": load_comfy_workflow(seed.workflow_key),
        }
        metadata = seed.metadata or {"workflow_key": seed.workflow_key}
        workflow = session.get(Workflow, seed.id)
        if not workflow:
            workflow = Workflow(
                id=seed.id,
                action=seed.action,
                name=seed.name,
                version=seed.version,
                type=seed.type,
                status=seed.status,
                definition=definition,
                extra_metadata=metadata,
            )
            session.add(workflow)
            changed = True
            continue

        next_fields = {
            "action": seed.action,
            "name": seed.name,
            "version": seed.version,
            "type": seed.type,
            "status": seed.status,
            "definition": definition,
            "extra_metadata": metadata,
        }
        for field, next_value in next_fields.items():
            if getattr(workflow, field) != next_value:
                setattr(workflow, field, next_value)
                changed = True
        if changed:
            session.add(workflow)
    if changed:
        session.commit()
    return changed


def ensure_default_bindings(session: Session) -> bool:
    """Insert default bindings (action → workflow → executor)."""

    with _WORKFLOW_SEED_LOCK:
        return _ensure_default_bindings(session)


def _ensure_default_bindings(session: Session) -> bool:
    changed = False
    for seed in DEFAULT_BINDING_SEEDS:
        stmt = select(WorkflowBinding).where(WorkflowBinding.id == seed.id)
        binding = session.execute(stmt).scalar_one_or_none()
        if binding:
            next_fields = {
                "action": seed.action,
                "workflow_id": seed.workflow_id,
                "executor_id": seed.executor_id,
                "priority": seed.priority,
                "enabled": seed.enabled,
                "extra_metadata": seed.metadata,
            }
            for field, next_value in next_fields.items():
                if getattr(binding, field) != next_value:
                    setattr(binding, field, next_value)
                    changed = True
            if changed:
                session.add(binding)
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
        changed = True
    if changed:
        session.commit()
    return changed
