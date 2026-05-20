#!/usr/bin/env python3
"""Export business run samples for AI/ComfyUI workflow review."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.db import get_session  # noqa: E402
from app.models.integration import BusinessRun  # noqa: E402
from app.services.business_runs import get_business_run_service  # noqa: E402


SECRET_KEY_PATTERN = re.compile(r"(authorization|api[_-]?key|token|secret|password|credential)", re.IGNORECASE)
URL_KEY_PATTERN = re.compile(r"(image|url|oss|asset|result|input)", re.IGNORECASE)
DEFAULT_OUTPUT_ROOT = Path("deliverables") / "business_sample_packs"


def _utc_now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_name(value: str, fallback: str = "sample") -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    text = text.strip("._-")
    return text[:120] or fallback


def _parse_datetime(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        parsed = datetime.strptime(raw, "%Y-%m-%d")
        return parsed + timedelta(days=1) if end_of_day else parsed
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if SECRET_KEY_PATTERN.search(str(key)):
                cleaned[str(key)] = "[redacted]"
            else:
                cleaned[str(key)] = _redact(item)
        return cleaned
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and value.lower().startswith(("bearer ", "sk-", "ak-")):
        return "[redacted]"
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_redact(_json_safe(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_url_values(value: Any) -> list[str]:
    urls: list[str] = []

    def walk(item: Any, *, key_hint: str = "") -> None:
        if isinstance(item, str):
            text = item.strip()
            if text.startswith(("http://", "https://")):
                urls.append(text)
            return
        if isinstance(item, list):
            for child in item:
                walk(child, key_hint=key_hint)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                child_key = str(key)
                if URL_KEY_PATTERN.search(child_key) or URL_KEY_PATTERN.search(key_hint):
                    walk(child, key_hint=child_key)
                elif isinstance(child, (dict, list)):
                    walk(child, key_hint=child_key)

    walk(value)
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _extract_input_urls(run: dict[str, Any]) -> list[str]:
    payload = run.get("request_payload") or run.get("requestPayload") or {}
    candidates = []
    if isinstance(payload, dict):
        for key in ("imageUrl", "image_url", "url", "Url", "URL", "inputUrl", "input_url"):
            if key in payload:
                candidates.append(payload.get(key))
        inputs = payload.get("inputs")
        if isinstance(inputs, dict):
            candidates.append(inputs)
    return _extract_url_values(candidates)


def _extract_output_urls(run: dict[str, Any]) -> list[str]:
    candidates = [
        run.get("image_urls"),
        run.get("imageUrls"),
        run.get("video_urls"),
        run.get("videoUrls"),
        run.get("result_payload"),
        run.get("resultPayload"),
    ]
    flow = run.get("flow_summary") or run.get("flowSummary")
    if isinstance(flow, dict):
        candidates.append(flow.get("output"))
    steps = run.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                candidates.append(step.get("result_summary") or step.get("resultSummary"))
                candidates.append(step.get("execution_evidence") or step.get("executionEvidence"))
    return _extract_url_values(candidates)


def _extract_vl_payloads(run: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    steps = run.get("steps")
    if not isinstance(steps, list):
        return payloads
    for step in steps:
        if not isinstance(step, dict):
            continue
        role = str(step.get("role") or "").lower()
        step_type = str(step.get("step_type") or step.get("stepType") or "").lower()
        ability_name = str(step.get("ability_name") or step.get("abilityName") or step.get("display_name") or "")
        result_summary = step.get("result_summary") or step.get("resultSummary")
        if not isinstance(result_summary, dict):
            continue
        if "vl" in role or "vl" in step_type or "vl" in ability_name.lower() or result_summary.get("vlCard"):
            payloads.append(
                {
                    "stepId": step.get("step_id") or step.get("stepId") or step.get("id"),
                    "displayName": step.get("display_name") or step.get("displayName") or ability_name,
                    "status": step.get("status"),
                    "resultSummary": result_summary,
                }
            )
    return payloads


def _extract_executor_ids(run: dict[str, Any]) -> list[str]:
    values: list[str] = []
    flow = run.get("flow_summary") or run.get("flowSummary")
    if isinstance(flow, dict):
        executor = flow.get("executor")
        if isinstance(executor, dict) and executor.get("id"):
            values.append(str(executor.get("id")))
    steps = run.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            for key in ("executor_id", "executorId"):
                if step.get(key):
                    values.append(str(step.get(key)))
            evidence = step.get("execution_evidence") or step.get("executionEvidence")
            if isinstance(evidence, dict) and evidence.get("executorId"):
                values.append(str(evidence.get("executorId")))
    return sorted({item for item in values if item})


def _matches_executor(run: dict[str, Any], executor_filter: str | None) -> bool:
    expected = str(executor_filter or "").strip()
    if not expected:
        return True
    return expected in _extract_executor_ids(run)


def _extension_from_url(url: str, content_type: str | None = None) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{2,5}", suffix):
        return suffix
    content_type = str(content_type or "").lower()
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    if "mp4" in content_type:
        return ".mp4"
    return ".jpg"


def _download_asset(client: httpx.Client, url: str, target_without_suffix: Path) -> str:
    response = client.get(url)
    response.raise_for_status()
    suffix = _extension_from_url(url, response.headers.get("content-type"))
    target = target_without_suffix.with_suffix(suffix)
    target.write_bytes(response.content)
    return target.name


def _query_candidate_run_ids(args: argparse.Namespace) -> list[str]:
    date_from = _parse_datetime(args.date_from)
    date_to = _parse_datetime(args.date_to, end_of_day=True)
    with get_session() as session:
        stmt = select(BusinessRun.id).order_by(BusinessRun.created_at.desc())
        filters = []
        if args.business_key:
            filters.append(BusinessRun.business_key == args.business_key)
        if args.version:
            filters.append(BusinessRun.version == args.version)
        if args.business_version_id:
            filters.append(BusinessRun.business_version_id == args.business_version_id)
        if args.status:
            filters.append(BusinessRun.status == args.status)
        if args.source:
            filters.append(BusinessRun.source == args.source)
        if date_from:
            filters.append(BusinessRun.created_at >= date_from)
        if date_to:
            filters.append(BusinessRun.created_at < date_to)
        if filters:
            stmt = stmt.where(*filters)
        return [str(item) for item in session.execute(stmt.limit(args.scan_limit)).scalars().all()]


def _summary_row(run: dict[str, Any]) -> dict[str, Any]:
    flow = run.get("flow_summary") or run.get("flowSummary") or {}
    executor = flow.get("executor") if isinstance(flow, dict) else {}
    output = flow.get("output") if isinstance(flow, dict) else {}
    vl_payloads = _extract_vl_payloads(run)
    input_urls = _extract_input_urls(run)
    output_urls = _extract_output_urls(run)
    return {
        "run_id": run.get("id"),
        "business_key": run.get("business_key") or run.get("businessKey"),
        "version": run.get("version"),
        "business_version_id": run.get("business_version_id") or run.get("businessVersionId"),
        "status": run.get("status"),
        "source": run.get("source"),
        "created_at": run.get("created_at") or run.get("createdAt"),
        "finished_at": run.get("finished_at") or run.get("finishedAt"),
        "duration_ms": run.get("duration_ms") or run.get("durationMs"),
        "executor_id": executor.get("id") if isinstance(executor, dict) else "",
        "executor_name": executor.get("name") if isinstance(executor, dict) else "",
        "image_count": output.get("imageCount") if isinstance(output, dict) else len(run.get("image_urls") or []),
        "video_count": output.get("videoCount") if isinstance(output, dict) else len(run.get("video_urls") or []),
        "text_count": output.get("textCount") if isinstance(output, dict) else len(run.get("texts") or []),
        "input_urls": " | ".join(input_urls),
        "output_urls": " | ".join(output_urls),
        "vl_step_count": len(vl_payloads),
        "error": run.get("error_message") or run.get("error"),
    }


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_id",
        "business_key",
        "version",
        "business_version_id",
        "status",
        "source",
        "created_at",
        "finished_at",
        "duration_ms",
        "executor_id",
        "executor_name",
        "image_count",
        "video_count",
        "text_count",
        "input_urls",
        "output_urls",
        "vl_step_count",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _write_readme(path: Path, *, args: argparse.Namespace, exported_count: int, zip_name: str) -> None:
    lines = [
        "# 业务样本导出包",
        "",
        "用途：给 AI / ComfyUI / 业务测试同学复盘同一批业务运行的原图、结果图、VL 内容和过程信息。",
        "",
        "## 筛选条件",
        "",
        f"- business_key: `{args.business_key or 'all'}`",
        f"- version: `{args.version or 'all'}`",
        f"- business_version_id: `{args.business_version_id or 'all'}`",
        f"- status: `{args.status or 'all'}`",
        f"- executor_id: `{args.executor_id or 'all'}`",
        f"- date_from: `{args.date_from or '-'}`",
        f"- date_to: `{args.date_to or '-'}`",
        f"- exported_count: `{exported_count}`",
        "",
        "## 文件说明",
        "",
        "- `summary.csv`：人工快速查看的总表。",
        "- `manifest.json`：本次导出条件、运行 ID 和文件索引。",
        "- `runs/<runId>/run.json`：单条业务运行完整详情，敏感字段已脱敏。",
        "- `runs/<runId>/process.json`：业务链路、步骤、执行节点和回填证据。",
        "- `runs/<runId>/vl.json`：VL 分析/控制卡摘要。",
        "- `runs/<runId>/urls.json`：原图和结果图 URL 清单。",
        "- `runs/<runId>/assets/`：若开启下载，会保存原图和结果图文件。",
        "",
        f"压缩包：`{zip_name}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def export_pack(args: argparse.Namespace) -> Path:
    service = get_business_run_service()
    candidate_ids = _query_candidate_run_ids(args)
    slug_parts = [
        "business_sample_pack",
        args.business_key or "all",
        args.version or args.business_version_id or "all_versions",
        _utc_now_slug(),
    ]
    output_root = Path(args.output_root or DEFAULT_OUTPUT_ROOT)
    pack_dir = output_root / _safe_name("_".join(slug_parts))
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    pack_dir.mkdir(parents=True, exist_ok=True)

    exported_runs: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []
    downloaded_errors: list[dict[str, Any]] = []
    client = httpx.Client(timeout=httpx.Timeout(args.download_timeout, connect=10.0), follow_redirects=True)
    try:
        for run_id in candidate_ids:
            if len(exported_runs) >= args.limit:
                break
            try:
                run = service.get_run(run_id=run_id, user=None)
            except Exception as exc:
                downloaded_errors.append({"runId": run_id, "stage": "load_run", "error": str(exc)})
                continue
            if not isinstance(run, dict) or not _matches_executor(run, args.executor_id):
                continue

            run_dir = pack_dir / "runs" / _safe_name(str(run.get("id") or run_id), fallback=run_id)
            asset_dir = run_dir / "assets"
            run_dir.mkdir(parents=True, exist_ok=True)
            if args.download_assets:
                asset_dir.mkdir(parents=True, exist_ok=True)

            input_urls = _extract_input_urls(run)
            output_urls = _extract_output_urls(run)
            vl_payloads = _extract_vl_payloads(run)
            process_payload = {
                "flowSummary": run.get("flow_summary") or run.get("flowSummary"),
                "steps": run.get("steps") or [],
                "executorIds": _extract_executor_ids(run),
            }

            _write_json(run_dir / "run.json", run)
            _write_json(run_dir / "process.json", process_payload)
            _write_json(run_dir / "vl.json", {"items": vl_payloads})
            _write_json(run_dir / "urls.json", {"inputUrls": input_urls, "outputUrls": output_urls})

            downloaded: list[dict[str, str]] = []
            if args.download_assets:
                for kind, urls in (("input", input_urls), ("output", output_urls)):
                    for index, url in enumerate(urls[: args.max_assets_per_kind], start=1):
                        try:
                            filename = _download_asset(client, url, asset_dir / f"{kind}_{index:02d}")
                            downloaded.append({"kind": kind, "url": url, "file": f"assets/{filename}"})
                        except Exception as exc:
                            downloaded_errors.append(
                                {"runId": str(run.get("id") or run_id), "stage": f"download_{kind}", "url": url, "error": str(exc)}
                            )
                _write_json(run_dir / "assets.json", downloaded)

            row = _summary_row(run)
            exported_runs.append(row)
            manifest_items.append(
                {
                    "runId": row["run_id"],
                    "businessKey": row["business_key"],
                    "version": row["version"],
                    "status": row["status"],
                    "executorId": row["executor_id"],
                    "inputCount": len(input_urls),
                    "outputCount": len(output_urls),
                    "vlStepCount": len(vl_payloads),
                    "path": str(run_dir.relative_to(pack_dir)),
                }
            )
    finally:
        client.close()

    _write_summary_csv(pack_dir / "summary.csv", exported_runs)
    manifest = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "businessKey": args.business_key,
            "version": args.version,
            "businessVersionId": args.business_version_id,
            "status": args.status,
            "executorId": args.executor_id,
            "source": args.source,
            "dateFrom": args.date_from,
            "dateTo": args.date_to,
            "limit": args.limit,
            "scanLimit": args.scan_limit,
        },
        "downloadAssets": args.download_assets,
        "items": manifest_items,
        "errors": downloaded_errors,
    }
    _write_json(pack_dir / "manifest.json", manifest)
    zip_path = pack_dir.with_suffix(".zip")
    _write_readme(pack_dir / "README.md", args=args, exported_count=len(exported_runs), zip_name=zip_path.name)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(pack_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(pack_dir.parent))
    return zip_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export business run samples into a zip package.")
    parser.add_argument("--business-key", default="", help="Business key, for example fission/outpaint/pattern_extract.")
    parser.add_argument("--version", default="", help="Business version label, for example comfyui-vl-control-v2.")
    parser.add_argument("--business-version-id", default="", help="Exact business_capabilities.id filter.")
    parser.add_argument("--status", default="succeeded", help="Run status filter. Empty string means all statuses.")
    parser.add_argument("--source", default="", help="Optional source filter, for example eval/coze/business-api.")
    parser.add_argument("--executor-id", default="", help="Filter by actual executor id in flowSummary/steps.")
    parser.add_argument("--date-from", default="", help="Inclusive start date or datetime, for example 2026-05-13.")
    parser.add_argument("--date-to", default="", help="Exclusive end datetime; date values include the whole day.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum exported runs.")
    parser.add_argument("--scan-limit", type=int, default=500, help="Maximum candidate DB rows to scan before executor filtering.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory for the extracted package and zip.")
    parser.add_argument("--no-download-assets", dest="download_assets", action="store_false", help="Only export URLs, do not download images/videos.")
    parser.add_argument("--download-timeout", type=float, default=60.0, help="Per-asset download timeout in seconds.")
    parser.add_argument("--max-assets-per-kind", type=int, default=6, help="Max downloaded input/output assets per run.")
    parser.set_defaults(download_assets=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.limit = max(1, min(int(args.limit), 5000))
    args.scan_limit = max(args.limit, min(int(args.scan_limit), 10000))
    args.max_assets_per_kind = max(1, min(int(args.max_assets_per_kind), 50))
    try:
        zip_path = export_pack(args)
    except Exception as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        return 2
    print(f"sample pack: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
