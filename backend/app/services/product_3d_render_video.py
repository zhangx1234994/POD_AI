"""3D model render-video planning for POD market assets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").strip().split())


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    if not text:
        return []
    for sep in ("；", ";", "，", ",", "\n", "|"):
        text = text.replace(sep, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "cup_1660": {
        "modelKey": "cup_1660",
        "displayName": "1660 杯子",
        "sourceArchive": "3D-1660.zip",
        "preferredFile": "1660.glb",
        "productType": "cup",
        "meshCount": 1,
        "materialCount": 7,
        "textureCount": 2,
        "imageCount": 1,
        "hasUv": True,
        "hasAnimation": False,
        "recommendedMaterialSlot": "front",
        "materialSlots": ["front", "mouth", "cover", "bottom", "handshank", "else", "else1"],
        "notes": [
            "GLB/GLTF 均存在，首版渲染优先使用 GLB。",
            "全部 primitive 有 TEXCOORD_0，可进入贴图验证。",
            "没有内置相机和动画，需要由渲染服务注入相机和轨道。",
        ],
    },
    "backpack_2551": {
        "modelKey": "backpack_2551",
        "displayName": "2551 笔记本电脑背包",
        "sourceArchive": "3D-2551.zip",
        "preferredFile": "2551.glb",
        "productType": "backpack",
        "meshCount": 1,
        "materialCount": 19,
        "textureCount": 19,
        "imageCount": 10,
        "hasUv": True,
        "hasAnimation": False,
        "recommendedMaterialSlot": "front",
        "materialSlots": [
            "front",
            "bottom",
            "back",
            "top",
            "left",
            "right",
            "sideleft",
            "sideright",
            "qitaDZ",
            "qitaBD",
            "zipper",
            "zipper02",
            "zipperB",
            "qitaSL",
            "stitch",
            "qitaWGBB",
            "qitaWG",
            "qitaWG001",
            "inside",
        ],
        "notes": [
            "GLB/GLTF 均存在，首版渲染优先使用 GLB。",
            "全部 primitive 有 TEXCOORD_0，可进入多材质贴图验证。",
            "材质槽较多，首版默认只贴 front，后续再开放多面贴图模板。",
        ],
    },
}

CAMERA_PRESETS: dict[str, dict[str, Any]] = {
    "orbit_360": {
        "label": "360 环绕",
        "description": "围绕商品一圈，适合商品展示短视频。",
        "keyframes": [
            {"time": 0, "camera": "front three-quarter"},
            {"time": 0.5, "camera": "side orbit"},
            {"time": 1, "camera": "back-to-front return"},
        ],
    },
    "slow_push_in": {
        "label": "慢速推进",
        "description": "从全景推进到主体细节，适合主视觉动效。",
        "keyframes": [
            {"time": 0, "camera": "wide product hero"},
            {"time": 1, "camera": "medium close product center"},
        ],
    },
    "detail_sweep": {
        "label": "细节扫过",
        "description": "沿材质和贴图区域轻扫，适合材质/印花展示。",
        "keyframes": [
            {"time": 0, "camera": "macro detail left"},
            {"time": 1, "camera": "macro detail right"},
        ],
    },
}

SCENE_PRESETS: dict[str, dict[str, Any]] = {
    "clean_studio": {
        "label": "干净摄影棚",
        "lighting": "softbox key light, soft fill, contact shadow",
        "background": "matte light gray seamless backdrop",
    },
    "marketplace_white": {
        "label": "电商白底",
        "lighting": "even product catalog lighting",
        "background": "white background with subtle floor shadow",
    },
    "premium_dark": {
        "label": "深色质感棚",
        "lighting": "controlled rim light and soft top light",
        "background": "deep charcoal studio sweep",
    },
}


class Product3DRenderVideoService:
    """Returns a truthful render plan before the real render worker is connected."""

    def preview(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        request_id = _clean_text(getattr(payload, "requestId", None)) or f"p3d_{uuid4().hex[:12]}"
        model_key = _clean_text(getattr(payload, "modelKey", None)) or "cup_1660"
        model = MODEL_REGISTRY.get(model_key)
        if not model:
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MODEL_INVALID")

        output_mode = _clean_text(getattr(payload, "outputMode", None)) or "plan_only"
        if output_mode != "plan_only":
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_EXECUTION_NOT_READY")

        material_slot = _clean_text(getattr(payload, "materialSlot", None)) or _clean_text(model.get("recommendedMaterialSlot"))
        if material_slot not in set(model.get("materialSlots") or []):
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID")

        camera_preset_key = _clean_text(getattr(payload, "cameraPreset", None)) or "orbit_360"
        camera_preset = CAMERA_PRESETS.get(camera_preset_key)
        if not camera_preset:
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_CAMERA_PRESET_INVALID")

        scene_preset_key = _clean_text(getattr(payload, "scenePreset", None)) or "clean_studio"
        scene_preset = SCENE_PRESETS.get(scene_preset_key)
        if not scene_preset:
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_SCENE_PRESET_INVALID")

        texture_urls = _normalize_list(getattr(payload, "textureImageUrls", None))
        texture_url = _clean_text(getattr(payload, "textureImageUrl", None))
        if texture_url and texture_url not in texture_urls:
            texture_urls.insert(0, texture_url)
        texture_urls = texture_urls[:6]
        duration_seconds = int(getattr(payload, "durationSeconds", None) or 6)
        aspect_ratio = _clean_text(getattr(payload, "aspectRatio", None)) or "16:9"
        extra_prompt = _clean_text(getattr(payload, "extraPrompt", None))

        warnings: list[dict[str, str]] = []
        if not texture_urls:
            warnings.append(
                {
                    "code": "PRODUCT_3D_RENDER_VIDEO_TEXTURE_MISSING",
                    "message": "没有提供贴图 URL；当前只能验证模型和镜头方案，不能判断最终商品效果。",
                }
            )
        if not model.get("hasUv"):
            warnings.append(
                {
                    "code": "PRODUCT_3D_RENDER_VIDEO_UV_MISSING",
                    "message": "模型缺少 UV，贴图前需要重建 UV。",
                }
            )

        render_plan = {
            "pipeline": "threejs_or_blender_render_worker",
            "executionStatus": "preview_only",
            "outputMode": output_mode,
            "modelFile": model.get("preferredFile"),
            "textureApplication": {
                "mode": "single_slot_texture" if len(texture_urls) <= 1 else "multi_texture_planned",
                "materialSlot": material_slot,
                "textureImageUrls": texture_urls,
                "preserveUv": True,
            },
            "scene": {
                "preset": scene_preset_key,
                **scene_preset,
            },
            "camera": {
                "preset": camera_preset_key,
                **camera_preset,
            },
            "durationSeconds": duration_seconds,
            "aspectRatio": aspect_ratio,
            "deliverables": [
                "rendered_video_mp4",
                "cover_frame_png",
                "render_manifest_json",
            ],
            "steps": [
                "Load GLB from managed model registry.",
                "Apply texture to the selected material slot and validate UV coverage.",
                "Create studio scene, lights, camera path, and turntable controls.",
                "Render or capture frames to MP4, then upload final assets to PODI OSS.",
            ],
            "extraPrompt": extra_prompt or None,
        }
        readiness_score = 92 if texture_urls and model.get("hasUv") else 72
        return {
            "requestId": request_id,
            "businessKey": "product_3d_render_video",
            "version": "product-3d-render-video-plan-v1",
            "status": "previewed",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "assetReadiness": {
                "score": readiness_score,
                "modelReady": True,
                "uvReady": bool(model.get("hasUv")),
                "textureProvided": bool(texture_urls),
                "renderWorkerReady": False,
                "warnings": warnings,
            },
            "renderPlan": render_plan,
            "review": {
                "score": readiness_score,
                "issues": warnings,
                "nextActions": [
                    "把 3D 模型归档到受控模型目录，并记录 modelKey 到能力配置。",
                    "用 Three.js 先做交互预览，验证贴图方向、比例和材质槽。",
                    "确认渲染质量后，再接异步渲染 worker 和 OSS 回填。",
                ],
            },
            "execution": {
                "videoGenerated": False,
                "costActions": [],
                "note": "This endpoint is a contract/plan preview only. It does not call KIE, Vidu, or any paid video model.",
            },
            "audit": {
                "userId": user_id,
                "source": _clean_text(getattr(payload, "source", None)) or "eval",
                "traceId": _clean_text(getattr(payload, "traceId", None)) or None,
            },
        }


product_3d_render_video_service = Product3DRenderVideoService()
