#!/usr/bin/env python3
"""Audit cleanup candidates across repo files, database records and OSS.

The script is intentionally read-only. It produces a report that separates
safe local artifacts from database/OSS records that need review before delete.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


SAFE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SAFE_TOP_LEVEL_DIRS = {".playwright-cli", ".playwright-mcp"}
SAFE_FILE_SUFFIXES = {".log", ".tmp", ".pyc", ".pyo"}
SAFE_FILE_NAMES = {".DS_Store"}
REBUILDABLE_DIRS = {
    "podi-admin-web/dist",
    "podi-eval-web/dist",
}
HEAVY_DEPENDENCY_DIR_NAMES = {"node_modules", ".venv"}


@dataclass
class AuditItem:
    area: str
    item_type: str
    risk: str
    action: str
    path_or_id: str
    count: int | None = None
    size_bytes: int | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "type": self.item_type,
            "risk": self.risk,
            "suggested_action": self.action,
            "path_or_id": self.path_or_id,
            "count": self.count,
            "size_bytes": self.size_bytes,
            "detail": self.detail,
        }


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys or ["empty"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                    for key, value in row.items()
                }
            )


def _directory_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for file_name in files:
            try:
                total += (Path(root) / file_name).stat().st_size
            except OSError:
                continue
    return total


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def audit_repo_files(root: Path) -> list[AuditItem]:
    candidates: list[AuditItem] = []
    root = root.resolve()

    for rel in sorted(REBUILDABLE_DIRS):
        path = root / rel
        if path.exists() and path.is_dir():
            candidates.append(
                AuditItem(
                    area="repo",
                    item_type="build-artifact",
                    risk="low",
                    action="safe-delete-local",
                    path_or_id=rel,
                    size_bytes=_directory_size(path),
                    detail="前端构建产物，可重新 build 生成。",
                )
            )

    for rel in sorted(SAFE_TOP_LEVEL_DIRS):
        path = root / rel
        if path.exists() and path.is_dir():
            candidates.append(
                AuditItem(
                    area="repo",
                    item_type="tool-log-dir",
                    risk="low",
                    action="safe-delete-local",
                    path_or_id=rel,
                    size_bytes=_directory_size(path),
                    detail="浏览器/自动化调试日志目录。",
                )
            )

    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        rel_current = _relative(current, root)
        dirs[:] = [
            item
            for item in dirs
            if item not in HEAVY_DEPENDENCY_DIR_NAMES
            and item != ".git"
            and _relative(current / item, root) not in REBUILDABLE_DIRS
            and _relative(current / item, root) not in SAFE_TOP_LEVEL_DIRS
        ]

        for dir_name in list(dirs):
            if dir_name in SAFE_DIR_NAMES:
                path = current / dir_name
                candidates.append(
                    AuditItem(
                        area="repo",
                        item_type="cache-dir",
                        risk="low",
                        action="safe-delete-local",
                        path_or_id=_relative(path, root),
                        size_bytes=_directory_size(path),
                        detail="运行缓存目录。",
                    )
                )
                dirs.remove(dir_name)

        for file_name in files:
            path = current / file_name
            suffix = path.suffix
            if file_name in SAFE_FILE_NAMES or suffix in SAFE_FILE_SUFFIXES:
                candidates.append(
                    AuditItem(
                        area="repo",
                        item_type="temp-file",
                        risk="low",
                        action="safe-delete-local",
                        path_or_id=_relative(path, root),
                        size_bytes=_file_size(path),
                        detail="本地临时文件或日志。",
                    )
                )
            elif _file_size(path) > 10 * 1024 * 1024 and rel_current != ".git":
                candidates.append(
                    AuditItem(
                        area="repo",
                        item_type="large-file",
                        risk="medium",
                        action="review-before-delete",
                        path_or_id=_relative(path, root),
                        size_bytes=_file_size(path),
                        detail="超过 10MB 的大文件，需确认是否为交付产物或应移出仓库。",
                    )
                )

    return candidates


def _query_rows(session: Any, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from sqlalchemy import text

    result = session.execute(text(sql), params or {})
    return [{key: _json_safe(value) for key, value in row._mapping.items()} for row in result]


def audit_database(*, stale_hours: int, retention_days: int, limit: int) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    from app.core.db import get_session

    cutoff = datetime.utcnow() - timedelta(hours=stale_hours)
    retention_cutoff = datetime.utcnow() - timedelta(days=retention_days)
    errors: list[str] = []
    sections: dict[str, list[dict[str, Any]]] = {}
    queries: dict[str, tuple[str, dict[str, Any]]] = {
        "business_stale_nonterminal_runs": (
            """
            SELECT id, business_key, business_version_id, version, status, source,
                   ability_task_id, ability_log_id, LEFT(COALESCE(error_message, ''), 500) AS error_message,
                   created_at, updated_at, started_at, finished_at
            FROM business_runs
            WHERE status IN ('queued', 'running', 'submitted', 'processing')
              AND updated_at < :cutoff
            ORDER BY updated_at ASC
            LIMIT :limit
            """,
            {"cutoff": cutoff, "limit": limit},
        ),
        "business_succeeded_without_output": (
            """
            SELECT id, business_key, business_version_id, version, status, source,
                   ability_task_id, ability_log_id, created_at, updated_at
            FROM business_runs
            WHERE status='succeeded'
              AND created_at < :retention_cutoff
              AND COALESCE(JSON_LENGTH(image_urls), 0)=0
              AND COALESCE(JSON_LENGTH(video_urls), 0)=0
              AND COALESCE(JSON_LENGTH(texts), 0)=0
            ORDER BY created_at ASC
            LIMIT :limit
            """,
            {"retention_cutoff": retention_cutoff, "limit": limit},
        ),
        "business_orphan_steps": (
            """
            SELECT s.id, s.run_id, s.step_order, s.status, s.ability_id, s.ability_task_id,
                   s.created_at, s.updated_at
            FROM business_run_steps s
            LEFT JOIN business_runs r ON r.id = s.run_id
            WHERE r.id IS NULL
            ORDER BY s.created_at ASC
            LIMIT :limit
            """,
            {"limit": limit},
        ),
        "ability_stale_nonterminal_logs": (
            """
            SELECT id, ability_id, ability_name, ability_provider, capability_key, source, task_id,
                   executor_id, executor_name, status, LEFT(COALESCE(error_message, ''), 500) AS error_message,
                   created_at, updated_at
            FROM ability_invocation_logs
            WHERE status IN ('pending', 'running', 'queued', 'submitted')
              AND updated_at < :cutoff
            ORDER BY updated_at ASC
            LIMIT :limit
            """,
            {"cutoff": cutoff, "limit": limit},
        ),
        "ability_stale_nonterminal_tasks": (
            """
            SELECT id, ability_id, ability_name, ability_provider, capability_key, log_id, status,
                   LEFT(COALESCE(error_message, ''), 500) AS error_message, created_at, updated_at, started_at, finished_at
            FROM ability_tasks
            WHERE status IN ('queued', 'running', 'submitted', 'processing')
              AND updated_at < :cutoff
            ORDER BY updated_at ASC
            LIMIT :limit
            """,
            {"cutoff": cutoff, "limit": limit},
        ),
        "eval_stale_nonterminal_runs": (
            """
            SELECT id, workflow_version_id, dataset_item_id, status, podi_task_id,
                   LEFT(COALESCE(error_message, ''), 500) AS error_message,
                   created_at, updated_at
            FROM eval_run
            WHERE status IN ('queued', 'running', 'submitted', 'processing')
              AND updated_at < :cutoff
            ORDER BY updated_at ASC
            LIMIT :limit
            """,
            {"cutoff": cutoff, "limit": limit},
        ),
        "eval_succeeded_without_output": (
            """
            SELECT id, workflow_version_id, status, podi_task_id, created_at, updated_at
            FROM eval_run
            WHERE status='success'
              AND created_at < :retention_cutoff
              AND COALESCE(JSON_LENGTH(result_image_urls_json), 0)=0
            ORDER BY created_at ASC
            LIMIT :limit
            """,
            {"retention_cutoff": retention_cutoff, "limit": limit},
        ),
        "eval_empty_draft_batches": (
            """
            SELECT b.id, b.workflow_version_id, b.status, b.planned_image_count,
                   b.uploaded_count, b.upload_failed_count, b.created_at, b.updated_at
            FROM eval_batch_session b
            LEFT JOIN eval_batch_asset a ON a.batch_session_id = b.id
            LEFT JOIN eval_batch_run_item i ON i.batch_session_id = b.id
            WHERE b.status IN ('draft', 'uploading')
              AND b.updated_at < :cutoff
            GROUP BY b.id
            HAVING COUNT(a.id)=0 AND COUNT(i.id)=0
            ORDER BY b.updated_at ASC
            LIMIT :limit
            """,
            {"cutoff": cutoff, "limit": limit},
        ),
        "expired_active_api_keys": (
            """
            SELECT id, provider, name, status, daily_quota, usage_count, expire_at, created_at, updated_at
            FROM api_keys
            WHERE status='active' AND expire_at IS NOT NULL AND expire_at < UTC_TIMESTAMP()
            ORDER BY expire_at ASC
            LIMIT :limit
            """,
            {"limit": limit},
        ),
    }
    with get_session() as session:
        for name, (sql, params) in queries.items():
            try:
                sections[name] = _query_rows(session, sql, params)
            except Exception as exc:  # noqa: BLE001 - audit should continue across partial schema drift.
                sections[name] = []
                errors.append(f"{name}: {exc}")
    return sections, errors


def _extract_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("http://", "https://")):
            urls.append(text)
    elif isinstance(value, list):
        for item in value:
            urls.extend(_extract_urls(item))
    elif isinstance(value, dict):
        for item in value.values():
            urls.extend(_extract_urls(item))
    return urls


def _object_key_from_url(url: str, *, known_domains: list[str], root_prefix: str | None) -> str | None:
    parsed = urlparse(str(url or "").strip())
    if not parsed.netloc:
        return None
    netloc = parsed.netloc.lower()
    if known_domains and not any(netloc == domain or netloc.endswith(f".{domain}") for domain in known_domains):
        return None
    path = unquote(parsed.path.lstrip("/"))
    if not path:
        return None
    prefix = str(root_prefix or "").strip("/")
    if prefix and not path.startswith(f"{prefix}/"):
        return None
    return path


def collect_referenced_oss_keys(*, reference_scan_limit: int) -> tuple[set[str], list[str]]:
    from app.core.config import get_settings
    from app.core.db import get_session

    settings = get_settings()
    domains = []
    for value in (settings.oss_public_domain, settings.download_domain, f"{settings.oss_bucket}.{settings.oss_region}.aliyuncs.com"):
        parsed = urlparse(str(value or ""))
        domain = parsed.netloc or str(value or "").replace("https://", "").replace("http://", "").strip("/")
        if domain:
            domains.append(domain.lower())

    keys: set[str] = set()
    errors: list[str] = []
    with get_session() as session:
        scalar_queries = {
            "task_assets": "SELECT object_key FROM task_assets WHERE object_key IS NOT NULL LIMIT :limit",
            "eval_batch_asset": "SELECT object_key FROM eval_batch_asset WHERE object_key IS NOT NULL LIMIT :limit",
        }
        for name, sql in scalar_queries.items():
            try:
                for row in _query_rows(session, sql, {"limit": reference_scan_limit}):
                    if row.get("object_key"):
                        keys.add(str(row["object_key"]).lstrip("/"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")

        json_queries = {
            "business_runs": """
                SELECT r.image_urls, r.video_urls, r.request_payload, r.result_payload
                FROM (
                    SELECT id
                    FROM business_runs
                    ORDER BY created_at DESC
                    LIMIT :limit
                ) recent
                JOIN business_runs r ON r.id = recent.id
            """,
            "eval_run": """
                SELECT r.input_oss_urls_json, r.result_image_urls_json, r.result_output_json
                FROM (
                    SELECT id
                    FROM eval_run
                    ORDER BY created_at DESC
                    LIMIT :limit
                ) recent
                JOIN eval_run r ON r.id = recent.id
            """,
            "ability_invocation_logs": """
                SELECT l.stored_url, l.response_payload, l.result_assets
                FROM (
                    SELECT id
                    FROM ability_invocation_logs
                    ORDER BY created_at DESC
                    LIMIT :limit
                ) recent
                JOIN ability_invocation_logs l ON l.id = recent.id
            """,
        }
        for name, sql in json_queries.items():
            try:
                for row in _query_rows(session, sql, {"limit": reference_scan_limit}):
                    for url in _extract_urls(row):
                        key = _object_key_from_url(url, known_domains=domains, root_prefix=settings.oss_root_prefix)
                        if key:
                            keys.add(key)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
    return keys, errors


def audit_oss_candidates(
    *,
    prefix: str | None,
    retention_days: int,
    max_objects: int,
    reference_scan_limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    import oss2
    from app.core.config import get_settings

    settings = get_settings()
    referenced_keys, errors = collect_referenced_oss_keys(reference_scan_limit=reference_scan_limit)
    if not (settings.oss_access_key and settings.oss_secret_key):
        errors.append("OSS_ACCESS_KEY / OSS_SECRET_KEY 未配置，跳过 OSS 对象列举。")
        return [], errors

    endpoint = settings.oss_internal_endpoint or settings.oss_endpoint
    if not endpoint.startswith("http"):
        endpoint = f"https://{endpoint}"
    auth = oss2.Auth(settings.oss_access_key, settings.oss_secret_key)
    bucket = oss2.Bucket(auth, endpoint, settings.oss_bucket, connect_timeout=max(5, int(settings.oss_connect_timeout or 30)))

    effective_prefix = str(prefix if prefix is not None else settings.oss_root_prefix or "").strip("/")
    if effective_prefix:
        effective_prefix = f"{effective_prefix}/"
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=retention_days)).timestamp())
    candidates: list[dict[str, Any]] = []
    inspected = 0
    try:
        for obj in oss2.ObjectIteratorV2(bucket, prefix=effective_prefix):
            inspected += 1
            if inspected > max_objects:
                break
            key = str(obj.key)
            last_modified = int(getattr(obj, "last_modified", 0) or 0)
            if key in referenced_keys:
                continue
            if last_modified and last_modified > cutoff_ts:
                continue
            candidates.append(
                {
                    "object_key": key,
                    "size_bytes": int(getattr(obj, "size", 0) or 0),
                    "last_modified": datetime.fromtimestamp(last_modified, tz=timezone.utc).isoformat()
                    if last_modified
                    else None,
                    "reason": "未在主要数据库引用中发现，且超过保留窗口。",
                }
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"oss_list: {exc}")
    return candidates, errors


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _oss_prefix_group(object_key: str, depth: int = 2) -> str:
    parts = [part for part in str(object_key or "").split("/") if part]
    if not parts:
        return "(empty)"
    return "/".join(parts[: max(1, depth)])


def summarize_oss_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidates:
        object_key = str(item.get("object_key") or "")
        last_modified = _parse_iso_datetime(item.get("last_modified"))
        month = last_modified.strftime("%Y-%m") if last_modified else "unknown"
        group_key = (_oss_prefix_group(object_key), month)
        summary = grouped.setdefault(
            group_key,
            {
                "prefix_group": group_key[0],
                "month": group_key[1],
                "count": 0,
                "size_bytes": 0,
                "earliest_last_modified": None,
                "latest_last_modified": None,
                "sample_keys": [],
            },
        )
        summary["count"] += 1
        summary["size_bytes"] += int(item.get("size_bytes") or 0)
        if last_modified:
            iso_value = last_modified.isoformat()
            if summary["earliest_last_modified"] is None or iso_value < summary["earliest_last_modified"]:
                summary["earliest_last_modified"] = iso_value
            if summary["latest_last_modified"] is None or iso_value > summary["latest_last_modified"]:
                summary["latest_last_modified"] = iso_value
        if len(summary["sample_keys"]) < 5 and object_key:
            summary["sample_keys"].append(object_key)
    return sorted(grouped.values(), key=lambda row: (int(row["size_bytes"]), int(row["count"])), reverse=True)


def build_oss_deletion_review_plan(
    candidates: list[dict[str, Any]],
    *,
    batch_size: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    safe_batch_size = max(1, int(batch_size or 100))
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            _oss_prefix_group(str(item.get("object_key") or "")),
            str(item.get("last_modified") or ""),
            str(item.get("object_key") or ""),
        ),
    )
    for index, item in enumerate(sorted_candidates):
        object_key = str(item.get("object_key") or "")
        last_modified = _parse_iso_datetime(item.get("last_modified"))
        rows.append(
            {
                "proposed_batch": index // safe_batch_size + 1,
                "object_key": object_key,
                "prefix_group": _oss_prefix_group(object_key),
                "month": last_modified.strftime("%Y-%m") if last_modified else "unknown",
                "size_bytes": int(item.get("size_bytes") or 0),
                "last_modified": item.get("last_modified"),
                "decision": "review_required",
                "delete_allowed": "no",
                "reason": item.get("reason") or "未在主要数据库引用中发现，且超过保留窗口。",
            }
        )
    return rows


def _summarize_db_sections(sections: dict[str, list[dict[str, Any]]]) -> list[AuditItem]:
    items: list[AuditItem] = []
    for name, rows in sections.items():
        if not rows:
            continue
        risk = "medium"
        action = "review-before-fix-or-archive"
        if "orphan" in name or "empty_draft" in name:
            risk = "low"
            action = "can-archive-after-backup"
        items.append(
            AuditItem(
                area="database",
                item_type=name,
                risk=risk,
                action=action,
                path_or_id=name,
                count=len(rows),
                detail="详见 raw/database.json；默认不建议物理删除，优先标记、归档或修正状态。",
            )
        )
    return items


def _build_summary(
    *,
    generated_at: datetime,
    items: list[AuditItem],
    db_errors: list[str],
    oss_candidates: list[dict[str, Any]],
    oss_groups: list[dict[str, Any]],
    oss_errors: list[str],
    output_dir: Path,
) -> str:
    repo_low = [item for item in items if item.area == "repo" and item.risk == "low"]
    repo_medium = [item for item in items if item.area == "repo" and item.risk != "low"]
    db_items = [item for item in items if item.area == "database"]
    total_repo_size = sum(item.size_bytes or 0 for item in repo_low)
    lines = [
        "# 清理审计报告",
        "",
        f"- 生成时间：{generated_at.isoformat()}",
        f"- 输出目录：`{output_dir}`",
        f"- 本地安全可删产物：{len(repo_low)} 项，约 {round(total_repo_size / 1024 / 1024, 2)} MB",
        f"- 本地需复核大文件：{len(repo_medium)} 项",
        f"- 数据库需复核分组：{len(db_items)} 类",
        f"- OSS 候选对象：{len(oss_candidates)} 个",
        "",
        "## 处理原则",
        "",
        "- 本报告只读，不执行删除。",
        "- 本地缓存/日志/构建产物可直接删除；`node_modules`、`.venv` 不默认删除。",
        "- 数据库默认不物理删除，优先归档、标记失效或修正状态；删除前必须备份。",
        "- OSS 只能删除“数据库无引用 + 超过保留窗口 + 非交付目录”的对象。",
        "",
        "## 本地安全可删产物 Top 20",
        "",
        "| 类型 | 路径 | 大小(MB) |",
        "| --- | --- | ---: |",
    ]
    for item in sorted(repo_low, key=lambda row: row.size_bytes or 0, reverse=True)[:20]:
        lines.append(f"| {item.item_type} | `{item.path_or_id}` | {round((item.size_bytes or 0) / 1024 / 1024, 2)} |")
    if not repo_low:
        lines.append("| - | 无 | 0 |")
    lines.extend(["", "## 数据库需复核", "", "| 类别 | 数量 | 建议 |", "| --- | ---: | --- |"])
    for item in db_items:
        lines.append(f"| `{item.item_type}` | {item.count or 0} | {item.action} |")
    if not db_items:
        lines.append("| - | 0 | 暂无 |")
    if db_errors:
        lines.extend(["", "## 数据库审计错误", ""])
        lines.extend([f"- {error}" for error in db_errors])
    if oss_errors:
        lines.extend(["", "## OSS 审计提示", ""])
        lines.extend([f"- {error}" for error in oss_errors])
    lines.extend(
        [
            "",
            "## OSS 候选分组 Top 20",
            "",
            "| 前缀分组 | 月份 | 数量 | 大小(MB) | 示例 |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for group in oss_groups[:20]:
        samples = ", ".join(f"`{key}`" for key in group.get("sample_keys", [])[:2]) or "-"
        lines.append(
            "| {prefix} | {month} | {count} | {size} | {samples} |".format(
                prefix=group.get("prefix_group") or "-",
                month=group.get("month") or "-",
                count=group.get("count") or 0,
                size=round(int(group.get("size_bytes") or 0) / 1024 / 1024, 2),
                samples=samples,
            )
        )
    if not oss_groups:
        lines.append("| - | - | 0 | 0 | 无 |")
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            "- `cleanup_candidates.csv`：所有候选项汇总",
            "- `raw/repo_candidates.json`：本地文件候选",
            "- `raw/database.json`：数据库候选明细",
            "- `raw/oss_candidates.json`：OSS 候选明细",
            "- `raw/oss_candidate_groups.json`：OSS 候选分组汇总",
            "- `oss_delete_review_manifest.csv`：OSS 小批量删除复核清单，默认不允许直接删除",
        ]
    )
    return "\n".join(lines) + "\n"


def run_audit(args: argparse.Namespace) -> Path:
    generated_at = datetime.now(timezone.utc)
    output_dir = Path(args.output_dir or PROJECT_ROOT / "reports" / "cleanup-audit" / generated_at.strftime("%Y%m%d_%H%M%S"))
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(args.repo_root or PROJECT_ROOT).resolve()
    repo_items = audit_repo_files(repo_root)

    db_sections: dict[str, list[dict[str, Any]]] = {}
    db_errors: list[str] = []
    if not args.skip_db:
        db_sections, db_errors = audit_database(stale_hours=args.stale_hours, retention_days=args.retention_days, limit=args.limit)

    oss_candidates: list[dict[str, Any]] = []
    oss_errors: list[str] = []
    if args.list_oss:
        oss_candidates, oss_errors = audit_oss_candidates(
            prefix=args.oss_prefix,
            retention_days=args.retention_days,
            max_objects=args.oss_max_objects,
            reference_scan_limit=args.reference_scan_limit,
        )

    items = repo_items + _summarize_db_sections(db_sections)
    if oss_candidates:
        items.append(
            AuditItem(
                area="oss",
                item_type="unreferenced-object-candidates",
                risk="high",
                action="review-before-delete",
                path_or_id=str(args.oss_prefix or "settings.oss_root_prefix"),
                count=len(oss_candidates),
                size_bytes=sum(int(item.get("size_bytes") or 0) for item in oss_candidates),
                detail="OSS 候选对象必须人工复核后再删。",
            )
        )
    oss_groups = summarize_oss_candidates(oss_candidates)
    oss_deletion_plan = build_oss_deletion_review_plan(
        oss_candidates,
        batch_size=args.oss_delete_batch_size,
    )

    _write_json(raw_dir / "repo_candidates.json", [item.to_dict() for item in repo_items])
    _write_json(raw_dir / "database.json", db_sections)
    _write_json(raw_dir / "database_errors.json", db_errors)
    _write_json(raw_dir / "oss_candidates.json", oss_candidates)
    _write_json(raw_dir / "oss_candidate_groups.json", oss_groups)
    _write_json(raw_dir / "oss_errors.json", oss_errors)
    _write_csv(output_dir / "cleanup_candidates.csv", [item.to_dict() for item in items])
    _write_csv(output_dir / "oss_delete_review_manifest.csv", oss_deletion_plan)
    (output_dir / "summary.md").write_text(
        _build_summary(
            generated_at=generated_at,
            items=items,
            db_errors=db_errors,
            oss_candidates=oss_candidates,
            oss_groups=oss_groups,
            oss_errors=oss_errors,
            output_dir=output_dir,
        ),
        encoding="utf-8",
    )
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit cleanup candidates without deleting anything.")
    parser.add_argument("--repo-root", default=str(PROJECT_ROOT), help="Project root to scan for local temp artifacts.")
    parser.add_argument("--output-dir", default="", help="Report output directory.")
    parser.add_argument("--stale-hours", type=int, default=24, help="Non-terminal DB records older than this are suspicious.")
    parser.add_argument("--retention-days", type=int, default=30, help="Retention window for old empty/success-without-output records.")
    parser.add_argument("--limit", type=int, default=500, help="Max rows per DB section.")
    parser.add_argument("--skip-db", action="store_true", help="Only audit repo files; skip database queries.")
    parser.add_argument("--list-oss", action="store_true", help="List OSS objects and compare with DB references. Read-only.")
    parser.add_argument("--oss-prefix", default=None, help="OSS prefix to inspect. Defaults to OSS_ROOT_PREFIX.")
    parser.add_argument("--oss-max-objects", type=int, default=500, help="Max OSS objects to inspect.")
    parser.add_argument(
        "--oss-delete-batch-size",
        type=int,
        default=100,
        help="Batch size used only for the generated OSS review manifest. The script never deletes objects.",
    )
    parser.add_argument("--reference-scan-limit", type=int, default=20000, help="Max DB rows to scan for OSS references per table.")
    return parser.parse_args()


def main() -> None:
    output_dir = run_audit(parse_args())
    print(f"[OK] cleanup audit written to {output_dir}")


if __name__ == "__main__":
    main()
