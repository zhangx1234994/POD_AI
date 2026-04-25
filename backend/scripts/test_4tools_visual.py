#!/usr/bin/env python3
"""Visual end-to-end test for the 4 new ComfyUI tools using local dataset images."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import AbilityTask
from app.schemas.ability_tasks import AbilityTaskCreateRequest
from app.services.ability_task_service import get_ability_task_service
from app.services.auth_service import auth_service
from app.services.media_ingest import media_ingest_service

DATASET_DIR = Path("/Volumes/MAC 1/pod_codex/对照测试集/AI数据集")

TESTS = [
    {
        "name": "beijing_koutu",
        "ability_id": "comfyui_beijing_koutu",
        "file": "005ytlq1gy1i8xd0rhovnj31401e0174.jpg",
        "inputs": {},
    },
    {
        "name": "toubu_kouxiang",
        "ability_id": "comfyui_toubu_kouxiang",
        "file": "Custom Photo & Text Pillow - Personalized Memorial Gift for Family, Pets, Mother's Day - 16x16 Inch Throw Pillow Cover, Home Decor - Soft Plush Pillow for Loved Ones.jpg",
        "inputs": {},
    },
    {
        "name": "qwen2512_print_shape_text_enhance",
        "ability_id": "comfyui_qwen2512_print_shape_text_enhance",
        "file": "202602121732376038443.jpg",
        "inputs": {"prompt": "enhanced pink ribbon and bow design", "bili": 50},
    },
    {
        "name": "flux2_9b_liebian_sifang",
        "ability_id": "comfyui_flux2_9b_liebian_sifang",
        "file": "BSFHH Pack of 2 Tapestry -Landscape Flower Aesthetic Long Tapestries for Living Room and Bedroom Wall Decor 13_ Wx51 H (Type 10).jpg",
        "inputs": {"prompt": "beautiful mountain flower seamless pattern"},
    },
]


def upload_to_oss(local_path: Path) -> str:
    with open(local_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    result = media_ingest_service.ingest_from_base64(
        b64,
        user_id="tester",
        filename_hint=local_path.name,
        mime_type="image/jpeg",
        tag="eval-test",
    )
    return result["ossUrl"]


def submit_and_poll(ability_id: str, image_url: str, inputs: dict) -> dict:
    user = auth_service.build_service_user()
    payload = AbilityTaskCreateRequest(
        abilityId=ability_id,
        inputs=inputs | {"url": image_url},
    )
    task = get_ability_task_service().enqueue(ability_id=payload.abilityId, payload=payload, user=user)
    task_id = task["id"]
    print(f"  Submitted task {task_id}")

    for _ in range(60):
        time.sleep(5)
        with get_session() as session:
            db_task = session.get(AbilityTask, task_id)
            if db_task.status in {"succeeded", "failed"}:
                return {
                    "status": db_task.status,
                    "error": db_task.error_message,
                    "result": db_task.result_payload,
                    "duration_ms": db_task.duration_ms,
                }
    return {"status": "timeout", "error": "POLL_TIMEOUT", "result": None, "duration_ms": None}


def main():
    results = []
    for test in TESTS:
        print(f"\n[{test['name']}] Testing...")
        local_path = DATASET_DIR / test["file"]
        if not local_path.exists():
            print(f"  SKIP: file not found {local_path}")
            continue

        image_url = upload_to_oss(local_path)
        print(f"  Uploaded to {image_url}")

        result = submit_and_poll(test["ability_id"], image_url, test["inputs"])
        print(f"  Result: {result['status']} | error={result['error']} | duration={result['duration_ms']}ms")

        images = []
        if result["result"]:
            images = result["result"].get("images") or result["result"].get("assets") or []
        results.append({"name": test["name"], "input_url": image_url, "output": result, "images": images})

    # Save report
    report_path = Path("/tmp/test_4tools_report.json")
    report_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nReport saved to {report_path}")
    for r in results:
        print(f"\n{r['name']}:")
        print(f"  Input: {r['input_url']}")
        for img in r.get("images", []):
            print(f"  Output: {img.get('url') or img.get('ossUrl')}")


if __name__ == "__main__":
    main()
