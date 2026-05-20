#!/usr/bin/env python3
"""Run real image-edit business API smoke cases and export the trace.

This script is intentionally separate from the default business patrol because
GPT Image 2 calls consume paid model quota. Use it only when validating the
image-edit release path.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
DEFAULT_SAMPLE_IMAGE_URL = (
    "https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/"
    "98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg"
)


@dataclass(frozen=True)
class ImageEditCase:
    key: str
    label: str
    edit_skill: str
    instruction: str
    selection_hints: list[dict[str, Any]]
    needs_reference: bool = False
    needs_target: bool = False


IMAGE_EDIT_CASES: tuple[ImageEditCase, ...] = (
    ImageEditCase(
        key="local_modify",
        label="局部修改",
        edit_skill="local_modify",
        instruction="把画面中央主体改成更鲜明的蓝绿色，保持原构图和周围元素不变。",
        selection_hints=[
            {
                "type": "box",
                "label": "中央主体",
                "x": 0.28,
                "y": 0.24,
                "width": 0.44,
                "height": 0.48,
                "unit": "ratio",
            }
        ],
        needs_target=True,
    ),
    ImageEditCase(
        key="reference_element_transfer",
        label="参考图替换",
        edit_skill="reference_element_transfer",
        instruction="参考图 #1 的颜色和纹理替换到主图中央主体，保持主图构图、边缘和背景稳定。",
        selection_hints=[
            {
                "type": "box",
                "label": "要替换的主体区域",
                "x": 0.28,
                "y": 0.24,
                "width": 0.44,
                "height": 0.48,
                "unit": "ratio",
            }
        ],
        needs_reference=True,
        needs_target=True,
    ),
    ImageEditCase(
        key="remove_inpaint",
        label="删除修补",
        edit_skill="remove_inpaint",
        instruction="删除框选区域内的小装饰元素，并用周围背景自然修补，不改变其他区域。",
        selection_hints=[
            {
                "type": "box",
                "label": "需要删除的小装饰",
                "x": 0.42,
                "y": 0.38,
                "width": 0.16,
                "height": 0.16,
                "unit": "ratio",
            }
        ],
        needs_target=True,
    ),
    ImageEditCase(
        key="color_reference_correction",
        label="补色校正",
        edit_skill="color_reference_correction",
        instruction="参考图 #1 的整体色彩倾向，对主图做补色校正；不要改变主体形状和版式。",
        selection_hints=[],
        needs_reference=True,
    ),
)


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"text": response.text[:2000]}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _headers(token: str | None) -> dict[str, str]:
    normalized = str(token or "").strip()
    return {"Authorization": f"Bearer {normalized}"} if normalized else {}


def _build_payload(
    case: ImageEditCase,
    *,
    image_url: str,
    reference_image_url: str,
    size: str,
    quality: str,
    tag: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "imageUrl": image_url,
        "editSkill": case.edit_skill,
        "instruction": case.instruction,
        "selectionHints": case.selection_hints,
        "size": size,
        "quality": quality,
        "outputFormat": "png",
        "source": "image-edit-release-patrol",
        "channel": "release-smoke",
        "traceId": f"image-edit-{case.key}-{tag}",
        "requestId": f"image-edit-{case.key}-{tag}",
        "tenantId": "podi-internal-patrol",
        "clientId": "image-edit-release-patrol",
        "metadata": {
            "patrol": True,
            "businessKey": "image_edit",
            "caseKey": case.key,
            "caseLabel": case.label,
        },
    }
    if case.needs_reference:
        payload["referenceImages"] = [
            {
                "url": reference_image_url,
                "label": "参考图 #1",
                "role": "reference",
            }
        ]
    return payload


def _post_json(client: httpx.Client, path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    response = client.post(path, json=payload)
    return response.status_code, _json_or_text(response)


def _poll_run(
    client: httpx.Client,
    *,
    run_id: str,
    interval_seconds: float,
    timeout_seconds: float,
    detail: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = datetime.now(timezone.utc).timestamp()
    records: list[dict[str, Any]] = []
    last: dict[str, Any] = {}

    while True:
        status_code, data = _post_json(client, "/api/business/runs/get", {"runId": run_id, "detail": detail})
        record = {
            "statusCode": status_code,
            "response": data,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)
        if isinstance(data, dict):
            last = data
            status = str(data.get("status") or data.get("taskStatus") or "").lower()
            if status in TERMINAL_STATUSES:
                return last, records
        if datetime.now(timezone.utc).timestamp() - started >= timeout_seconds:
            if isinstance(last, dict):
                last = dict(last)
            else:
                last = {}
            last.setdefault("status", "timeout")
            last.setdefault("error", f"巡检等待超过 {timeout_seconds:.0f} 秒。")
            return last, records
        time_sleep(interval_seconds)


def time_sleep(seconds: float) -> None:
    import time

    time.sleep(max(0.1, seconds))


def _case_result_summary(case: ImageEditCase, final: dict[str, Any], submit_status: int, submit_data: Any) -> dict[str, Any]:
    submit_run_id = submit_data.get("runId") if isinstance(submit_data, dict) else None
    final_status = str(final.get("status") or final.get("taskStatus") or "").lower()
    image_urls = final.get("imageUrls") if isinstance(final.get("imageUrls"), list) else []
    return {
        "caseKey": case.key,
        "caseLabel": case.label,
        "editSkill": case.edit_skill,
        "submitStatusCode": submit_status,
        "runId": submit_run_id,
        "finalStatus": final_status or "unknown",
        "imageUrls": image_urls,
        "error": final.get("error") or final.get("message"),
    }


def _select_cases(raw: str) -> list[ImageEditCase]:
    requested = {item.strip() for item in str(raw or "all").split(",") if item.strip()}
    if not requested or "all" in requested:
        return list(IMAGE_EDIT_CASES)
    by_key = {case.key: case for case in IMAGE_EDIT_CASES}
    unknown = sorted(requested - set(by_key))
    if unknown:
        raise ValueError(f"未知图编辑巡检用例：{', '.join(unknown)}")
    return [by_key[key] for key in requested]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run image-edit business API smoke cases.")
    parser.add_argument("--base-url", default=os.getenv("PODI_BACKEND", "http://127.0.0.1:8099"))
    parser.add_argument("--token", default=os.getenv("PODI_BUSINESS_API_KEY") or os.getenv("PODI_API_KEY"))
    parser.add_argument("--image-url", default=os.getenv("PODI_IMAGE_EDIT_SAMPLE_URL", DEFAULT_SAMPLE_IMAGE_URL))
    parser.add_argument("--reference-image-url", default=os.getenv("PODI_IMAGE_EDIT_REFERENCE_URL"))
    parser.add_argument("--size", default="auto")
    parser.add_argument("--quality", default="preview", choices=["auto", "preview", "production", "premium"])
    parser.add_argument("--cases", default="all", help="逗号分隔：local_modify,reference_element_transfer,remove_inpaint,color_reference_correction")
    parser.add_argument("--repeat", type=int, default=1, help="每个模式重复运行次数；封版真实样本建议设为 2。")
    parser.add_argument("--poll-interval", type=float, default=8.0)
    parser.add_argument("--timeout", type=float, default=360.0)
    parser.add_argument("--detail", choices=["light", "full"], default="full")
    parser.add_argument("--out-dir", default=str(Path("deliverables") / "image_edit_patrol"))
    args = parser.parse_args()

    tag = _now_tag()
    out_dir = Path(args.out_dir) / tag
    reference_image_url = args.reference_image_url or args.image_url
    selected_cases = _select_cases(args.cases)
    repeat = max(1, int(args.repeat or 1))

    base_url = str(args.base_url).rstrip("/")
    client = httpx.Client(base_url=base_url, headers=_headers(args.token), timeout=30.0)
    summary: dict[str, Any] = {
        "baseUrl": base_url,
        "tag": tag,
        "imageUrl": args.image_url,
        "referenceImageUrl": reference_image_url,
        "size": args.size,
        "quality": args.quality,
        "repeat": repeat,
        "cases": [],
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }

    try:
        for repeat_index in range(repeat):
            repeat_tag = f"{tag}-r{repeat_index + 1:02d}"
            for case in selected_cases:
                case_dir_name = case.key if repeat == 1 else f"{case.key}_{repeat_index + 1:02d}"
                case_dir = out_dir / case_dir_name
                payload = _build_payload(
                    case,
                    image_url=args.image_url,
                    reference_image_url=reference_image_url,
                    size=args.size,
                    quality=args.quality,
                    tag=repeat_tag,
                )
                payload.setdefault("metadata", {})["repeatIndex"] = repeat_index + 1
                _write_json(case_dir / "request.json", payload)

                submit_status, submit_data = _post_json(client, "/api/business/image-edit/runs", payload)
                _write_json(case_dir / "submit.response.json", {"statusCode": submit_status, "response": submit_data})

                final: dict[str, Any]
                poll_records: list[dict[str, Any]]
                if submit_status == 200 and isinstance(submit_data, dict) and submit_data.get("runId"):
                    final, poll_records = _poll_run(
                        client,
                        run_id=str(submit_data["runId"]),
                        interval_seconds=args.poll_interval,
                        timeout_seconds=args.timeout,
                        detail=args.detail,
                    )
                else:
                    final = {"status": "failed", "error": "提交失败，未进入轮询。", "submitResponse": submit_data}
                    poll_records = []
                _write_json(case_dir / "poll.records.json", poll_records)
                _write_json(case_dir / "final.response.json", final)
                case_summary = _case_result_summary(case, final, submit_status, submit_data)
                case_summary["repeatIndex"] = repeat_index + 1
                case_summary["caseDir"] = case_dir_name
                summary["cases"].append(case_summary)
    finally:
        client.close()

    summary["finishedAt"] = datetime.now(timezone.utc).isoformat()
    _write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    failed = [item for item in summary["cases"] if item.get("finalStatus") != "succeeded"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
