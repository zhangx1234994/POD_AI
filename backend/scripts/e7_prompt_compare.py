#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import sys
import time
import uuid
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.oss import oss_service


def main() -> int:
    root = Path("/Volumes/MAC 1/pod_codex")
    report_dir = root / "reports" / f"e7_prompt_compare_{time.strftime('%Y%m%d_%H%M%S')}"
    report_dir.mkdir(parents=True, exist_ok=True)

    img_path = Path("/Volumes/MAC 1/下载/abc04bf0-1774824991.png")
    server_name = "158"
    base = "http://117.50.80.158:8079"
    seed = 424242
    steps = 6
    cfg = 1.0
    denoise = 0.60
    workflow = json.loads((root / "backend/app/workflows/comfyui/e7_flux2_liebian.json").read_text())

    prompts = {
        "p1_caption": "这是白色背景的满铺重复儿童扁平图案，画面中均匀分布鲸鱼、云朵、彩虹和雨滴等元素，主体造型简洁圆润，整体为低龄感、柔和配色的卡通插画风格，元素大小适中、节奏均匀，留白充足，装饰密度中等，无文字元素。",
        "p2_structure": "保持白色背景、规则满铺重复的排布方式、元素之间均匀稳定的间距关系和整体版式秩序，保留鲸鱼、云朵、彩虹、雨滴这些核心元素及其重复节奏，维持低龄扁平、轮廓圆润、柔和配色和充足留白，不要让元素分布变得松散、杂乱或失去规律性。",
        "p3_targeted": "保持白底、规则重复排布、元素数量级和整体节奏不变，保留鲸鱼、云朵、彩虹、雨滴这组元素体系，只对鲸鱼造型、云朵表情和彩虹局部形态做同风格微调，维持低龄扁平、柔和配色、简洁圆润轮廓和均匀留白，不要增加复杂纹理，不要改变整体版式秩序。",
    }

    with img_path.open("rb") as f:
        data = f.read()
    content_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
    up = oss_service.upload_bytes(user_id="prompt-compare", filename=img_path.name, data=data, content_type=content_type)
    image_url = up["url"]
    (report_dir / img_path.name).write_bytes(data)
    print("uploaded", image_url, flush=True)

    results: list[dict[str, object]] = []
    client = httpx.Client(timeout=30)
    for key, prompt in prompts.items():
        wf = deepcopy(workflow)
        wf["10"]["inputs"]["url"] = image_url
        wf["13"]["inputs"]["text1"] = prompt
        wf["18"]["inputs"]["cfg"] = cfg
        wf["19"]["inputs"]["noise_seed"] = seed
        wf["21"]["inputs"]["steps"] = steps
        wf["21"]["inputs"]["denoise"] = denoise
        wf["24"]["inputs"]["batch_size"] = 1
        prefix = f"E7PromptCmp_{server_name}_{key}_{uuid.uuid4().hex[:8]}"
        wf["27"]["inputs"]["filename_prefix"] = prefix
        r = client.post(f"{base}/prompt", json={"prompt": wf})
        r.raise_for_status()
        prompt_id = r.json().get("prompt_id")
        print("submitted", key, prompt_id, flush=True)

        entry = None
        for _ in range(90):
            hr = client.get(f"{base}/history/{prompt_id}")
            hr.raise_for_status()
            hist = hr.json()
            entry = hist.get(prompt_id) or hist if isinstance(hist, dict) else None
            outputs = (entry or {}).get("outputs") if isinstance(entry, dict) else None
            if isinstance(outputs, dict) and outputs:
                break
            time.sleep(4)

        outputs = (entry or {}).get("outputs") if isinstance(entry, dict) else {}
        images = []
        for node in outputs.values() if isinstance(outputs, dict) else []:
            node_images = node.get("images") if isinstance(node, dict) else None
            if isinstance(node_images, list):
                images.extend(node_images)

        if not images:
            results.append({"key": key, "prompt": prompt, "status": "no_images", "prompt_id": prompt_id})
            continue

        img_info = images[0]
        view_url = (
            f"{base}/view?filename={img_info.get('filename')}"
            f"&subfolder={img_info.get('subfolder') or ''}&type={img_info.get('type') or 'output'}"
        )
        ir = client.get(view_url)
        ir.raise_for_status()
        out_name = f"{key}.png"
        out_path = report_dir / out_name
        out_path.write_bytes(ir.content)
        Image.open(BytesIO(ir.content)).save(out_path)
        results.append(
            {
                "key": key,
                "prompt": prompt,
                "status": "ok",
                "prompt_id": prompt_id,
                "view_url": view_url,
                "file": str(out_path),
            }
        )

    summary = {
        "image_url": image_url,
        "server": server_name,
        "denoise": denoise,
        "seed": seed,
        "steps": steps,
        "cfg": cfg,
        "results": results,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    cards: list[str] = []
    for r in results:
        title = str(r["key"])
        prompt = str(r["prompt"])
        if r["status"] != "ok":
            cards.append(
                f"<div class='card'><h3>{title}</h3><pre>{prompt}</pre><p>status={r['status']}</p><p>{r['prompt_id']}</p></div>"
            )
        else:
            rel = Path(str(r["file"])).name
            cards.append(
                f"<div class='card'><h3>{title}</h3><img src='{rel}' /><pre>{prompt}</pre><p>{r['prompt_id']}</p><p><a href='{r['view_url']}'>view_url</a></p></div>"
            )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>E7 prompt compare</title>
  <style>
    body {{ font-family: sans-serif; padding: 24px; background: #111; color: #eee; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .card {{ background: #1b1b1b; border: 1px solid #333; border-radius: 12px; padding: 12px; }}
    img {{ width: 100%; height: auto; border-radius: 8px; background: #fff; }}
    a {{ color: #8ab4ff; }}
    pre {{ white-space: pre-wrap; background: #0b0f14; padding: 10px; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>E7 prompt compare</h1>
  <p>server={server_name} denoise={denoise} seed={seed}</p>
  <div class='card'><h3>original</h3><img src='{img_path.name}' /></div>
  <div class='grid'>{''.join(cards)}</div>
</body>
</html>"""
    (report_dir / "index.html").write_text(html, encoding="utf-8")

    print("REPORT", report_dir, flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
