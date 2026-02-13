"""Backfill pending async ability logs (ComfyUI/KIE).

Usage:
  PYTHONPATH=backend python3 backend/scripts/backfill_async_ability_logs.py --apply
  PYTHONPATH=backend python3 backend/scripts/backfill_async_ability_logs.py --limit 200 --age-minutes 10 --apply
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import desc, or_, select

from app.core.db import get_session
from app.models.integration import AbilityInvocationLog, Executor
from app.services.ability_logs import ability_log_service
from app.services.ability_task_service import AbilityTaskService
from app.services.integration_test import integration_test_service


def _now_utc() -> datetime:
    return datetime.utcnow()


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().lower()


def _log_needs_assets(log: AbilityInvocationLog) -> bool:
    if log.status != "success":
        return False
    assets = log.result_assets or []
    if isinstance(assets, list) and assets:
        return False
    return True


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _extract_prompt_meta(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None, list[str] | None]:
    prompt_id = payload.get("promptId") or payload.get("taskId")
    base_url = payload.get("baseUrl")
    executor_id = payload.get("executorId") or payload.get("executor")
    output_node_ids = payload.get("outputNodeIds") or payload.get("output_node_ids")
    return (
        str(prompt_id).strip() if isinstance(prompt_id, str) else None,
        str(base_url).strip() if isinstance(base_url, str) else None,
        str(executor_id).strip() if isinstance(executor_id, str) else None,
        output_node_ids if isinstance(output_node_ids, list) else None,
    )


def _resolve_executor_base(executor_id: str | None, base_url: str | None) -> str | None:
    if base_url:
        return base_url
    if not executor_id:
        return None
    with get_session() as session:
        ex = session.get(Executor, executor_id)
        if not ex:
            return None
        cfg = ex.config or {}
        return (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip() or None


def _finalize_comfyui_log(log: AbilityInvocationLog, *, apply: bool) -> bool:
    payload = _as_dict(log.response_payload)
    prompt_id, base_url, executor_id, output_node_ids = _extract_prompt_meta(payload)
    base_url = _resolve_executor_base(executor_id, base_url)
    if not prompt_id or not base_url:
        return False

    try:
        import httpx
        from app.services.executors.base import ExecutionContext
        from app.services.executors.registry import registry
    except Exception:
        return False

    adapter = registry.get("comfyui")
    if adapter is None:
        return False

    try:
        history_url = f"{base_url.rstrip('/')}/history/{prompt_id}"
        resp = httpx.get(history_url, timeout=15)
        if resp.status_code != 200:
            return False
        data = resp.json()
        entry = data.get(prompt_id) if isinstance(data, dict) else None
        if not isinstance(entry, dict):
            return False
        output_nodes = None
        if isinstance(output_node_ids, list):
            output_nodes = {str(x) for x in output_node_ids if str(x).strip()}
        outputs = adapter._extract_outputs(entry, output_node_ids=output_nodes)  # type: ignore[attr-defined]
        hist = outputs.get("history") if isinstance(outputs, dict) else None
        status_dict = hist.get("status") if isinstance(hist, dict) else None
        status_str = str((status_dict or {}).get("status_str") or "").lower()
        if status_str == "error":
            if apply:
                ability_log_service.finish_failure(
                    log.id,
                    error_message="COMFYUI_ERROR",
                    response_payload=payload,
                    duration_ms=log.duration_ms,
                )
            return True
        if status_str != "success":
            return False
        images = outputs.get("images") if isinstance(outputs, dict) else None
        if not isinstance(images, list) or not images:
            return False
        ctx = ExecutionContext(
            task=SimpleNamespace(id=f"log-{log.id}", user_id=log.source or "system", assets=[]),
            workflow=SimpleNamespace(id="log_finalize", definition={}, extra_metadata={}),
            executor=SimpleNamespace(id=executor_id or "comfyui", base_url=base_url, config={}),
            payload={},
            api_key=None,
        )
        assets: list[dict[str, Any]] = []
        for img in images:
            if not isinstance(img, dict):
                continue
            source_url = img.get("url") or adapter._build_image_url(base_url.rstrip("/"), img)  # type: ignore[attr-defined]
            base64_data = img.get("base64")
            if source_url:
                asset = adapter._store_remote_asset(source_url, ctx, tag="comfyui")  # type: ignore[attr-defined]
            elif base64_data:
                asset = adapter._store_base64_asset(base64_data, ctx, tag="comfyui")  # type: ignore[attr-defined]
            else:
                asset = None
            if asset:
                assets.append(asset)
        if not assets:
            return False
        next_payload = dict(payload)
        next_payload["images"] = assets
        next_payload["assets"] = assets
        next_payload["status"] = "succeeded"
        next_payload["state"] = "success"
        if apply:
            ability_log_service.finish_success(
                log.id,
                response_payload=next_payload,
                duration_ms=log.duration_ms,
            )
        return True
    except Exception:
        return False


def _finalize_kie_log(log: AbilityInvocationLog, *, apply: bool) -> bool:
    payload = _as_dict(log.response_payload)
    task_id = payload.get("taskId")
    executor_id = payload.get("executorId") or payload.get("executor")
    if isinstance(task_id, dict):
        task_id = task_id.get("taskId")
    if not (isinstance(task_id, str) and task_id.strip()):
        return False
    if not (isinstance(executor_id, str) and executor_id.strip()):
        return False
    try:
        fetched = integration_test_service.fetch_kie_market_result(
            executor_id=executor_id.strip(),
            task_id=task_id.strip(),
            timeout=18.0,
            max_retries=1,
        )
    except Exception:
        return False

    state = str(fetched.get("state") or "").lower()
    urls = fetched.get("resultUrls") if isinstance(fetched.get("resultUrls"), list) else []
    assets = fetched.get("storedAssets") if isinstance(fetched.get("storedAssets"), list) else []
    if state == "success" and (urls or assets):
        if not assets and urls:
            assets = [{"url": u} for u in urls if isinstance(u, str) and u.strip()]
        next_payload = dict(payload)
        next_payload["images"] = assets
        next_payload["assets"] = assets
        next_payload["status"] = "succeeded"
        next_payload["state"] = state
        if apply:
            ability_log_service.finish_success(
                log.id,
                response_payload=next_payload,
                duration_ms=log.duration_ms,
            )
        return True
    if state == "fail":
        error_message = AbilityTaskService._extract_kie_error_message(fetched) or "KIE_TASK_FAILED"
        if apply:
            ability_log_service.finish_failure(
                log.id,
                error_message=error_message,
                response_payload=payload,
                duration_ms=log.duration_ms,
            )
        return True
    return False


def backfill(*, apply: bool, limit: int | None, age_minutes: int) -> None:
    cutoff = _now_utc() - timedelta(minutes=age_minutes)
    scanned = 0
    updated = 0
    marked_failed = 0

    with get_session() as session:
        stmt = (
            select(AbilityInvocationLog)
            .where(
            AbilityInvocationLog.ability_provider.in_(["comfyui", "kie"]),
            or_(
                AbilityInvocationLog.status.in_(["pending", "running", "queued"]),
                AbilityInvocationLog.status == "success",
            ),
            )
            .order_by(desc(AbilityInvocationLog.created_at))
        )
        if limit:
            stmt = stmt.limit(limit)
        logs = session.execute(stmt).scalars().all()

    for log in logs:
        scanned += 1
        status = _normalize_status(log.status)
        if log.created_at and log.created_at > cutoff:
            # Skip very recent logs to avoid racing with normal flows.
            continue

        # Only repair success-without-assets or pending/running.
        if status == "success" and not _log_needs_assets(log):
            continue

        provider = (log.ability_provider or "").lower()
        updated_flag = False
        if provider == "comfyui":
            updated_flag = _finalize_comfyui_log(log, apply=apply)
            if not updated_flag and status in {"pending", "running", "queued"}:
                payload = _as_dict(log.response_payload)
                prompt_id, base_url, executor_id, _ = _extract_prompt_meta(payload)
                base_url = _resolve_executor_base(executor_id, base_url)
                if not prompt_id or not base_url:
                    if apply:
                        ability_log_service.finish_failure(
                            log.id,
                            error_message="COMFYUI_PROMPT_ID_MISSING",
                            response_payload=payload,
                            duration_ms=log.duration_ms,
                        )
                    marked_failed += 1
                    continue
        elif provider == "kie":
            updated_flag = _finalize_kie_log(log, apply=apply)
            if not updated_flag and status in {"pending", "running", "queued"}:
                payload = _as_dict(log.response_payload)
                task_id = payload.get("taskId")
                executor_id = payload.get("executorId") or payload.get("executor")
                if not (isinstance(task_id, str) and task_id.strip() and isinstance(executor_id, str) and executor_id.strip()):
                    if apply:
                        ability_log_service.finish_failure(
                            log.id,
                            error_message="KIE_TASK_ID_MISSING",
                            response_payload=payload,
                            duration_ms=log.duration_ms,
                        )
                    marked_failed += 1
                    continue
        if updated_flag:
            updated += 1

    print(
        f"scanned={scanned} updated={updated} marked_failed={marked_failed} "
        f"age_minutes={age_minutes} apply={apply}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill async ability logs (ComfyUI/KIE).")
    parser.add_argument("--apply", action="store_true", help="Write updates to DB.")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows.")
    parser.add_argument("--age-minutes", type=int, default=5, help="Only process logs older than this.")
    args = parser.parse_args()
    backfill(apply=bool(args.apply), limit=args.limit, age_minutes=args.age_minutes)


if __name__ == "__main__":
    main()
