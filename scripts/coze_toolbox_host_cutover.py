#!/usr/bin/env python3
"""Plan/apply/rollback Coze toolbox host cutovers for a fixed plugin allowlist.

This script intentionally edits only Coze plugin metadata. It does not mutate
workflow canvases, task rows, or tool contracts.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OLD_HOST = "http://117.50.80.158:8099"
NEW_HOST = "http://114.55.0.56:8099"


@dataclass(frozen=True)
class ToolboxTarget:
    plugin_id: int
    name: str
    openapi_path: str
    required_paths: tuple[str, ...]


FIRST_WAVE_TARGETS: tuple[ToolboxTarget, ...] = (
    ToolboxTarget(
        7631836638263377920,
        "新高质量裂变 · flux_strong_hq_softstyle_fission",
        "/api/coze/podi/comfyui/execute/flux-strong-hq-softstyle-fission/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/flux_strong_hq_softstyle_fission",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7631173785135087616,
        "FLUX2-Klein 扩图",
        "/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/flux2_klein_9b_outpaint",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7628913766867927040,
        "裂变文字强化 · qwen2512_print_shape_text_enhance",
        "/api/coze/podi/comfyui/execute/qwen2512-print-shape-text-enhance/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/qwen2512_print_shape_text_enhance",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7628912336622845952,
        "FLUX2 裂变+四方",
        "/api/coze/podi/comfyui/execute/flux2-9b-liebian-sifang/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/flux2_9b_liebian_sifang",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7628910935691755520,
        "头部抠像",
        "/api/coze/podi/comfyui/execute/toubu-kouxiang/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/toubu_kouxiang",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7628907351721902080,
        "背景抠图",
        "/api/coze/podi/comfyui/execute/beijing-koutu/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/beijing_koutu",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7622183737911934976,
        "E7 裂变重绘",
        "/api/coze/podi/comfyui/execute/e7-flux2-liebian/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/e7_flux2_liebian",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7619028968418574336,
        "8步加速可换 LoRA",
        "/api/coze/podi/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/yinhua_tiqu_lora_8step",
            "/api/coze/podi/tasks/get",
        ),
    ),
    ToolboxTarget(
        7618120767196102656,
        "多图融合",
        "/api/coze/podi/comfyui/execute/duotu-ronghe/openapi.json",
        (
            "/api/coze/podi/tools/comfyui/duotu_ronghe",
            "/api/coze/podi/tasks/get",
        ),
    ),
)

DEFERRED_PLUGIN_IDS = {
    7597708980080607232,  # PODI Utils: image atomics.
    7598530380819333120,  # PODI Utils duplicate.
    7597514608831627264,  # PODI Abilities aggregate.
    7629396726855499776,  # PODI Abilities aggregate in another space.
}


def _run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _mysql_cmd(args: argparse.Namespace, sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        args.mysql_container,
        "mysql",
        f"-u{args.mysql_user}",
        f"-p{args.mysql_password}",
        args.mysql_database,
        "--batch",
        "--raw",
        "--skip-column-names",
        "-e",
        sql,
    ]
    result = _run(cmd)
    return result.stdout


def _shell_quote(value: str) -> str:
    return shlex.quote(value)


def _sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _ids_sql(targets: tuple[ToolboxTarget, ...]) -> str:
    return ",".join(str(t.plugin_id) for t in targets)


def _read_rows(args: argparse.Namespace, targets: tuple[ToolboxTarget, ...]) -> list[dict[str, Any]]:
    ids = _ids_sql(targets)
    sql = f"""
select 'plugin' as table_name,id as row_id,id as plugin_id,server_url,
  json_unquote(json_extract(openapi_doc,'$.servers[0].url')) as doc_server,
  to_base64(cast(openapi_doc as char)) as doc_b64
from plugin where id in ({ids})
union all
select 'plugin_draft' as table_name,id as row_id,id as plugin_id,server_url,
  json_unquote(json_extract(openapi_doc,'$.servers[0].url')) as doc_server,
  to_base64(cast(openapi_doc as char)) as doc_b64
from plugin_draft where id in ({ids}) and deleted_at is null
union all
select 'plugin_version' as table_name,id as row_id,plugin_id,server_url,
  json_unquote(json_extract(openapi_doc,'$.servers[0].url')) as doc_server,
  to_base64(cast(openapi_doc as char)) as doc_b64
from plugin_version where plugin_id in ({ids}) and deleted_at is null
order by plugin_id, table_name, row_id;
"""
    rows: list[dict[str, Any]] = []
    for line in _mysql_cmd(args, sql).splitlines():
        parts = line.split("\t")
        if len(parts) != 6:
            continue
        table_name, row_id, plugin_id, server_url, doc_server, doc_b64 = parts
        doc: dict[str, Any] = {}
        if doc_b64 and doc_b64 != "NULL":
            try:
                doc = json.loads(base64.b64decode(doc_b64).decode("utf-8"))
            except Exception:
                doc = {}
        rows.append(
            {
                "table": table_name,
                "row_id": int(row_id),
                "plugin_id": int(plugin_id),
                "server_url": "" if server_url == "NULL" else server_url,
                "doc_server": "" if doc_server == "NULL" else doc_server,
                "doc": doc,
            }
        )
    return rows


def _validate_contracts(
    args: argparse.Namespace,
    targets: tuple[ToolboxTarget, ...],
    host: str,
) -> list[str]:
    errors: list[str] = []
    token = os.getenv("SERVICE_API_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    for target in targets:
        url = f"{host.rstrip('/')}{target.openapi_path}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=args.http_timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            errors.append(f"{target.plugin_id} {target.name}: HTTP {exc.code} for {url}")
            continue
        except Exception as exc:
            errors.append(f"{target.plugin_id} {target.name}: cannot fetch {url}: {exc}")
            continue
        paths = payload.get("paths") if isinstance(payload, dict) else {}
        for required in target.required_paths:
            if not isinstance(paths, dict) or required not in paths:
                errors.append(f"{target.plugin_id} {target.name}: OpenAPI missing path {required}")
    return errors


def _validate_rows(
    rows: list[dict[str, Any]],
    targets: tuple[ToolboxTarget, ...],
    expected_host: str,
    *,
    strict: bool,
) -> list[str]:
    errors: list[str] = []
    rows_by_plugin: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_plugin.setdefault(row["plugin_id"], []).append(row)

    for target in targets:
        plugin_rows = rows_by_plugin.get(target.plugin_id, [])
        tables = {row["table"] for row in plugin_rows}
        for required_table in ("plugin", "plugin_draft", "plugin_version"):
            if required_table not in tables:
                errors.append(f"{target.plugin_id} {target.name}: missing {required_table} row")
        for row in plugin_rows:
            server_ok = row["server_url"] == expected_host
            doc_ok = row["doc_server"] == expected_host
            if strict and (not server_ok or not doc_ok):
                errors.append(
                    f"{target.plugin_id} {target.name}: {row['table']}:{row['row_id']} "
                    f"server_url={row['server_url']!r} doc_server={row['doc_server']!r}, expected {expected_host!r}"
                )
            paths = row["doc"].get("paths") if isinstance(row["doc"], dict) else {}
            if isinstance(paths, dict):
                for required in target.required_paths:
                    if required not in paths:
                        errors.append(
                            f"{target.plugin_id} {target.name}: {row['table']}:{row['row_id']} missing {required}"
                        )
    return errors


def _print_plan(rows: list[dict[str, Any]], targets: tuple[ToolboxTarget, ...]) -> None:
    target_names = {target.plugin_id: target.name for target in targets}
    print("target plugin rows:")
    for row in rows:
        print(
            f"- {row['plugin_id']} {target_names.get(row['plugin_id'], '')} "
            f"{row['table']}:{row['row_id']} server={row['server_url']} doc={row['doc_server']}"
        )


def _backup(args: argparse.Namespace, label: str) -> Path:
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"coze_toolbox_{label}_{stamp}.sql"
    cmd = (
        f"docker exec {shlex.quote(args.mysql_container)} "
        f"mysqldump -u{shlex.quote(args.mysql_user)} -p{shlex.quote(args.mysql_password)} "
        f"--single-transaction --skip-lock-tables --no-tablespaces {shlex.quote(args.mysql_database)} "
        "plugin plugin_draft plugin_version > "
        f"{_shell_quote(str(path))}"
    )
    subprocess.run(["bash", "-lc", cmd], check=True)
    print(f"backup: {path}")
    return path


def _apply_update(args: argparse.Namespace, targets: tuple[ToolboxTarget, ...], src_host: str, dst_host: str) -> None:
    ids = _ids_sql(targets)
    src = _sql_quote(src_host)
    dst = _sql_quote(dst_host)
    sql = f"""
start transaction;
update plugin
set server_url = {dst},
    openapi_doc = json_set(openapi_doc, '$.servers[0].url', {dst})
where id in ({ids})
  and server_url = {src};
update plugin_draft
set server_url = {dst},
    openapi_doc = json_set(openapi_doc, '$.servers[0].url', {dst})
where id in ({ids})
  and deleted_at is null
  and server_url = {src};
update plugin_version
set server_url = {dst},
    openapi_doc = json_set(openapi_doc, '$.servers[0].url', {dst})
where plugin_id in ({ids})
  and deleted_at is null
  and server_url = {src};
commit;
select 'plugin', row_count();
"""
    _mysql_cmd(args, sql)


def _target_subset(args: argparse.Namespace) -> tuple[ToolboxTarget, ...]:
    if not args.plugin_id:
        return FIRST_WAVE_TARGETS
    wanted = {int(v) for raw in args.plugin_id for v in raw.split(",") if v.strip()}
    illegal = wanted & DEFERRED_PLUGIN_IDS
    if illegal:
        raise SystemExit(f"Refusing to touch deferred image-atomic/aggregate plugin ids: {sorted(illegal)}")
    targets = tuple(target for target in FIRST_WAVE_TARGETS if target.plugin_id in wanted)
    missing = wanted - {target.plugin_id for target in targets}
    if missing:
        raise SystemExit(f"Unknown first-wave plugin ids: {sorted(missing)}")
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "apply", "rollback"))
    parser.add_argument("--old-host", default=OLD_HOST)
    parser.add_argument("--new-host", default=NEW_HOST)
    parser.add_argument("--plugin-id", action="append", default=[], help="Limit to one or more first-wave plugin IDs.")
    parser.add_argument("--mysql-container", default="coze-mysql")
    parser.add_argument("--mysql-user", default="coze")
    parser.add_argument("--mysql-password", default="coze123")
    parser.add_argument("--mysql-database", default="opencoze")
    parser.add_argument("--backup-dir", default="/srv/pod/runtime")
    parser.add_argument("--http-timeout", type=int, default=20)
    parser.add_argument("--skip-contract-check", action="store_true")
    parser.add_argument("--allow-nonmatching-source", action="store_true")
    args = parser.parse_args()

    targets = _target_subset(args)
    if not targets:
        raise SystemExit("No toolbox targets selected.")

    source = args.old_host if args.action in {"plan", "apply"} else args.new_host
    destination = args.new_host if args.action == "apply" else args.old_host

    print(f"action: {args.action}")
    print(f"source host: {source}")
    print(f"destination host: {destination if args.action != 'plan' else '(none)'}")
    print(f"target count: {len(targets)}")

    if args.action in {"plan", "apply"} and not args.skip_contract_check:
        errors = _validate_contracts(args, targets, args.new_host)
        if errors:
            print("contract check failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 2

    rows = _read_rows(args, targets)
    _print_plan(rows, targets)
    row_errors = _validate_rows(
        rows,
        targets,
        source,
        strict=not args.allow_nonmatching_source and args.action != "plan",
    )
    if row_errors:
        print("row validation failed:", file=sys.stderr)
        for error in row_errors:
            print(f"- {error}", file=sys.stderr)
        return 3

    if args.action == "plan":
        if row_errors:
            print("plan warnings:")
            for error in row_errors:
                print(f"- {error}")
        return 0

    _backup(args, args.action)
    _apply_update(args, targets, source, destination)
    after = _read_rows(args, targets)
    _print_plan(after, targets)
    after_errors = _validate_rows(after, targets, destination, strict=True)
    if after_errors:
        print("post-update validation failed:", file=sys.stderr)
        for error in after_errors:
            print(f"- {error}", file=sys.stderr)
        return 4
    print("cutover validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
