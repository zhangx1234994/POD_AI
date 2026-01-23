#!/usr/bin/env python3
"""Quick validity checks for PODI's ComfyUI workflow parameter mappings.

This script:
- uploads a local test image to OSS
- runs the ComfyUI abilities directly via the backend service layer
- prints output image sizes so we can confirm that size/width/height params work

Run:
  python3 scripts/comfyui_param_validity_test.py
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image


def _find_test_image() -> Path:
    candidates = []
    for pat in [
        "提取测试图/*.jpg",
        "提取测试图/*.png",
        "workflowTemplates/*.jpg",
        "workflowTemplates/*.png",
        "*.jpg",
        "*.png",
    ]:
        candidates.extend(Path(".").glob(pat))
    for p in candidates:
        if p.is_file() and p.stat().st_size > 10_000:
            return p
    raise SystemExit("No test image found in repo root or 提取测试图/")


def _fetch_image_size(url: str) -> tuple[int, int]:
    r = httpx.get(url, timeout=180)
    r.raise_for_status()
    im = Image.open(BytesIO(r.content))
    return im.size


def main() -> int:
    # Allow running from repo root without setting PYTHONPATH.
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # Import inside main so running this script doesn't require PYTHONPATH if not used.
    from app.core.db import get_session
    from app.schemas import abilities as ability_schemas
    from app.services.ability_invocation import ability_invocation_service
    from app.services.ability_seed import ensure_default_abilities
    from app.services.auth_service import auth_service
    from app.services.executor_seed import ensure_default_executors
    from app.services.workflow_seed import ensure_default_bindings, ensure_default_workflows
    from app.services.oss import oss_service
    from app.models.integration import Ability

    img_path = _find_test_image()
    data = img_path.read_bytes()
    uploaded = oss_service.upload_bytes(user_id="comfyui-test", filename=img_path.name, data=data, content_type="image/jpeg")
    img_url = uploaded["url"]
    print("test_image", str(img_path))
    print("oss_url", img_url)

    with get_session() as s:
        ensure_default_executors(s)
        ensure_default_workflows(s)
        ensure_default_bindings(s)
        ensure_default_abilities(s)
        s.commit()

        abilities = {
            a.capability_key: a
            for a in s.query(Ability).filter(Ability.provider == "comfyui", Ability.status == "active").all()
        }

    user = auth_service.build_service_user()

    def run(capability_key: str, inputs: dict[str, Any]) -> dict[str, Any]:
        ability = abilities.get(capability_key)
        if not ability:
            raise SystemExit(f"Missing comfyui ability: {capability_key}")
        payload = ability_schemas.AbilityInvokeRequest(executorId=None, inputs=inputs, imageUrl=img_url, imageBase64=None)
        resp = ability_invocation_service.invoke(ability_id=ability.id, payload=payload, user=user, source="script")
        return resp.model_dump()

    def first_image_url(resp: dict[str, Any]) -> str | None:
        images = resp.get("images") or []
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                return first.get("ossUrl") or first.get("sourceUrl")
        assets = resp.get("assets") or []
        if isinstance(assets, list) and assets:
            first = assets[0]
            if isinstance(first, dict):
                return first.get("ossUrl") or first.get("sourceUrl")
        return None

    results: list[dict[str, Any]] = []

    # 1) 四方/两方连续：提交式（不等待出图），只验证参数接受/路由正确
    for size in (1024, 2048):
        out = run("sifang_lianxu", {"patternType": "twoway", "size": str(size)})
        meta = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
        results.append(
            {
                "ability": "sifang_lianxu",
                "size": size,
                "status": out.get("status"),
                "promptId": meta.get("promptId"),
                "executorId": meta.get("executorId"),
                "baseUrl": meta.get("baseUrl"),
            }
        )
        print(
            "sifang_lianxu",
            "size",
            size,
            "->",
            "status",
            out.get("status"),
            "executor",
            meta.get("executorId"),
            "promptId",
            meta.get("promptId"),
        )

    # 2) 印花提取：测宽高生效 + lora 下拉值可用
    for wh in ((1600, 1600), (2400, 2400)):
        out = run(
            "yinhua_tiqu",
            {
                "width": str(wh[0]),
                "height": str(wh[1]),
                "batch": "1",
                "lora": "印花提取-YinHuaTiQu-Qwen-Image-Edit-LoRA_V1.safetensors",
            },
        )
        url = first_image_url(out)
        sz = _fetch_image_size(url) if url else None
        results.append({"ability": "yinhua_tiqu", "width": wh[0], "height": wh[1], "out": url, "imgSize": sz})
        print("yinhua_tiqu", wh, "->", sz, "url", url)

    # 3) 花纹扩图：测 size(预缩放最长边) + expand 生效（只打印输出尺寸）
    for size in (512, 1024):
        out = run(
            "huawen_kuotu",
            {
                "size": str(size),
                "expand_left": "200",
                "expand_right": "200",
                "expand_top": "0",
                "expand_bottom": "0",
            },
        )
        meta = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
        results.append(
            {
                "ability": "huawen_kuotu",
                "size": size,
                "status": out.get("status"),
                "promptId": meta.get("promptId"),
                "executorId": meta.get("executorId"),
                "baseUrl": meta.get("baseUrl"),
            }
        )
        print(
            "huawen_kuotu",
            "size",
            size,
            "->",
            "status",
            out.get("status"),
            "executor",
            meta.get("executorId"),
            "promptId",
            meta.get("promptId"),
        )

    # 4) 极速/中速处理：测 width/height 生效（会按 8 的倍数归一）
    for key in ("jisu_chuli", "zhongsu_tisheng"):
        out = run(
            key,
            {
                "prompt": "把图片变成线稿",
                "width": "1500",
                "height": "900",
                "batch": "1",
            },
        )
        url = first_image_url(out)
        sz = _fetch_image_size(url) if url else None
        results.append({"ability": key, "out": url, "imgSize": sz})
        print(key, "1500x900", "->", sz, "url", url)

    print("\njson_summary:")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
