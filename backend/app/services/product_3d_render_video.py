"""3D model render-video planning for POD market assets."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
import math
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.services.oss import oss_service


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

CAMERA_DISTANCE_PRESETS: dict[str, dict[str, Any]] = {
    "wide": {
        "label": "远景完整商品",
        "description": "优先保证商品完整入画，适合验收贴图、轮廓和平台素材。",
        "frameHeightRatio": 0.56,
        "safeMarginRatio": 0.07,
        "framingPolicy": "fit_product_safe_bounds",
        "cameraZ": 4.35,
        "fov": 35,
    },
    "standard": {
        "label": "标准商品镜头",
        "description": "在完整商品和材质细节之间取平衡，适合通用展示视频。",
        "frameHeightRatio": 0.66,
        "safeMarginRatio": 0.065,
        "framingPolicy": "fit_product_safe_bounds",
        "cameraZ": 3.55,
        "fov": 38,
    },
    "close": {
        "label": "近景细节镜头",
        "description": "靠近材质和贴图区域，适合短镜头细节补充；不建议作为唯一交付镜头。",
        "frameHeightRatio": 0.76,
        "safeMarginRatio": 0.06,
        "framingPolicy": "fit_product_safe_bounds",
        "cameraZ": 2.85,
        "fov": 42,
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

SCENE_ASSET_SOURCES: list[dict[str, Any]] = [
    {
        "provider": "Poly Haven",
        "sourceType": "hdri_and_3d_models",
        "sourceUrl": "https://polyhaven.com",
        "license": "CC0",
        "licenseUrl": "https://polyhaven.com/license",
        "commercialUse": True,
        "currentUse": ["studio HDRI", "soft indoor HDRI", "neutral lighting reference", "shelf/table scene model candidates"],
        "candidateAssets": [
            {
                "assetId": "blocky_photo_studio",
                "displayName": "Blocky Photo Studio",
                "sourceUrl": "https://polyhaven.com/a/blocky_photo_studio",
                "targetScenePresets": ["clean_studio", "marketplace_white"],
                "use": "calibrated studio HDRI for soft commercial product lighting",
            },
            {
                "assetId": "blue_photo_studio",
                "displayName": "Blue Photo Studio",
                "sourceUrl": "https://polyhaven.com/a/blue_photo_studio",
                "targetScenePresets": ["desktop_lifestyle"],
                "use": "indoor studio HDRI with window and lamp cues for lifestyle tabletop depth",
            },
            {
                "assetId": "brown_photostudio_01",
                "displayName": "Brown Photostudio 01",
                "sourceUrl": "https://polyhaven.com/a/brown_photostudio_01",
                "targetScenePresets": ["gift_table", "premium_dark"],
                "use": "warm studio HDRI candidate for gift and premium scenes",
            },
            {
                "assetId": "metal_office_desk",
                "displayName": "Metal Office Desk",
                "sourceUrl": "https://polyhaven.com/a/metal_office_desk",
                "targetScenePresets": ["desktop_lifestyle"],
                "kind": "scene_model",
                "use": "real desk scene model candidate for desktop lifestyle product placement",
            },
            {
                "assetId": "SchoolDesk_01",
                "displayName": "School Desk 01",
                "sourceUrl": "https://polyhaven.com/a/SchoolDesk_01",
                "targetScenePresets": ["desktop_lifestyle", "retail_shelf"],
                "kind": "scene_model",
                "use": "simple desk model candidate for controlled tabletop and front display validation",
            },
            {
                "assetId": "wooden_display_shelves_01",
                "displayName": "Wooden Display Shelves 01",
                "sourceUrl": "https://polyhaven.com/a/wooden_display_shelves_01",
                "targetScenePresets": ["retail_shelf", "desktop_lifestyle"],
                "kind": "scene_model",
                "use": "non-branded cubby shelf model candidate for retail display and lifestyle product placement",
            },
            {
                "assetId": "steel_frame_shelves_01",
                "displayName": "Steel Frame Shelves 01",
                "sourceUrl": "https://polyhaven.com/a/steel_frame_shelves_01",
                "targetScenePresets": ["retail_shelf"],
                "kind": "scene_model",
                "use": "industrial five-tier shelf candidate for non-branded retail display and product scale validation",
            },
            {
                "assetId": "industrial_coffee_table",
                "displayName": "Industrial Coffee Table",
                "sourceUrl": "https://polyhaven.com/a/industrial_coffee_table",
                "targetScenePresets": ["desktop_lifestyle", "gift_table"],
                "kind": "scene_model",
                "use": "tabletop scene candidate for product placement, orbit shots, and contact-shadow validation",
            },
        ],
        "ingestStatus": "candidate_source",
        "ingestGate": [
            "record asset URL, provider, license URL, version, and download date",
            "verify no embedded text, logo, watermark, or brand-specific prop",
            "test scene fusion, safe framing, and render performance before promoting to ready",
        ],
    },
    {
        "provider": "ambientCG",
        "sourceType": "pbr_materials_and_models",
        "sourceUrl": "https://ambientcg.com",
        "license": "CC0 1.0 Universal",
        "licenseUrl": "https://docs.ambientcg.com/license/",
        "commercialUse": True,
        "currentUse": ["wood tabletop material", "paper/cardboard material", "neutral dark material"],
        "candidateAssets": [
            {
                "assetId": "Wood095",
                "displayName": "Wood 095",
                "sourceUrl": "https://ambientcg.com/a/Wood095",
                "targetScenePresets": ["desktop_lifestyle"],
                "use": "minimal light wood tabletop PBR material",
            },
            {
                "assetId": "Paper006",
                "displayName": "Paper 006",
                "sourceUrl": "https://ambientcg.com/a/Paper006",
                "targetScenePresets": ["gift_table", "marketplace_white"],
                "use": "neutral paper surface for gift cards, backdrops, and soft packaging props",
            },
            {
                "assetId": "Cardboard002",
                "displayName": "Cardboard 002",
                "sourceUrl": "https://ambientcg.com/a/Cardboard002",
                "targetScenePresets": ["gift_table"],
                "use": "neutral cardboard gift-box material without readable labels",
            },
            {
                "assetId": "Concrete036",
                "displayName": "Concrete 036",
                "sourceUrl": "https://ambientcg.com/a/Concrete036",
                "targetScenePresets": ["premium_dark", "clean_studio"],
                "use": "controlled dark/gray plinth and sweep surface candidate",
            },
            {
                "assetId": "Fabric079",
                "displayName": "Fabric 079",
                "sourceUrl": "https://ambientcg.com/a/Fabric079",
                "targetScenePresets": ["premium_dark"],
                "use": "dark soft surface candidate for premium non-reflective scenes",
            },
            {
                "assetId": "Metal037",
                "displayName": "Metal 037",
                "sourceUrl": "https://ambientcg.com/a/Metal037",
                "targetScenePresets": ["retail_shelf", "desktop_lifestyle"],
                "use": "neutral steel/fixture PBR material candidate for shelf and desk frame surfaces",
            },
        ],
        "ingestStatus": "candidate_source",
        "ingestGate": [
            "record asset URL, provider, license URL, version, and download date",
            "validate texture scale, roughness, and color do not overpower active product texture slots",
            "test browser preview and server renderer memory before promoting to ready",
        ],
    },
    {
        "provider": "internal_or_cc0",
        "sourceType": "generic_scene_model",
        "sourceUrl": "internal://market-assets",
        "license": "to_be_verified_per_asset",
        "licenseUrl": "",
        "commercialUse": False,
        "currentUse": ["generic retail shelf candidate"],
        "ingestStatus": "needs_license_review",
        "ingestGate": [
            "cannot be exposed to production until commercial use and attribution rules are verified",
            "remove readable shelf labels, fake packaging claims, and competing product props",
            "map final scene asset to scenePreset only after visual and legal review",
        ],
    },
]

SCENE_ASSET_LIBRARY: dict[str, dict[str, Any]] = {
    "clean_studio": {
        "assetId": "podi.scene.procedural.clean_studio.v1",
        "assetType": "procedural_scene_model",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "source": "podi_internal",
        "license": {"type": "internal_procedural", "commercialUse": True},
        "geometry": ["seamless cyclorama sweep", "matte floor plane", "softbox light cards"],
        "materialPolicy": "neutral matte materials only; no readable labels or brand props",
        "highFidelityTarget": "replace with Blender/headless Three.js studio sweep scene without API changes",
        "externalCandidates": [
            {
                "provider": "Poly Haven",
                "kind": "studio HDRI",
                "assetId": "blocky_photo_studio",
                "displayName": "Blocky Photo Studio",
                "url": "https://polyhaven.com/a/blocky_photo_studio",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "replace procedural softbox lighting with calibrated studio environment lighting",
            },
            {
                "provider": "ambientCG",
                "kind": "studio material",
                "assetId": "Concrete036",
                "displayName": "Concrete 036",
                "url": "https://ambientcg.com/a/Concrete036",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "replace MVP matte floor and backdrop materials with PBR surfaces",
            },
        ],
    },
    "marketplace_white": {
        "assetId": "podi.scene.procedural.marketplace_white.v1",
        "assetType": "procedural_scene_model",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "source": "podi_internal",
        "license": {"type": "internal_procedural", "commercialUse": True},
        "geometry": ["white sweep", "catalog floor plane", "subtle contact shadow receiver"],
        "materialPolicy": "white ecommerce surface only; no props, text, logo, price tag, or claim",
        "highFidelityTarget": "replace with controlled catalog-lighting studio asset",
        "externalCandidates": [
            {
                "provider": "Poly Haven",
                "kind": "neutral studio HDRI",
                "assetId": "blocky_photo_studio",
                "displayName": "Blocky Photo Studio",
                "url": "https://polyhaven.com/a/blocky_photo_studio",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "improve catalog lighting while keeping pure marketplace background",
            }
        ],
    },
    "premium_dark": {
        "assetId": "podi.scene.procedural.premium_dark.v1",
        "assetType": "procedural_scene_model",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "source": "podi_internal",
        "license": {"type": "internal_procedural", "commercialUse": True},
        "geometry": ["dark sweep", "low plinth", "rim-light cards"],
        "materialPolicy": "dark neutral materials; reflections cannot introduce fake marks",
        "highFidelityTarget": "replace with premium dark studio scene and calibrated rim lights",
        "externalCandidates": [
            {
                "provider": "ambientCG",
                "kind": "neutral dark material",
                "assetId": "Concrete036",
                "displayName": "Concrete 036",
                "url": "https://ambientcg.com/a/Concrete036",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "replace dark MVP sweep and plinth material with PBR concrete-like surface",
            },
            {
                "provider": "ambientCG",
                "kind": "dark fabric material",
                "assetId": "Fabric079",
                "displayName": "Fabric 079",
                "url": "https://ambientcg.com/a/Fabric079",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "test non-reflective premium tabletop surface without overpowering product texture",
            }
        ],
    },
    "desktop_lifestyle": {
        "assetId": "podi.scene.procedural.desktop_lifestyle.v1",
        "assetType": "procedural_scene_model",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "source": "podi_internal",
        "license": {"type": "internal_procedural", "commercialUse": True},
        "geometry": ["desk plane", "background book block", "soft cube prop"],
        "materialPolicy": "props remain behind product and cannot occlude texture slots",
        "highFidelityTarget": "replace with real tabletop scene model plus CC0 material/HDRI bundle",
        "externalCandidates": [
            {
                "provider": "ambientCG",
                "kind": "wood tabletop material",
                "assetId": "Wood095",
                "displayName": "Wood 095",
                "url": "https://ambientcg.com/a/Wood095",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "replace procedural desk plane with PBR tabletop material",
            },
            {
                "provider": "Poly Haven",
                "kind": "soft indoor HDRI",
                "assetId": "blue_photo_studio",
                "displayName": "Blue Photo Studio",
                "url": "https://polyhaven.com/a/blue_photo_studio",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "improve lifestyle depth and natural window lighting",
            },
            {
                "provider": "Poly Haven",
                "kind": "desk scene model",
                "assetId": "metal_office_desk",
                "displayName": "Metal Office Desk",
                "url": "https://polyhaven.com/a/metal_office_desk",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "replace procedural desk plane with a licensed desk model after scale, occlusion, and performance validation",
            },
            {
                "provider": "Poly Haven",
                "kind": "tabletop scene model",
                "assetId": "industrial_coffee_table",
                "displayName": "Industrial Coffee Table",
                "url": "https://polyhaven.com/a/industrial_coffee_table",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "replace procedural tabletop with a licensed table model after contact-shadow, product scale, occlusion, and browser performance validation",
            },
        ],
    },
    "gift_table": {
        "assetId": "podi.scene.procedural.gift_table.v1",
        "assetType": "procedural_scene_model",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "source": "podi_internal",
        "license": {"type": "internal_procedural", "commercialUse": True},
        "geometry": ["gift table plane", "rear gift box blocks", "warm fill surface"],
        "materialPolicy": "gift props are decorative only; no text, logo, card message, or packaging claim",
        "highFidelityTarget": "replace with curated gift tabletop set and swappable seasonal prop pack",
        "externalCandidates": [
            {
                "provider": "ambientCG",
                "kind": "paper/cardboard material",
                "assetId": "Paper006",
                "displayName": "Paper 006",
                "url": "https://ambientcg.com/a/Paper006",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "replace gift box placeholder blocks with neutral PBR paper/cardboard materials",
            },
            {
                "provider": "ambientCG",
                "kind": "cardboard material",
                "assetId": "Cardboard002",
                "displayName": "Cardboard 002",
                "url": "https://ambientcg.com/a/Cardboard002",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "test neutral gift-box material without text, logos, or packaging claims",
            },
            {
                "provider": "Poly Haven",
                "kind": "warm studio HDRI",
                "assetId": "brown_photostudio_01",
                "displayName": "Brown Photostudio 01",
                "url": "https://polyhaven.com/a/brown_photostudio_01",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "add warm studio lighting to gift tabletop scene",
            },
            {
                "provider": "Poly Haven",
                "kind": "gift tabletop scene model",
                "assetId": "industrial_coffee_table",
                "displayName": "Industrial Coffee Table",
                "url": "https://polyhaven.com/a/industrial_coffee_table",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "test a real tabletop scene for gift-oriented product placement without readable props, cards, labels, or packaging claims",
            },
        ],
    },
    "retail_shelf": {
        "assetId": "podi.scene.procedural.retail_shelf.v1",
        "assetType": "procedural_scene_model",
        "assetStatus": "ready",
        "renderFidelity": "mvp_procedural",
        "source": "podi_internal",
        "license": {"type": "internal_procedural", "commercialUse": True},
        "geometry": ["three shelf rails", "front product placement zone", "shallow depth background"],
        "materialPolicy": "shelves cannot contain readable labels, fake product claims, or competing products",
        "highFidelityTarget": "replace with licensed generic retail display set",
        "externalCandidates": [
            {
                "provider": "Poly Haven",
                "kind": "retail display shelf model",
                "assetId": "wooden_display_shelves_01",
                "displayName": "Wooden Display Shelves 01",
                "url": "https://polyhaven.com/a/wooden_display_shelves_01",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "replace procedural shelf rails with a licensed non-branded cubby display after scale, occlusion, and label-risk validation",
            },
            {
                "provider": "Poly Haven",
                "kind": "industrial shelf scene model",
                "assetId": "steel_frame_shelves_01",
                "displayName": "Steel Frame Shelves 01",
                "url": "https://polyhaven.com/a/steel_frame_shelves_01",
                "license": "CC0",
                "licenseUrl": "https://polyhaven.com/license",
                "status": "candidate",
                "use": "replace procedural shelf rails with a licensed steel shelf model after scale, occlusion, no-label, and close-camera safety validation",
            },
            {
                "provider": "ambientCG",
                "kind": "shelf fixture material",
                "assetId": "Metal037",
                "displayName": "Metal 037",
                "url": "https://ambientcg.com/a/Metal037",
                "license": "CC0",
                "licenseUrl": "https://docs.ambientcg.com/license/",
                "status": "candidate",
                "use": "test neutral metal fixture material without readable labels or fake retail markings",
            },
        ],
    },
}


def _scene_asset_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for raw_source in SCENE_ASSET_SOURCES:
        source = deepcopy(raw_source)
        source["candidateAssets"] = [
            _scene_candidate_asset_package(candidate, provider=source.get("provider"), source=source)
            for candidate in source.get("candidateAssets", [])
            if isinstance(candidate, dict)
        ]
        source["candidateAssetCount"] = len(source["candidateAssets"])
        source["candidateAssetPolicy"] = {
            "status": "staging_only",
            "executionInput": False,
            "promotionPath": ["candidate_source", "staging_asset", "visual_performance_review", "ready_scene_asset"],
            "mustRecord": ["sourceUrl", "licenseUrl", "authorOrProvider", "assetVersion", "downloadDate", "fileHash"],
        }
        sources.append(source)
    return sources


def _scene_candidate_asset_package(
    raw_candidate: dict[str, Any],
    *,
    provider: Any,
    source: dict[str, Any] | None = None,
    scene_preset_key: str | None = None,
) -> dict[str, Any]:
    candidate = deepcopy(raw_candidate)
    provider_name = _clean_text(candidate.get("provider")) or _clean_text(provider) or "unknown"
    license_name = _clean_text(candidate.get("license")) or _clean_text(source.get("license") if source else None)
    license_url = _clean_text(candidate.get("licenseUrl")) or _clean_text(source.get("licenseUrl") if source else None)
    status = _clean_text(candidate.get("status")) or "candidate"
    source_url = _clean_text(candidate.get("sourceUrl")) or _clean_text(candidate.get("url"))
    target_presets = _normalize_list(candidate.get("targetScenePresets"))
    if scene_preset_key and scene_preset_key not in target_presets:
        target_presets.append(scene_preset_key)
    commercial_use = bool((source or {}).get("commercialUse")) or license_name.upper().startswith("CC0")

    candidate.update(
        {
            "provider": provider_name,
            "sourceUrl": source_url,
            "license": license_name or "to_be_verified",
            "licenseUrl": license_url,
            "status": status,
            "ingestStage": "license_review" if status == "needs_license_review" else "staging_candidate",
            "assetVersion": "to_be_recorded",
            "downloadDate": "not_downloaded",
            "fileHash": "to_be_recorded",
            "downloadRequired": True,
            "targetScenePresets": target_presets,
            "workerReadiness": {
                "browserPreview": "not_ingested",
                "serverLightweightRenderer": "not_ingested",
                "highFidelityWorker": "requires_asset_import_test",
            },
            "licenseReview": {
                "required": status == "needs_license_review" or not commercial_use or not license_name.upper().startswith("CC0"),
                "commercialUse": commercial_use,
                "licenseUrl": license_url,
            },
            "requiredValidation": [
                "license_and_commercial_use",
                "no_text_logo_watermark_or_brand_props",
                "scene_fusion_no_occlusion",
                "safe_framing_with_close_camera",
                "browser_preview_performance",
                "server_worker_render_smoke",
            ],
        }
    )
    return candidate


def _scene_asset_package(scene_preset_key: str) -> dict[str, Any]:
    asset = dict(SCENE_ASSET_LIBRARY.get(scene_preset_key) or SCENE_ASSET_LIBRARY["clean_studio"])
    candidates = [
        _scene_candidate_asset_package(item, provider=item.get("provider"), scene_preset_key=scene_preset_key)
        for item in asset.get("externalCandidates") or []
        if isinstance(item, dict)
    ]
    asset["externalCandidates"] = candidates
    asset["requiresLicenseReview"] = any(_clean_text(item.get("status")) == "needs_license_review" for item in candidates)
    asset["currentRendererSupport"] = {
        "browserPreview": True,
        "serverLightweightRenderer": True,
        "highFidelityWorker": "planned",
    }
    asset["ingestPolicy"] = {
        "allowCommercialUseOnly": True,
        "allowedLicenses": ["CC0", "internal_procedural", "owned_asset"],
        "mustRecord": ["sourceUrl", "licenseUrl", "authorOrProvider", "assetVersion", "downloadDate"],
        "doNotBundleLargeVendorAssetsInRepo": True,
    }
    return asset


def _scene_fusion_policy(scene_preset_key: str) -> dict[str, Any]:
    policies: dict[str, dict[str, Any]] = {
        "clean_studio": {
            "landingZone": "center_ellipse_floor_zone",
            "productScale": "56-70% frame height",
            "occlusionPolicy": "no foreground props may cross the product silhouette",
            "propDepth": "lighting cards and backdrop stay behind the product",
            "shadowPolicy": "soft contact shadow under product footprint",
        },
        "marketplace_white": {
            "landingZone": "center_white_catalog_zone",
            "productScale": "66-78% frame height",
            "occlusionPolicy": "no props, labels, price tags, or decorative objects",
            "propDepth": "background and floor only",
            "shadowPolicy": "subtle catalog contact shadow",
        },
        "premium_dark": {
            "landingZone": "center_dark_plinth_zone",
            "productScale": "56-68% frame height",
            "occlusionPolicy": "rim lights cannot hide texture boundaries or product edges",
            "propDepth": "plinth below product, lights behind and above",
            "shadowPolicy": "controlled soft shadow on dark surface",
        },
        "desktop_lifestyle": {
            "landingZone": "front_center_tabletop_zone",
            "productScale": "realistic desk scale with full product visible",
            "occlusionPolicy": "secondary props stay behind the product and cannot cover texture slots",
            "propDepth": "book blocks and soft props stay in the rear depth layer",
            "shadowPolicy": "natural tabletop contact shadow",
        },
        "gift_table": {
            "landingZone": "center_gift_table_zone",
            "productScale": "product remains larger than gift props",
            "occlusionPolicy": "gift boxes and ribbon props cannot cover active texture slots",
            "propDepth": "gift props are rear-row atmosphere only",
            "shadowPolicy": "warm tabletop contact shadow",
        },
        "retail_shelf": {
            "landingZone": "front_row_shelf_center_zone",
            "productScale": "front display scale with full product visible",
            "occlusionPolicy": "shelf rails and posts cannot intersect the product body",
            "propDepth": "shelves and rails stay in background depth layers",
            "shadowPolicy": "small shelf contact shadow",
        },
    }
    policy = dict(policies.get(scene_preset_key) or policies["clean_studio"])
    policy["verification"] = {
        "mode": "scene_fusion_preview",
        "mustShow": ["landingZone", "productFootprint", "propDepth", "occlusionPolicy"],
        "failureIf": ["product cropped", "active texture slot occluded", "fake text/logo appears in scene props"],
    }
    return policy


def _scene_render_elements(scene_preset_key: str) -> list[dict[str, Any]]:
    """Semantic scene model elements used by the lightweight renderer and future high-fidelity workers."""
    elements: dict[str, list[dict[str, Any]]] = {
        "clean_studio": [
            {
                "elementId": "cyclorama_backdrop",
                "type": "seamless_backdrop",
                "depthLayer": "background",
                "zone": "full_frame",
                "occlusion": "never_cross_product_silhouette",
            },
            {
                "elementId": "matte_floor",
                "type": "floor_plane",
                "depthLayer": "surface",
                "zone": "bottom_20_percent",
                "occlusion": "shadow_receiver_only",
            },
        ],
        "marketplace_white": [
            {
                "elementId": "white_catalog_backdrop",
                "type": "catalog_backdrop",
                "depthLayer": "background",
                "zone": "full_frame",
                "occlusion": "no_props_or_text",
            },
            {
                "elementId": "subtle_contact_shadow_receiver",
                "type": "floor_plane",
                "depthLayer": "surface",
                "zone": "bottom_20_percent",
                "occlusion": "shadow_receiver_only",
            },
        ],
        "premium_dark": [
            {
                "elementId": "charcoal_sweep",
                "type": "studio_sweep",
                "depthLayer": "background",
                "zone": "full_frame",
                "occlusion": "rim_light_cannot_hide_edges",
            },
            {
                "elementId": "low_dark_plinth",
                "type": "display_plinth",
                "depthLayer": "surface",
                "zone": "bottom_22_percent",
                "occlusion": "below_product_only",
            },
        ],
        "desktop_lifestyle": [
            {
                "elementId": "wood_tabletop",
                "type": "table_surface",
                "depthLayer": "surface",
                "zone": "bottom_27_percent",
                "occlusion": "shadow_receiver_only",
            },
            {
                "elementId": "rear_book_block",
                "type": "soft_prop",
                "depthLayer": "rear_prop",
                "zone": "left_rear",
                "occlusion": "behind_product_only",
            },
            {
                "elementId": "rear_soft_cube",
                "type": "soft_prop",
                "depthLayer": "rear_prop",
                "zone": "right_rear",
                "occlusion": "behind_product_only",
            },
        ],
        "gift_table": [
            {
                "elementId": "warm_gift_table",
                "type": "table_surface",
                "depthLayer": "surface",
                "zone": "bottom_26_percent",
                "occlusion": "shadow_receiver_only",
            },
            {
                "elementId": "rear_gift_box_left",
                "type": "neutral_gift_prop",
                "depthLayer": "rear_prop",
                "zone": "left_rear",
                "occlusion": "behind_product_no_text",
            },
            {
                "elementId": "rear_gift_box_right",
                "type": "neutral_gift_prop",
                "depthLayer": "rear_prop",
                "zone": "right_rear",
                "occlusion": "behind_product_no_text",
            },
        ],
        "retail_shelf": [
            {
                "elementId": "rear_shelf_rail_top",
                "type": "shelf_rail",
                "depthLayer": "background",
                "zone": "upper_rear",
                "occlusion": "cannot_intersect_product_body",
            },
            {
                "elementId": "rear_shelf_rail_mid",
                "type": "shelf_rail",
                "depthLayer": "background",
                "zone": "middle_rear",
                "occlusion": "cannot_intersect_product_body",
            },
            {
                "elementId": "front_display_shelf",
                "type": "shelf_surface",
                "depthLayer": "surface",
                "zone": "bottom_23_percent",
                "occlusion": "product_stands_in_front",
            },
        ],
    }
    return deepcopy(elements.get(scene_preset_key) or elements["clean_studio"])


def _normalize_motion_path(value: Any) -> list[dict[str, float]]:
    if value is None:
        return [
            {"x": 0.22, "y": 0.66},
            {"x": 0.5, "y": 0.5},
            {"x": 0.78, "y": 0.42},
        ]
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID")

    points: list[dict[str, float]] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID")
        try:
            x = float(item.get("x"))
            y = float(item.get("y"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID") from None
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID")
        points.append({"x": round(x, 4), "y": round(y, 4)})

    if len(points) < 2:
        raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_MOTION_PATH_INVALID")
    return points


def _first_texture_url(payload: Any) -> str:
    raw_texture_slots = getattr(payload, "textureSlots", None)
    if isinstance(raw_texture_slots, list):
        for item in raw_texture_slots:
            if not isinstance(item, dict):
                continue
            image_url = _clean_text(item.get("imageUrl") or item.get("image_url") or item.get("url"))
            if image_url:
                return image_url
    texture_url = _clean_text(getattr(payload, "textureImageUrl", None))
    if texture_url:
        return texture_url
    texture_urls = _normalize_list(getattr(payload, "textureImageUrls", None))
    return texture_urls[0] if texture_urls else ""


def _aspect_dimensions(aspect_ratio: str, *, long_edge: int = 960) -> tuple[int, int]:
    text = _clean_text(aspect_ratio) or "16:9"
    if ":" in text:
        left, right = text.split(":", 1)
    elif "/" in text:
        left, right = text.split("/", 1)
    else:
        left, right = "16", "9"
    try:
        width_ratio = max(1.0, float(left))
        height_ratio = max(1.0, float(right))
    except (TypeError, ValueError):
        width_ratio, height_ratio = 16.0, 9.0
    if width_ratio >= height_ratio:
        width = long_edge
        height = int(round(width * height_ratio / width_ratio))
    else:
        height = long_edge
        width = int(round(height * width_ratio / height_ratio))
    width = max(320, int(round(width / 2) * 2))
    height = max(320, int(round(height / 2) * 2))
    return width, height


def _get_ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg  # type: ignore

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            return str(exe)
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    raise HTTPException(status_code=500, detail="PRODUCT_3D_RENDER_VIDEO_FFMPEG_MISSING")


def _load_texture_image(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        if url.startswith(("http://", "https://")):
            response = httpx.get(url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            data = response.content
        else:
            with open(url, "rb") as handle:  # noqa: PTH123 - explicit local render asset path
                data = handle.read()
        return Image.open(BytesIO(data)).convert("RGB")
    except Exception:
        return None


def _fallback_texture(model_key: str, size: tuple[int, int] = (512, 512)) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, "#dfe7f2" if model_key == "cup_1660" else "#d8dde8")
    draw = ImageDraw.Draw(image)
    palette = ["#315f9d", "#e45858", "#f1c453", "#57a773", "#7d5fff"]
    for index in range(-height, width, 48):
        color = palette[(index // 48) % len(palette)]
        draw.line([(index, 0), (index + height, height)], fill=color, width=18)
    for x in range(42, width, 118):
        for y in range(44, height, 118):
            draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill="#ffffff")
    return image


def _texture_fill(texture: Image.Image | None, size: tuple[int, int], model_key: str) -> Image.Image:
    source = texture or _fallback_texture(model_key)
    return ImageOps.fit(source.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def _motion_position(points: list[dict[str, float]], progress: float) -> tuple[float, float]:
    if len(points) < 2:
        points = _normalize_motion_path(None)
    clamped = min(1.0, max(0.0, float(progress)))
    segment = clamped * (len(points) - 1)
    index = min(len(points) - 2, int(math.floor(segment)))
    local_progress = segment - index
    start = points[index]
    end = points[index + 1]
    x = float(start["x"]) + (float(end["x"]) - float(start["x"])) * local_progress
    y = float(start["y"]) + (float(end["y"]) - float(start["y"])) * local_progress
    return x, y


def _motion_path_bounds(points: list[dict[str, float]]) -> dict[str, float]:
    normalized = points if len(points) >= 2 else _normalize_motion_path(None)
    xs = [float(point["x"]) for point in normalized]
    ys = [float(point["y"]) for point in normalized]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    return {
        "minX": round(min_x, 4),
        "maxX": round(max_x, 4),
        "minY": round(min_y, 4),
        "maxY": round(max_y, 4),
        "spanX": round(max_x - min_x, 4),
        "spanY": round(max_y - min_y, 4),
    }


def _camera_plan_points(value: Any) -> list[dict[str, float]] | None:
    if not isinstance(value, dict):
        return None
    raw_path = value.get("path")
    if isinstance(raw_path, dict) and isinstance(raw_path.get("points"), list):
        return _normalize_motion_path(raw_path.get("points"))
    raw_points = value.get("points")
    if isinstance(raw_points, list):
        return _normalize_motion_path(raw_points)
    return None


def _framing_safety(camera_distance_key: str, motion_path: list[dict[str, float]]) -> dict[str, Any]:
    distance_profile = CAMERA_DISTANCE_PRESETS.get(camera_distance_key) or CAMERA_DISTANCE_PRESETS["wide"]
    safe_margin_ratio = float(distance_profile.get("safeMarginRatio") or 0.065)
    frame_height_ratio = float(distance_profile.get("frameHeightRatio") or 0.66)
    path_bounds = _motion_path_bounds(motion_path)
    final_delivery_recommended = camera_distance_key in {"wide", "standard"}
    caution = (
        "Close distance is kept inside safe bounds, but should be used as a detail clip rather than the only final marketplace video."
        if camera_distance_key == "close"
        else ""
    )
    return {
        "mode": "fit_product_safe_bounds",
        "cameraDistance": camera_distance_key,
        "frameHeightRatio": frame_height_ratio,
        "safeMarginRatio": safe_margin_ratio,
        "normalizedSafeZone": {
            "x": [round(safe_margin_ratio, 4), round(1 - safe_margin_ratio, 4)],
            "y": [round(safe_margin_ratio, 4), round(1 - safe_margin_ratio, 4)],
        },
        "motionPathBounds": path_bounds,
        "appliedMotionScale": {
            "xFrameRatio": 0.22,
            "yFrameRatio": 0.16,
            "reason": "Compatibility metric for the camera path preview; product remains fixed and final framing is clamped inside safe bounds.",
        },
        "cameraPathBounds": path_bounds,
        "clampPolicy": "scale_product_to_frame_then_clamp_rect_inside_safe_bounds",
        "fullProductFitRequired": True,
        "finalDeliveryRecommended": final_delivery_recommended,
        "caution": caution or None,
        "checks": {
            "pathHasAtLeastTwoPoints": len(motion_path) >= 2,
            "pathCoordinatesNormalized": True,
            "closeCameraStillClamped": True,
            "motionCannotOverrideSafeBounds": True,
        },
    }


def _scene_candidate_acceptance(candidate: dict[str, Any]) -> dict[str, Any]:
    readiness = candidate.get("workerReadiness") if isinstance(candidate.get("workerReadiness"), dict) else {}
    license_review = candidate.get("licenseReview") if isinstance(candidate.get("licenseReview"), dict) else {}
    blocking_reasons: list[str] = []
    if license_review.get("required"):
        blocking_reasons.append("license_review_required")
    if _clean_text(candidate.get("downloadDate")) == "not_downloaded":
        blocking_reasons.append("asset_not_downloaded")
    if _clean_text(candidate.get("fileHash")) == "to_be_recorded":
        blocking_reasons.append("file_hash_missing")
    if _clean_text(readiness.get("browserPreview")) != "ready":
        blocking_reasons.append("browser_preview_not_verified")
    if _clean_text(readiness.get("highFidelityWorker")) != "ready":
        blocking_reasons.append("high_fidelity_import_smoke_missing")

    status = "ready_scene_asset" if not blocking_reasons else "candidate_review_required"
    return {
        "assetId": candidate.get("assetId"),
        "displayName": candidate.get("displayName") or candidate.get("assetId"),
        "provider": candidate.get("provider"),
        "kind": candidate.get("kind"),
        "license": candidate.get("license"),
        "licenseUrl": candidate.get("licenseUrl"),
        "sourceUrl": candidate.get("sourceUrl") or candidate.get("url"),
        "ingestStage": candidate.get("ingestStage"),
        "commercialUse": bool(license_review.get("commercialUse")),
        "workerReadiness": readiness,
        "requiredValidation": candidate.get("requiredValidation") or [],
        "status": status,
        "blockingReasons": blocking_reasons,
        "promotionNextAction": (
            "ready for high-fidelity renderer"
            if status == "ready_scene_asset"
            else "download asset, record hash/version, run visual + import smoke checks, then promote"
        ),
    }


def _scene_visual_acceptance(
    scene_preset_key: str,
    *,
    camera_distance_key: str = "wide",
    motion_path: list[dict[str, float]] | None = None,
) -> dict[str, Any]:
    normalized_motion_path = motion_path if motion_path and len(motion_path) >= 2 else _normalize_motion_path(None)
    scene_asset = _scene_asset_package(scene_preset_key)
    fusion = _scene_fusion_policy(scene_preset_key)
    render_elements = _scene_render_elements(scene_preset_key)
    framing_safety = _framing_safety(camera_distance_key, normalized_motion_path)
    candidate_assets = [
        _scene_candidate_acceptance(candidate)
        for candidate in scene_asset.get("externalCandidates") or []
        if isinstance(candidate, dict)
    ]
    current_commercial_use = bool((scene_asset.get("license") or {}).get("commercialUse"))
    current_ready = scene_asset.get("assetStatus") == "ready" and current_commercial_use
    critical_checks = [
        {
            "code": "CURRENT_SCENE_ASSET_READY",
            "label": "当前场景资产可执行",
            "status": "passed" if current_ready else "blocked",
            "evidence": f"{scene_asset.get('assetId')} · {scene_asset.get('renderFidelity')}",
        },
        {
            "code": "COMMERCIAL_LICENSE_OK",
            "label": "授权可商用",
            "status": "passed" if current_commercial_use else "blocked",
            "evidence": _clean_text((scene_asset.get("license") or {}).get("type")) or "unknown",
        },
        {
            "code": "LANDING_ZONE_DEFINED",
            "label": "商品落点明确",
            "status": "passed" if _clean_text(fusion.get("landingZone")) else "blocked",
            "evidence": fusion.get("landingZone"),
        },
        {
            "code": "PRODUCT_OCCLUSION_GUARDED",
            "label": "道具不遮挡商品",
            "status": "passed" if _clean_text(fusion.get("occlusionPolicy")) else "blocked",
            "evidence": fusion.get("occlusionPolicy"),
        },
        {
            "code": "SCENE_DEPTH_LAYERED",
            "label": "场景层级可控",
            "status": "passed" if render_elements else "blocked",
            "evidence": f"{len(render_elements)} render elements",
        },
        {
            "code": "SAFE_FRAMING",
            "label": "镜头完整入画",
            "status": "passed" if framing_safety.get("fullProductFitRequired") else "blocked",
            "evidence": (
                f"{camera_distance_key} · frame {round(float(framing_safety.get('frameHeightRatio') or 0) * 100)}% "
                f"· margin {round(float(framing_safety.get('safeMarginRatio') or 0) * 100)}%"
            ),
        },
        {
            "code": "HIGH_FIDELITY_IMPORT_SMOKE",
            "label": "高保真候选待入库",
            "status": "planned" if candidate_assets else "not_applicable",
            "evidence": f"{len(candidate_assets)} candidates need staging/import smoke before promotion",
        },
    ]
    blocking_reasons = [
        check["code"]
        for check in critical_checks
        if check.get("status") == "blocked"
    ]
    candidate_blocked_count = sum(1 for candidate in candidate_assets if candidate.get("blockingReasons"))
    return {
        "status": "mvp_ready" if current_ready and not blocking_reasons else "blocked",
        "summary": (
            "Current procedural scene is ready for preview and lightweight MP4/OSS output; "
            "high-fidelity external scene candidates remain staging-only until visual/import gates pass."
            if current_ready
            else "Current scene asset is not ready for execution."
        ),
        "currentAsset": {
            "assetId": scene_asset.get("assetId"),
            "assetStatus": scene_asset.get("assetStatus"),
            "renderFidelity": scene_asset.get("renderFidelity"),
            "source": scene_asset.get("source"),
            "license": scene_asset.get("license"),
            "materialPolicy": scene_asset.get("materialPolicy"),
        },
        "sceneFusion": {
            "landingZone": fusion.get("landingZone"),
            "productScale": fusion.get("productScale"),
            "occlusionPolicy": fusion.get("occlusionPolicy"),
            "propDepth": fusion.get("propDepth"),
        },
        "checks": critical_checks,
        "candidateSummary": {
            "total": len(candidate_assets),
            "cc0Count": sum(1 for candidate in candidate_assets if _clean_text(candidate.get("license")).upper() == "CC0"),
            "readyCount": len(candidate_assets) - candidate_blocked_count,
            "blockedCount": candidate_blocked_count,
        },
        "candidateAssets": candidate_assets,
        "blockingReasons": blocking_reasons,
        "promotionPolicy": {
            "currentRendererCanExecute": current_ready,
            "businessInput": "scenePreset only; external asset URLs are not accepted at execution time",
            "highFidelityPromotionGate": [
                "license_and_commercial_use",
                "no_text_logo_watermark_or_brand_props",
                "scene_fusion_no_occlusion",
                "safe_framing_with_close_camera",
                "browser_preview_performance",
                "server_worker_render_smoke",
            ],
        },
    }


def _fit_rect_to_safe_bounds(
    *,
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    product_width: int,
    product_height: int,
    safe_margin_ratio: float,
) -> tuple[int, int, int, int]:
    margin_x = max(12, int(width * safe_margin_ratio))
    margin_y = max(12, int(height * safe_margin_ratio))
    max_product_width = max(80, width - margin_x * 2)
    max_product_height = max(80, height - margin_y * 2)
    if product_width > max_product_width or product_height > max_product_height:
        scale = min(max_product_width / max(1, product_width), max_product_height / max(1, product_height))
        product_width = max(40, int(product_width * scale))
        product_height = max(40, int(product_height * scale))
    left = center_x - product_width // 2
    top = center_y - product_height // 2
    left = min(max(left, margin_x), max(margin_x, width - margin_x - product_width))
    top = min(max(top, margin_y), max(margin_y, height - margin_y - product_height))
    return left, top, left + product_width, top + product_height


def _draw_gradient_background(draw: ImageDraw.ImageDraw, size: tuple[int, int], top: str, bottom: str) -> None:
    width, height = size
    top_rgb = Image.new("RGB", (1, 1), top).getpixel((0, 0))
    bottom_rgb = Image.new("RGB", (1, 1), bottom).getpixel((0, 0))
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top_rgb[i] * (1 - ratio) + bottom_rgb[i] * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)


def _draw_scene(draw: ImageDraw.ImageDraw, size: tuple[int, int], scene_preset: str) -> None:
    width, height = size
    if scene_preset == "premium_dark":
        _draw_gradient_background(draw, size, "#171b24", "#313846")
        draw.rectangle((0, int(height * 0.78), width, height), fill="#242a34")
        return
    if scene_preset == "marketplace_white":
        _draw_gradient_background(draw, size, "#ffffff", "#f4f6f8")
        draw.rectangle((0, int(height * 0.8), width, height), fill="#ffffff")
        return
    if scene_preset == "desktop_lifestyle":
        _draw_gradient_background(draw, size, "#eef4fb", "#d9e3ee")
        draw.rectangle((0, int(height * 0.73), width, height), fill="#c7a276")
        draw.rounded_rectangle((int(width * 0.08), int(height * 0.58), int(width * 0.2), int(height * 0.72)), radius=10, fill="#dde3ea")
        draw.ellipse((int(width * 0.78), int(height * 0.6), int(width * 0.88), int(height * 0.72)), fill="#b2bdc9")
        return
    if scene_preset == "gift_table":
        _draw_gradient_background(draw, size, "#f6efe7", "#e9dccd")
        draw.rectangle((0, int(height * 0.74), width, height), fill="#e2d2be")
        draw.rounded_rectangle((int(width * 0.1), int(height * 0.6), int(width * 0.22), int(height * 0.73)), radius=14, fill="#e8eef8")
        draw.rounded_rectangle((int(width * 0.74), int(height * 0.62), int(width * 0.86), int(height * 0.74)), radius=12, fill="#d9b9aa")
        return
    if scene_preset == "retail_shelf":
        _draw_gradient_background(draw, size, "#f4f6fb", "#dce4ef")
        for y in (0.36, 0.56, 0.77):
            yy = int(height * y)
            draw.rectangle((0, yy, width, yy + max(8, height // 55)), fill="#d8dee8")
        return
    _draw_gradient_background(draw, size, "#f7f9fc", "#e8edf4")
    draw.rectangle((0, int(height * 0.8), width, height), fill="#edf1f6")


def _paste_with_mask(base: Image.Image, layer: Image.Image, mask: Image.Image) -> None:
    base.paste(layer, (0, 0), mask)


def _draw_product_frame(
    *,
    size: tuple[int, int],
    model_key: str,
    texture: Image.Image | None,
    scene_preset: str,
    camera_preset: str,
    camera_distance: str,
    motion_path: list[dict[str, float]],
    progress: float,
) -> Image.Image:
    width, height = size
    frame = Image.new("RGB", size, "#f7f9fc")
    draw = ImageDraw.Draw(frame)
    _draw_scene(draw, size, scene_preset)

    distance_profile = CAMERA_DISTANCE_PRESETS.get(camera_distance) or CAMERA_DISTANCE_PRESETS["wide"]
    frame_ratio = float(distance_profile.get("frameHeightRatio") or 0.58)
    safe_margin_ratio = float(distance_profile.get("safeMarginRatio") or 0.065)
    if camera_preset == "slow_push_in":
        frame_ratio *= 1 + progress * 0.08
    elif camera_preset == "detail_sweep":
        frame_ratio *= 1.03
    elif camera_preset == "top_reveal":
        frame_ratio *= 0.92 + progress * 0.1
    product_height = int(height * min(0.88, max(0.42, frame_ratio)))
    product_width = int(product_height * (0.58 if model_key == "cup_1660" else 0.76))
    center_x = int(width * 0.5)
    center_y = int(height * 0.57)
    if scene_preset in {"desktop_lifestyle", "gift_table", "retail_shelf"}:
        center_y = max(center_y, int(height * 0.58))
    left, top, right, bottom = _fit_rect_to_safe_bounds(
        width=width,
        height=height,
        center_x=center_x,
        center_y=center_y,
        product_width=product_width,
        product_height=product_height,
        safe_margin_ratio=safe_margin_ratio,
    )
    product_width = right - left
    product_height = bottom - top

    shadow_y = min(height - 20, bottom + max(8, height // 80))
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((left + product_width * 0.08, shadow_y - product_height * 0.05, right - product_width * 0.08, shadow_y + product_height * 0.05), fill=(0, 0, 0, 58))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(6, int(width * 0.012))))
    frame = Image.alpha_composite(frame.convert("RGBA"), shadow)

    product = Image.new("RGBA", size, (0, 0, 0, 0))
    product_draw = ImageDraw.Draw(product)
    texture_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)

    if model_key == "cup_1660":
        body = (
            left + product_width * 0.1,
            top + product_height * 0.12,
            right - product_width * 0.24,
            bottom - product_height * 0.04,
        )
        mask_draw.rounded_rectangle(tuple(map(int, body)), radius=max(18, product_width // 9), fill=255)
        tex = _texture_fill(texture, (int(body[2] - body[0]), int(body[3] - body[1])), model_key).convert("RGBA")
        texture_layer.paste(tex, (int(body[0]), int(body[1])))
        product_draw.ellipse((int(body[0]), int(body[1] - product_height * 0.04), int(body[2]), int(body[1] + product_height * 0.12)), outline=(42, 52, 64, 180), width=max(2, width // 260))
        handle = (
            right - product_width * 0.32,
            top + product_height * 0.32,
            right - product_width * 0.04,
            top + product_height * 0.68,
        )
        product_draw.arc(tuple(map(int, handle)), start=-72, end=78, fill=(42, 52, 64, 190), width=max(8, product_width // 13))
        product_draw.rounded_rectangle(tuple(map(int, body)), radius=max(18, product_width // 9), outline=(42, 52, 64, 210), width=max(2, width // 320))
    else:
        body = (left + product_width * 0.06, top + product_height * 0.08, right - product_width * 0.06, bottom - product_height * 0.06)
        mask_draw.rounded_rectangle(tuple(map(int, body)), radius=max(28, product_width // 8), fill=255)
        tex = _texture_fill(texture, (int(body[2] - body[0]), int(body[3] - body[1])), model_key).convert("RGBA")
        texture_layer.paste(tex, (int(body[0]), int(body[1])))
        product_draw.rounded_rectangle(tuple(map(int, body)), radius=max(28, product_width // 8), outline=(34, 42, 55, 215), width=max(3, width // 260))
        product_draw.arc((int(left + product_width * 0.2), int(top - product_height * 0.04), int(right - product_width * 0.2), int(top + product_height * 0.42)), start=190, end=350, fill=(34, 42, 55, 180), width=max(8, product_width // 22))
        product_draw.line((int(body[0] + product_width * 0.16), int(body[1] + product_height * 0.18), int(body[2] - product_width * 0.16), int(body[1] + product_height * 0.18)), fill=(255, 255, 255, 120), width=max(2, width // 300))

    mask = mask.filter(ImageFilter.GaussianBlur(radius=0.2))
    _paste_with_mask(product, texture_layer, mask)
    frame = Image.alpha_composite(frame, product)
    return frame.convert("RGB")


def _encode_mp4(frames: list[Image.Image], *, fps: int) -> bytes:
    ffmpeg = _get_ffmpeg_executable()
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        output_path = tmp.name
    command = [
        ffmpeg,
        "-y",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        output_path,
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        assert process.stdin is not None
        for frame in frames:
            buffer = BytesIO()
            frame.save(buffer, format="PNG")
            process.stdin.write(buffer.getvalue())
        process.stdin.close()
        process.wait(timeout=90)
        stderr = process.stderr.read() if process.stderr else b""
        if process.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", errors="ignore")[-500:])
        with open(output_path, "rb") as handle:  # noqa: PTH123 - temporary ffmpeg output
            return handle.read()
    finally:
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
        except Exception:
            pass
        try:
            os.remove(output_path)
        except OSError:
            pass


class Product3DRenderVideoService:
    """Returns a truthful render plan before the real render worker is connected."""

    def catalog(self) -> dict[str, Any]:
        """Return the public configuration catalog for building 3D render-video UI."""
        return {
            "businessKey": "product_3d_render_video",
            "version": "product-3d-render-video-catalog-v1",
            "status": "active",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "defaults": {
                "modelKey": "cup_1660",
                "materialSlot": "front",
                "cameraPreset": "orbit_360",
                "cameraDistance": "wide",
                "scenePreset": "clean_studio",
                "durationSeconds": 6,
                "aspectRatio": "16:9",
                "motionPath": _normalize_motion_path(None),
            },
            "models": [
                {
                    "modelKey": key,
                    "displayName": value.get("displayName"),
                    "preferredFile": value.get("preferredFile"),
                    "productType": value.get("productType"),
                    "recommendedMaterialSlot": value.get("recommendedMaterialSlot"),
                    "materialSlots": value.get("materialSlots") or [],
                    "hasUv": bool(value.get("hasUv")),
                    "hasAnimation": bool(value.get("hasAnimation")),
                    "sourceArchive": value.get("sourceArchive"),
                    "notes": value.get("notes") or [],
                }
                for key, value in MODEL_REGISTRY.items()
            ],
            "scenePresets": [
                {
                    "key": key,
                    "label": value.get("label"),
                    "lighting": value.get("lighting"),
                    "background": value.get("background"),
                    "sceneModel": value.get("sceneModel"),
                    "placement": value.get("placement"),
                    "asset": _scene_asset_package(key),
                    "fusion": _scene_fusion_policy(key),
                    "renderElements": _scene_render_elements(key),
                    "sceneVisualAcceptance": _scene_visual_acceptance(key),
                }
                for key, value in SCENE_PRESETS.items()
            ],
            "sceneAssetSources": _scene_asset_sources(),
            "cameraPresets": [
                {
                    "key": key,
                    **value,
                }
                for key, value in CAMERA_PRESETS.items()
            ],
            "cameraDistances": [
                {
                    "key": key,
                    **value,
                }
                for key, value in CAMERA_DISTANCE_PRESETS.items()
            ],
            "durationOptions": [3, 5, 6, 8, 12],
            "aspectRatioOptions": ["16:9", "1:1", "4:5", "9:16"],
            "renderers": {
                "browserPreview": {
                    "status": "ready",
                    "boundary": "client_threejs_wysiwyg_preview",
                    "deliverable": "local_mp4_or_webm_preview",
                },
                "serverLightweight": {
                    "status": "ready",
                    "worker": "lightweight_scene_renderer_v1",
                    "deliverables": ["rendered_video_mp4", "cover_frame_png", "render_manifest_json"],
                },
                "highFidelity": {
                    "status": "planned",
                    "worker": "blender_or_headless_threejs",
                    "replacementPolicy": "same request contract; replace renderer behind /runs",
                },
            },
            "endpoints": {
                "catalog": "GET /api/business/product-3d-render-video/catalog",
                "preview": "POST /api/business/product-3d-render-video/preview",
                "renderRun": "POST /api/business/product-3d-render-video/runs",
                "poll": "POST /api/business/runs/get",
            },
        }

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

        camera_distance_key = _clean_text(getattr(payload, "cameraDistance", None)) or "wide"
        camera_distance = CAMERA_DISTANCE_PRESETS.get(camera_distance_key)
        if not camera_distance:
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_CAMERA_DISTANCE_INVALID")

        scene_preset_key = _clean_text(getattr(payload, "scenePreset", None)) or "clean_studio"
        scene_preset = SCENE_PRESETS.get(scene_preset_key)
        if not scene_preset:
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_SCENE_PRESET_INVALID")
        scene_asset = _scene_asset_package(scene_preset_key)
        raw_camera_plan = getattr(payload, "cameraPlan", None)
        motion_path = _camera_plan_points(raw_camera_plan) or _normalize_motion_path(getattr(payload, "motionPath", None))
        framing_safety = _framing_safety(camera_distance_key, motion_path)
        scene_visual_acceptance = _scene_visual_acceptance(
            scene_preset_key,
            camera_distance_key=camera_distance_key,
            motion_path=motion_path,
        )

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
        camera_plan = raw_camera_plan if isinstance(raw_camera_plan, dict) else {}
        camera_plan = {
            "version": _clean_text(camera_plan.get("version")) or "camera-plan-v1",
            "template": _clean_text(camera_plan.get("template")) or camera_preset_key,
            "productMotion": "fixed",
            "cameraMotion": _clean_text(camera_plan.get("cameraMotion")) or "path_playback",
            "playbackConfirmed": bool(camera_plan.get("playbackConfirmed")),
            "confirmationRequiredBeforeRender": True,
            "durationSeconds": duration_seconds,
            "aspectRatio": aspect_ratio,
            "cameraDistance": camera_distance_key,
            "scenePreset": scene_preset_key,
            "focusTarget": _clean_text(camera_plan.get("focusTarget")) or "product_center",
            "focusSlot": _clean_text(camera_plan.get("focusSlot")) or material_slot,
            "path": {
                "coordinateSpace": "normalized_camera_path_preview",
                "points": motion_path,
                "pointCount": len(motion_path),
            },
            "constraints": {
                "productFixed": True,
                "keepFullProductInFrame": True,
                "avoidTextureDistortion": True,
            },
            "rationale": _clean_text(camera_plan.get("rationale")) or _clean_text(camera_preset.get("description")),
        }

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
                "asset": scene_asset,
                "assetId": scene_asset.get("assetId"),
                "assetStatus": scene_asset.get("assetStatus"),
                "renderFidelity": scene_asset.get("renderFidelity"),
                "fusion": _scene_fusion_policy(scene_preset_key),
                "renderElements": _scene_render_elements(scene_preset_key),
                "visualAcceptance": scene_visual_acceptance,
                **scene_preset,
            },
            "camera": {
                "key": camera_preset_key,
                "preset": camera_preset_key,
                "distanceKey": camera_distance_key,
                "distance": {
                    "key": camera_distance_key,
                    **camera_distance,
                },
                "framing": {
                    "mode": "fit_product_safe_bounds",
                    "primaryRule": "The product remains fixed; camera path playback must keep the full product visible.",
                    "frameHeightRatio": camera_distance.get("frameHeightRatio"),
                    "safeMarginRatio": camera_distance.get("safeMarginRatio"),
                    "recommendedUse": "Use wide/standard for final marketplace assets; reserve close for supplemental detail clips.",
                    "safety": framing_safety,
                },
                **camera_preset,
            },
            "cameraPlan": camera_plan,
            "framingSafety": framing_safety,
            "sceneVisualAcceptance": scene_visual_acceptance,
            "motionPath": {
                "mode": "legacy_camera_path_points",
                "coordinateSpace": "normalized_camera_path_preview",
                "points": motion_path,
                "pointCount": len(motion_path),
                "description": "Compatibility field for camera path points. Product stays fixed; new integrations should read renderPlan.cameraPlan.",
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
                "sceneAssetReady": scene_asset.get("assetStatus") == "ready",
                "sceneAssetId": scene_asset.get("assetId"),
                "sceneRenderFidelity": scene_asset.get("renderFidelity"),
                "sceneVisualAcceptanceStatus": scene_visual_acceptance.get("status"),
                "renderWorkerReady": True,
                "renderWorker": "lightweight_scene_renderer_v1",
                "highFidelityWorkerReady": False,
                "highFidelityWorker": "planned",
                "warnings": warnings,
            },
            "renderPlan": render_plan,
            "review": {
                "score": readiness_score,
                "issues": warnings,
                "nextActions": [
                    "把 3D 模型归档到受控模型目录，并记录 modelKey 到能力配置。",
                    "用 Three.js 先做交互预览，验证贴图方向、比例和材质槽。",
                    "当前可用轻量服务端渲染输出 MP4/OSS；商用品质再替换为 Blender/headless Three.js 高保真 worker。",
                    "确认外部场景资产授权、遮挡规则和渲染质量后，再把候选场景入库。",
                ],
                "sceneVisualAcceptance": scene_visual_acceptance,
            },
            "execution": {
                "videoGenerated": False,
                "costActions": [],
                "note": "This endpoint is a contract/plan preview only. It does not call KIE, Vidu, or any paid video model.",
                "serverRenderEndpoint": "/api/business/product-3d-render-video/runs",
                "serverRenderWorker": "lightweight_scene_renderer_v1",
            },
            "audit": {
                "userId": user_id,
                "source": _clean_text(getattr(payload, "source", None)) or "eval",
                "traceId": _clean_text(getattr(payload, "traceId", None)) or None,
            },
        }

    def render_video(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        request_id = _clean_text(getattr(payload, "requestId", None)) or f"p3d_{uuid4().hex[:12]}"
        texture_url = _first_texture_url(payload)
        if not texture_url:
            raise HTTPException(status_code=400, detail="PRODUCT_3D_RENDER_VIDEO_TEXTURE_REQUIRED")
        preview_payload = payload
        if hasattr(payload, "model_copy"):
            preview_payload = payload.model_copy(update={"outputMode": "plan_only", "requestId": request_id})
        plan = self.preview(preview_payload, user_id=user_id)
        render_plan = plan.get("renderPlan") if isinstance(plan.get("renderPlan"), dict) else {}
        model = plan.get("model") if isinstance(plan.get("model"), dict) else {}
        model_key = _clean_text(model.get("modelKey")) or "cup_1660"
        texture_application = (
            render_plan.get("textureApplication") if isinstance(render_plan.get("textureApplication"), dict) else {}
        )
        texture_slots_for_manifest = [
            {
                "materialSlot": _clean_text(item.get("materialSlot") or item.get("material_slot")),
                "imageUrl": _clean_text(item.get("imageUrl") or item.get("image_url") or item.get("url")),
                "label": _clean_text(item.get("label")),
            }
            for item in (texture_application.get("textureSlots") or [])
            if isinstance(item, dict)
        ]
        scene = render_plan.get("scene") if isinstance(render_plan.get("scene"), dict) else {}
        camera = render_plan.get("camera") if isinstance(render_plan.get("camera"), dict) else {}
        motion = render_plan.get("motionPath") if isinstance(render_plan.get("motionPath"), dict) else {}
        camera_plan = render_plan.get("cameraPlan") if isinstance(render_plan.get("cameraPlan"), dict) else {}
        scene_preset = _clean_text(scene.get("key") or scene.get("preset")) or "clean_studio"
        scene_asset = _scene_asset_package(scene_preset)
        camera_preset = _clean_text(camera.get("key") or camera.get("preset")) or "orbit_360"
        camera_distance = _clean_text((camera.get("distance") or {}).get("key") if isinstance(camera.get("distance"), dict) else None) or "wide"
        motion_path = _camera_plan_points(camera_plan) or (motion.get("points") if isinstance(motion.get("points"), list) else _normalize_motion_path(None))
        scene_visual_acceptance = (
            render_plan.get("sceneVisualAcceptance")
            if isinstance(render_plan.get("sceneVisualAcceptance"), dict)
            else _scene_visual_acceptance(scene_preset, camera_distance_key=camera_distance, motion_path=motion_path)
        )
        duration_seconds = max(1, min(30, int(render_plan.get("durationSeconds") or getattr(payload, "durationSeconds", None) or 6)))
        aspect_ratio = _clean_text(render_plan.get("aspectRatio") or getattr(payload, "aspectRatio", None)) or "16:9"
        fps = 10
        frame_count = max(fps, duration_seconds * fps)
        size = _aspect_dimensions(aspect_ratio)
        texture = _load_texture_image(texture_url)
        if texture is None:
            raise HTTPException(status_code=502, detail="PRODUCT_3D_RENDER_VIDEO_TEXTURE_LOAD_FAILED")
        frames = [
            _draw_product_frame(
                size=size,
                model_key=model_key,
                texture=texture,
                scene_preset=scene_preset,
                camera_preset=camera_preset,
                camera_distance=camera_distance,
                motion_path=motion_path,
                progress=index / max(1, frame_count - 1),
            )
            for index in range(frame_count)
        ]
        video_bytes = _encode_mp4(frames, fps=fps)
        cover_buffer = BytesIO()
        frames[0].save(cover_buffer, format="PNG")
        manifest = {
            "businessKey": "product_3d_render_video",
            "requestId": request_id,
            "renderer": "lightweight_scene_renderer_v1",
            "rendererBoundary": "server-side lightweight scene renderer; replaceable by Blender/headless Three.js without API changes",
            "sceneModelVersion": "procedural-commerce-scene-v2",
            "sceneAsset": {
                "assetId": scene_asset.get("assetId"),
                "assetType": scene_asset.get("assetType"),
                "assetStatus": scene_asset.get("assetStatus"),
                "renderFidelity": scene_asset.get("renderFidelity"),
                "source": scene_asset.get("source"),
                "license": scene_asset.get("license"),
                "geometry": scene_asset.get("geometry"),
                "materialPolicy": scene_asset.get("materialPolicy"),
                "highFidelityTarget": scene_asset.get("highFidelityTarget"),
                "externalCandidates": scene_asset.get("externalCandidates"),
                "ingestPolicy": scene_asset.get("ingestPolicy"),
            },
            "sceneFusion": _scene_fusion_policy(scene_preset),
            "sceneElements": _scene_render_elements(scene_preset),
            "sceneVisualAcceptance": scene_visual_acceptance,
            "framingPolicy": {
                "mode": "fit_product_safe_bounds",
                "safeMarginRatio": (CAMERA_DISTANCE_PRESETS.get(camera_distance) or CAMERA_DISTANCE_PRESETS["wide"]).get("safeMarginRatio"),
                "framingSafety": render_plan.get("framingSafety") or _framing_safety(camera_distance, motion_path),
                "note": "Product remains fixed. Camera path playback is constrained to keep the product inside the visible frame.",
            },
            "framingSafety": render_plan.get("framingSafety") or _framing_safety(camera_distance, motion_path),
            "modelKey": model_key,
            "textureApplication": {
                "mode": _clean_text(texture_application.get("mode")) or "slot_texture_mapping",
                "activeMaterialSlot": _clean_text(texture_application.get("activeMaterialSlot"))
                or _clean_text(texture_application.get("materialSlot"))
                or _clean_text(getattr(payload, "materialSlot", None)),
                "textureSlotCount": len(texture_slots_for_manifest),
                "textureSlots": texture_slots_for_manifest,
                "primaryTextureUrl": texture_url,
                "preserveUv": True,
                "note": (
                    "The lightweight renderer currently uses the primary texture for its simplified preview frame; "
                    "the manifest preserves every submitted material-slot binding for high-fidelity workers."
                ),
            },
            "textureSourceUrl": texture_url,
            "scenePreset": scene_preset,
            "cameraPreset": camera_preset,
            "cameraDistance": camera_distance,
            "cameraPlan": camera_plan
            or {
                "version": "camera-plan-v1",
                "template": camera_preset,
                "productMotion": "fixed",
                "cameraMotion": "path_playback",
                "playbackConfirmed": bool(getattr(payload, "cameraPlan", None) and getattr(payload, "cameraPlan", {}).get("playbackConfirmed")),
                "confirmationRequiredBeforeRender": True,
                "cameraDistance": camera_distance,
                "scenePreset": scene_preset,
                "path": {
                    "coordinateSpace": "normalized_camera_path_preview",
                    "points": motion_path,
                    "pointCount": len(motion_path),
                },
                "constraints": {
                    "productFixed": True,
                    "keepFullProductInFrame": True,
                    "avoidTextureDistortion": True,
                },
            },
            "motionPath": motion_path,
            "durationSeconds": duration_seconds,
            "fps": fps,
            "width": size[0],
            "height": size[1],
            "aspectRatio": aspect_ratio,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
        user_segment = user_id or "product-3d-render-video"
        try:
            video_upload = oss_service.upload_bytes(
                user_id=user_segment,
                filename=f"{request_id}.mp4",
                data=video_bytes,
                content_type="video/mp4",
            )
            cover_upload = oss_service.upload_bytes(
                user_id=user_segment,
                filename=f"{request_id}-cover.png",
                data=cover_buffer.getvalue(),
                content_type="image/png",
            )
            manifest_upload = oss_service.upload_bytes(
                user_id=user_segment,
                filename=f"{request_id}-manifest.json",
                data=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                content_type="application/json",
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_FAILED") from exc

        video_url = _clean_text(video_upload.get("url"))
        cover_url = _clean_text(cover_upload.get("url"))
        manifest_url = _clean_text(manifest_upload.get("url"))
        if not video_url or not cover_url or not manifest_url:
            raise HTTPException(status_code=500, detail="PRODUCT_3D_RENDER_VIDEO_RENDER_RUN_FAILED")
        assets = [
            {"type": "video", "role": "rendered_video", "ossUrl": video_url, "url": video_url, "contentType": "video/mp4"},
            {"type": "image", "role": "cover_frame", "ossUrl": cover_url, "url": cover_url, "contentType": "image/png"},
            {"type": "manifest", "role": "render_manifest", "ossUrl": manifest_url, "url": manifest_url, "contentType": "application/json"},
        ]
        next_render_plan = dict(render_plan)
        next_render_plan["executionStatus"] = "rendered"
        next_render_plan["renderer"] = "lightweight_scene_renderer_v1"
        next_render_plan["outputMode"] = "render_video"
        return {
            **plan,
            "status": "succeeded",
            "version": "product-3d-render-video-lightweight-v1",
            "renderPlan": next_render_plan,
            "assetReadiness": {
                **(plan.get("assetReadiness") if isinstance(plan.get("assetReadiness"), dict) else {}),
                "renderWorkerReady": True,
                "renderWorker": "lightweight_scene_renderer_v1",
            },
            "renderAssetPackage": {
                "deliveryStatus": "assets_ready",
                "renderer": "lightweight_scene_renderer_v1",
                "videoUrl": video_url,
                "coverFrameUrl": cover_url,
                "manifestUrl": manifest_url,
                "textureApplication": manifest["textureApplication"],
                "assets": assets,
                "manifest": manifest,
            },
            "videoResult": {
                "status": "succeeded",
                "videoUrls": [video_url],
                "storedAssets": assets,
            },
            "imageUrls": [cover_url],
            "videoUrls": [video_url],
            "execution": {
                "videoGenerated": True,
                "costActions": ["server_lightweight_3d_render"],
                "note": "Server-side lightweight scene renderer generated MP4, cover frame, and manifest. Blender/headless Three.js can replace this renderer behind the same API.",
            },
        }

    def submit_render_run(self, payload: Any, *, user_id: str | None = None) -> dict[str, Any]:
        return self.render_video(payload, user_id=user_id)


product_3d_render_video_service = Product3DRenderVideoService()
