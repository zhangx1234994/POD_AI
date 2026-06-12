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
            "材质槽较多，建议先从 front 验证方向和比例，再逐步扩展多槽贴图模板。",
        ],
    },
}

CAMERA_PRESETS: dict[str, dict[str, Any]] = {
    "orbit_360": {
        "label": "360 环绕",
        "description": "围绕商品一圈，适合商品展示短视频。",
        "shootingGoal": "完整展示商品外形、轮廓和贴图连续性。",
        "lens": "50mm product lens",
        "motionTemplate": "turntable_orbit",
        "keyframes": [
            {"time": 0, "camera": "front three-quarter", "target": "product center"},
            {"time": 0.5, "camera": "side orbit", "target": "product center"},
            {"time": 1, "camera": "back-to-front return", "target": "product center"},
        ],
    },
    "slow_push_in": {
        "label": "慢速推进",
        "description": "从全景推进到主体细节，适合主视觉动效。",
        "shootingGoal": "先建立电商主视觉，再靠近商品主贴图区。",
        "lens": "55mm product lens",
        "motionTemplate": "dolly_push_in",
        "keyframes": [
            {"time": 0, "camera": "wide product hero", "target": "full product"},
            {"time": 1, "camera": "medium close product center", "target": "active texture slot"},
        ],
    },
    "detail_sweep": {
        "label": "细节扫过",
        "description": "沿材质和贴图区域轻扫，适合材质/印花展示。",
        "shootingGoal": "展示材质、印花清晰度和贴图边界。",
        "lens": "70mm macro lens",
        "motionTemplate": "macro_lateral_sweep",
        "keyframes": [
            {"time": 0, "camera": "macro detail left", "target": "active texture slot"},
            {"time": 1, "camera": "macro detail right", "target": "active texture slot"},
        ],
    },
    "hero_turntable": {
        "label": "主视觉转台",
        "description": "轻微俯视的转台动效，适合平台商品页首屏。",
        "shootingGoal": "在不夸张运动的前提下形成商品高级感。",
        "lens": "60mm product lens",
        "motionTemplate": "slow_turntable_hero",
        "keyframes": [
            {"time": 0, "camera": "front hero", "target": "product center"},
            {"time": 0.45, "camera": "front-right three-quarter", "target": "product center"},
            {"time": 1, "camera": "front-left three-quarter", "target": "product center"},
        ],
    },
    "top_reveal": {
        "label": "俯拍揭示",
        "description": "从轻俯拍过渡到正面主体，适合杯子、包袋等展示结构。",
        "shootingGoal": "同时交代顶部结构和正面贴图区。",
        "lens": "45mm product lens",
        "motionTemplate": "top_to_front_reveal",
        "keyframes": [
            {"time": 0, "camera": "high three-quarter", "target": "top opening and product center"},
            {"time": 1, "camera": "front hero", "target": "active texture slot"},
        ],
    },
    "social_arc": {
        "label": "社媒弧线",
        "description": "节奏更快的弧形推拉，适合短视频封面和社媒动效。",
        "shootingGoal": "快速建立商品吸引力，但保持商品形变为零。",
        "lens": "40mm commercial lens",
        "motionTemplate": "social_arc_push",
        "keyframes": [
            {"time": 0, "camera": "wide front-left", "target": "full product"},
            {"time": 0.55, "camera": "medium front", "target": "active texture slot"},
            {"time": 1, "camera": "wide front-right settle", "target": "full product"},
        ],
    },
}

SCENE_PRESETS: dict[str, dict[str, Any]] = {
    "clean_studio": {
        "label": "干净摄影棚",
        "lighting": "softbox key light, soft fill, contact shadow",
        "background": "matte light gray seamless backdrop",
        "sceneModel": "studio_seamless_sweep",
        "placement": {
            "surface": "matte seamless floor",
            "anchor": "center",
            "scalePolicy": "fit product to 70% frame height",
            "shadow": "soft contact shadow",
            "safeZones": ["leave top/bottom breathing room", "no props crossing product silhouette"],
        },
    },
    "marketplace_white": {
        "label": "电商白底",
        "lighting": "even product catalog lighting",
        "background": "white background with subtle floor shadow",
        "sceneModel": "marketplace_white_sweep",
        "placement": {
            "surface": "white studio floor",
            "anchor": "center",
            "scalePolicy": "fit product to 78% frame height",
            "shadow": "catalog contact shadow",
            "safeZones": ["no decorative props", "white background only"],
        },
    },
    "premium_dark": {
        "label": "深色质感棚",
        "lighting": "controlled rim light and soft top light",
        "background": "deep charcoal studio sweep",
        "sceneModel": "dark_premium_sweep",
        "placement": {
            "surface": "charcoal seamless floor",
            "anchor": "center",
            "scalePolicy": "fit product to 68% frame height",
            "shadow": "controlled soft shadow",
            "safeZones": ["preserve edge highlight", "no reflective logo props"],
        },
    },
    "desktop_lifestyle": {
        "label": "桌面生活场景",
        "lighting": "soft window key light with warm fill",
        "background": "minimal desk surface with blurred lifestyle depth",
        "sceneModel": "desktop_lifestyle_table",
        "placement": {
            "surface": "wood or matte desk",
            "anchor": "front center on tabletop",
            "scalePolicy": "realistic product scale on desk",
            "shadow": "natural tabletop shadow",
            "safeZones": ["props stay secondary", "do not occlude the texture slot"],
        },
    },
    "gift_table": {
        "label": "礼品桌面场景",
        "lighting": "soft celebratory key light without harsh color cast",
        "background": "clean gift table with subtle ribbon or box props",
        "sceneModel": "gift_table_minimal",
        "placement": {
            "surface": "neutral gift table",
            "anchor": "center with props behind",
            "scalePolicy": "product remains dominant",
            "shadow": "soft tabletop shadow",
            "safeZones": ["props cannot cover product", "no text or brand marks"],
        },
    },
    "retail_shelf": {
        "label": "货架陈列场景",
        "lighting": "bright retail display lighting",
        "background": "simple shelf depth for commerce display",
        "sceneModel": "retail_display_shelf",
        "placement": {
            "surface": "retail shelf",
            "anchor": "front row center",
            "scalePolicy": "commercial display scale",
            "shadow": "small shelf contact shadow",
            "safeZones": ["avoid fake packaging claims", "no readable shelf labels"],
        },
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

        valid_slots = set(model.get("materialSlots") or [])
        texture_slots: list[dict[str, str]] = []
        raw_texture_slots = getattr(payload, "textureSlots", None)
        if isinstance(raw_texture_slots, list):
            for item in raw_texture_slots:
                if not isinstance(item, dict):
                    continue
                slot = _clean_text(item.get("materialSlot") or item.get("material_slot"))
                image_url = _clean_text(item.get("imageUrl") or item.get("image_url") or item.get("url"))
                if not image_url:
                    continue
                if slot and slot not in valid_slots:
                    raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MATERIAL_SLOT_INVALID")
                texture_slots.append(
                    {
                        "materialSlot": slot or material_slot,
                        "imageUrl": image_url,
                        "label": _clean_text(item.get("label")) or slot or material_slot,
                    }
                )

        texture_urls = _normalize_list(getattr(payload, "textureImageUrls", None))
        texture_url = _clean_text(getattr(payload, "textureImageUrl", None))
        if texture_url and texture_url not in texture_urls:
            texture_urls.insert(0, texture_url)
        for item in texture_slots:
            image_url = _clean_text(item.get("imageUrl"))
            if image_url and image_url not in texture_urls:
                texture_urls.append(image_url)
        texture_urls = texture_urls[:6]
        if texture_urls and not texture_slots:
            texture_slots.append(
                {
                    "materialSlot": material_slot,
                    "imageUrl": texture_urls[0],
                    "label": _clean_text(model.get("recommendedMaterialSlot")) or material_slot,
                }
            )
        duration_seconds = int(getattr(payload, "durationSeconds", None) or 6)
        aspect_ratio = _clean_text(getattr(payload, "aspectRatio", None)) or "16:9"
        render_note = _clean_text(getattr(payload, "extraPrompt", None))

        warnings: list[dict[str, str]] = []
        if not texture_urls and not texture_slots:
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
                "mode": "slot_texture_mapping" if texture_slots else "single_slot_texture",
                "activeMaterialSlot": material_slot,
                "materialSlot": material_slot,
                "textureImageUrls": texture_urls,
                "textureSlots": texture_slots,
                "textureSlotCount": len(texture_slots),
                "preserveUv": True,
                "previewBoundary": "client_threejs_wysiwyg_preview_then_server_render_worker",
            },
            "scene": {
                "key": scene_preset_key,
                "preset": scene_preset_key,
                **scene_preset,
            },
            "camera": {
                "key": camera_preset_key,
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
            "renderNote": render_note or None,
        }
        readiness_score = 92 if (texture_urls or texture_slots) and model.get("hasUv") else 72
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
                "textureProvided": bool(texture_urls or texture_slots),
                "textureSlotCount": len(texture_slots),
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
