#!/usr/bin/env python3
"""Export the previous day's operations health snapshot.

This script is intended to be the first read-only check every morning. It
summarizes business runs, ability logs, eval runs and business API key usage,
then writes a small deliverable pack for review.
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.db import get_session


def _default_check_date(tz_name: str) -> str:
    now = datetime.now(ZoneInfo(tz_name))
    return (now.date() - timedelta(days=1)).isoformat()


def _resolve_window(check_date: str, tz_name: str) -> tuple[datetime, datetime, datetime, datetime]:
    local_tz = ZoneInfo(tz_name)
    day = datetime.fromisoformat(check_date).date()
    start_local = datetime(day.year, day.month, day.day, tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_local, end_local, start_utc, end_utc


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _query_rows(session: Any, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = session.execute(text(sql), params or {})
    return [{key: _normalize_value(value) for key, value in row._mapping.items()} for row in result]


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, data: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    for item in data:
        for key in item:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys or ["empty"])
        writer.writeheader()
        for item in data:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                    for key, value in item.items()
                }
            )


def _one_line(value: Any, limit: int = 180) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ")[:limit]


def _build_summary_markdown(
    *,
    check_date: str,
    start_local: datetime,
    end_local: datetime,
    start_utc: datetime,
    end_utc: datetime,
    business_summary: list[dict[str, Any]],
    business_issues: list[dict[str, Any]],
    ability_issues: list[dict[str, Any]],
    ability_pending: list[dict[str, Any]],
    eval_issues: list[dict[str, Any]],
    key_usage_issues: list[dict[str, Any]],
    business_recent_count: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# {check_date} 运营早检报告")
    lines.append("")
    lines.append(
        f"- 检查窗口：{start_local.isoformat()} ~ {end_local.isoformat()}（数据库 UTC：{start_utc.isoformat()} ~ {end_utc.isoformat()}）"
    )
    lines.append(f"- 业务运行：{business_recent_count} 条，需关注 {len(business_issues)} 条")
    lines.append(f"- 能力调用需关注：{len(ability_issues)} 条，历史 pending 残留：{len(ability_pending)} 条")
    lines.append(f"- 测评运行需关注：{len(eval_issues)} 条")
    lines.append(f"- 业务 API Key 调用异常：{len(key_usage_issues)} 条")
    lines.append("")
    lines.append("## 业务运行汇总")
    lines.append("")
    lines.append("| 业务 | 状态 | 数量 | 平均耗时(ms) | 最近时间 |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for row in business_summary:
        avg_duration = round(row.get("avg_duration_ms") or 0, 2)
        lines.append(
            f"| {row.get('business_key')} | {row.get('status')} | {row.get('count')} | {avg_duration} | {row.get('latest_created_at')} |"
        )
    lines.append("")
    lines.append("## 需关注业务运行")
    lines.append("")
    if business_issues:
        lines.append("| 时间 | 业务 | 状态 | runId | 错误 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in business_issues[:30]:
            lines.append(
                f"| {row.get('created_at')} | {row.get('business_key')} | {row.get('status')} | `{row.get('id')}` | {_one_line(row.get('error_message'))} |"
            )
    else:
        lines.append("无。")
    lines.append("")
    lines.append("## 能力调用需关注")
    lines.append("")
    if ability_issues:
        lines.append("| 时间 | 能力 | 状态 | logId | 执行节点 | 错误 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in ability_issues[:50]:
            lines.append(
                f"| {row.get('created_at')} | {row.get('ability_name') or row.get('capability_key')} | {row.get('status')} | `{row.get('id')}` | {row.get('executor_name') or ''} | {_one_line(row.get('error_message'))} |"
            )
    else:
        lines.append("无。")
    lines.append("")
    lines.append("## 测评运行需关注")
    lines.append("")
    if eval_issues:
        lines.append("| 时间 | 测评入口 | 状态 | runId | 错误 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in eval_issues[:50]:
            lines.append(
                f"| {row.get('created_at')} | {row.get('name') or row.get('workflow_id')} | {row.get('status')} | `{row.get('id')}` | {_one_line(row.get('error_message'))} |"
            )
    else:
        lines.append("无。")
    lines.append("")
    lines.append("## 导出文件")
    lines.append("")
    lines.append("- `raw/*.json`：完整结构化数据")
    lines.append("- `csv/*.csv`：给业务/测试快速查看的表格")
    lines.append("- `summary.md`：本报告")
    return "\n".join(lines) + "\n"


def run_export(*, check_date: str, tz_name: str, output_dir: Path, max_rows: int) -> dict[str, Any]:
    start_local, end_local, start_utc, end_utc = _resolve_window(check_date, tz_name)
    raw_dir = output_dir / "raw"
    csv_dir = output_dir / "csv"
    raw_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

    with get_session() as session:
        business_summary = _query_rows(
            session,
            """
            SELECT business_key, status, COUNT(*) AS count,
                   AVG(duration_ms) AS avg_duration_ms,
                   MAX(created_at) AS latest_created_at
            FROM business_runs
            WHERE created_at >= :start AND created_at < :end
            GROUP BY business_key, status
            ORDER BY business_key, status
            """,
            {"start": start_utc, "end": end_utc},
        )
        business_recent = _query_rows(
            session,
            """
            SELECT id, business_key, business_version_id, version, status, source, channel,
                   trace_id, request_id, tenant_id, client_id, ability_id, ability_task_id,
                   ability_log_id, duration_ms, callback_status, callback_http_status,
                   LEFT(COALESCE(error_message, ''), 500) AS error_message,
                   JSON_LENGTH(image_urls) AS image_count,
                   JSON_LENGTH(video_urls) AS video_count,
                   JSON_LENGTH(texts) AS text_count,
                   created_at, updated_at, started_at, finished_at
            FROM business_runs
            WHERE created_at >= :start AND created_at < :end
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"start": start_utc, "end": end_utc, "limit": max_rows},
        )
        business_issues = _query_rows(
            session,
            """
            SELECT id, business_key, business_version_id, version, status, source, channel,
                   trace_id, request_id, tenant_id, client_id, ability_id, ability_task_id,
                   ability_log_id, duration_ms, callback_status, callback_http_status,
                   LEFT(COALESCE(error_message, callback_error, ''), 1000) AS error_message,
                   JSON_LENGTH(image_urls) AS image_count,
                   JSON_LENGTH(video_urls) AS video_count,
                   JSON_LENGTH(texts) AS text_count,
                   created_at, updated_at, started_at, finished_at
            FROM business_runs
            WHERE created_at >= :start AND created_at < :end
              AND (
                status NOT IN ('succeeded')
                OR callback_status IN ('failed')
                OR callback_error IS NOT NULL
                OR (status='succeeded' AND COALESCE(JSON_LENGTH(image_urls), 0)=0 AND COALESCE(JSON_LENGTH(video_urls), 0)=0 AND COALESCE(JSON_LENGTH(texts), 0)=0)
              )
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"start": start_utc, "end": end_utc, "limit": max_rows},
        )
        ability_summary = _query_rows(
            session,
            """
            SELECT ability_provider, capability_key, status, COUNT(*) AS count,
                   AVG(duration_ms) AS avg_duration_ms,
                   MAX(created_at) AS latest_created_at
            FROM ability_invocation_logs
            WHERE created_at >= :start AND created_at < :end
            GROUP BY ability_provider, capability_key, status
            ORDER BY ability_provider, capability_key, status
            """,
            {"start": start_utc, "end": end_utc},
        )
        ability_issues = _query_rows(
            session,
            """
            SELECT id, ability_id, ability_name, ability_provider, capability_key, source, task_id,
                   executor_id, executor_name, executor_type, status, duration_ms,
                   callback_status, callback_http_status,
                   LEFT(COALESCE(error_message, callback_error, ''), 1000) AS error_message,
                   stored_url, trace_id, workflow_run_id, created_at, updated_at
            FROM ability_invocation_logs
            WHERE created_at >= :start AND created_at < :end
              AND (
                status NOT IN ('success', 'succeeded')
                OR callback_status IN ('failed')
                OR callback_error IS NOT NULL
              )
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"start": start_utc, "end": end_utc, "limit": max_rows},
        )
        ability_pending = _query_rows(
            session,
            """
            SELECT id, ability_id, ability_name, ability_provider, capability_key, source, task_id,
                   executor_id, executor_name, executor_type, status, duration_ms,
                   LEFT(COALESCE(error_message, ''), 1000) AS error_message,
                   created_at, updated_at
            FROM ability_invocation_logs
            WHERE status='pending'
              AND created_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 30 MINUTE)
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"limit": max_rows},
        )
        eval_summary = _query_rows(
            session,
            """
            SELECT r.status, w.category, w.name, w.workflow_id, COUNT(*) AS count,
                   AVG(r.duration_ms) AS avg_duration_ms,
                   MAX(r.created_at) AS latest_created_at
            FROM eval_run r
            LEFT JOIN eval_workflow_version w ON w.id = r.workflow_version_id
            WHERE r.created_at >= :start AND r.created_at < :end
            GROUP BY r.status, w.category, w.name, w.workflow_id
            ORDER BY w.category, w.name, r.status
            """,
            {"start": start_utc, "end": end_utc},
        )
        eval_issues = _query_rows(
            session,
            """
            SELECT r.id, r.workflow_version_id, w.workflow_id, w.name, w.category, r.status,
                   r.podi_task_id, r.coze_execute_id, r.duration_ms,
                   LEFT(COALESCE(r.error_message, ''), 1000) AS error_message,
                   JSON_LENGTH(r.result_image_urls_json) AS image_count,
                   CASE WHEN r.result_output_json IS NULL THEN 0 ELSE 1 END AS has_structured_output,
                   r.created_at, r.updated_at
            FROM eval_run r
            LEFT JOIN eval_workflow_version w ON w.id = r.workflow_version_id
            WHERE r.created_at >= :start AND r.created_at < :end
              AND (
                r.status NOT IN ('succeeded')
                OR (COALESCE(JSON_LENGTH(r.result_image_urls_json), 0)=0 AND r.result_output_json IS NULL)
              )
            ORDER BY r.created_at DESC
            LIMIT :limit
            """,
            {"start": start_utc, "end": end_utc, "limit": max_rows},
        )
        key_usage_summary = _query_rows(
            session,
            """
            SELECT business_key, status_code, error_code, COUNT(*) AS count,
                   AVG(duration_ms) AS avg_duration_ms,
                   MAX(created_at) AS latest_created_at
            FROM business_api_key_usage_logs
            WHERE created_at >= :start AND created_at < :end
            GROUP BY business_key, status_code, error_code
            ORDER BY business_key, status_code, error_code
            """,
            {"start": start_utc, "end": end_utc},
        )
        key_usage_issues = _query_rows(
            session,
            """
            SELECT id, api_key_name, api_key_preview, method, path, status_code, business_key,
                   run_id, request_id, trace_id, tenant_id, client_id, error_code, duration_ms,
                   ip_address, created_at
            FROM business_api_key_usage_logs
            WHERE created_at >= :start AND created_at < :end
              AND (status_code IS NULL OR status_code < 200 OR status_code >= 300 OR error_code IS NOT NULL)
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            {"start": start_utc, "end": end_utc, "limit": max_rows},
        )

    payloads: dict[str, Any] = {
        "business_runs": business_recent,
        "business_issues": business_issues,
        "ability_summary": ability_summary,
        "ability_issues": ability_issues,
        "ability_pending": ability_pending,
        "eval_summary": eval_summary,
        "eval_issues": eval_issues,
        "business_api_key_usage_summary": key_usage_summary,
        "business_api_key_usage_issues": key_usage_issues,
    }
    summary = {
        "window": {
            "localStart": start_local.isoformat(),
            "localEnd": end_local.isoformat(),
            "utcStart": start_utc.isoformat(),
            "utcEnd": end_utc.isoformat(),
        },
        "counts": {
            "businessRuns": len(business_recent),
            "businessIssues": len(business_issues),
            "abilityIssues": len(ability_issues),
            "stalePendingAbilityLogs": len(ability_pending),
            "evalIssues": len(eval_issues),
            "apiKeyUsageIssues": len(key_usage_issues),
        },
        "businessSummary": business_summary,
        "abilitySummary": ability_summary,
        "evalSummary": eval_summary,
        "keyUsageSummary": key_usage_summary,
    }
    payloads["summary"] = summary

    for name, data in payloads.items():
        _write_json(raw_dir / f"{name}.json", data)
        if isinstance(data, list):
            _write_csv(csv_dir / f"{name}.csv", data)

    summary_md = _build_summary_markdown(
        check_date=check_date,
        start_local=start_local,
        end_local=end_local,
        start_utc=start_utc,
        end_utc=end_utc,
        business_summary=business_summary,
        business_issues=business_issues,
        ability_issues=ability_issues,
        ability_pending=ability_pending,
        eval_issues=eval_issues,
        key_usage_issues=key_usage_issues,
        business_recent_count=len(business_recent),
    )
    (output_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    zip_path = output_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in output_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(output_dir.parent))

    return {
        "ok": True,
        "outputDir": str(output_dir),
        "zip": str(zip_path),
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the previous day's operations health snapshot.")
    parser.add_argument("--timezone", default="Asia/Shanghai", help="Local business timezone.")
    parser.add_argument("--date", default="", help="Local date to check, YYYY-MM-DD. Defaults to yesterday.")
    parser.add_argument("--output-dir", default="", help="Output directory. Defaults to reports/morning-check/YYYYMMDD.")
    parser.add_argument("--max-rows", type=int, default=300, help="Maximum issue/detail rows per section.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable summary JSON.")
    args = parser.parse_args()

    check_date = args.date or _default_check_date(args.timezone)
    output_dir = Path(args.output_dir) if args.output_dir else Path("reports/morning-check") / check_date.replace("-", "")
    result = run_export(
        check_date=check_date,
        tz_name=args.timezone,
        output_dir=output_dir,
        max_rows=max(1, args.max_rows),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        counts = result["summary"]["counts"]
        print(f"morning check exported: {result['zip']}")
        print(
            "counts: "
            f"businessIssues={counts['businessIssues']}, "
            f"abilityIssues={counts['abilityIssues']}, "
            f"stalePendingAbilityLogs={counts['stalePendingAbilityLogs']}, "
            f"evalIssues={counts['evalIssues']}, "
            f"apiKeyUsageIssues={counts['apiKeyUsageIssues']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
