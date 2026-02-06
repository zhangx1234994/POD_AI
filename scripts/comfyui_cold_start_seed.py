#!/usr/bin/env python3
"""Seed ComfyUI baseline snapshot and optional catalog entries.

Usage:
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-models --seed-plugins
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-loras
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --output reports/comfyui_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ssl
from typing import Iterable


MODEL_TYPES = ("unet", "clip", "vae")
DEFAULT_MODEL_SOURCE = "reports/comfyui_model_catalog_seed_20260205.json"


def _is_url(value: str) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def _load_json_source(source: str, *, insecure: bool = False) -> object | None:
    if not source:
        return None
    path = Path(source)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if not _is_url(source):
        return None
    req = Request(source, headers={"User-Agent": "podi-comfyui-seed/1.0"})
    context = ssl._create_unverified_context() if insecure else None
    with urlopen(req, timeout=60, context=context) as resp:  # nosec B310
        payload = resp.read().decode("utf-8")
    return json.loads(payload)


def _clean_str(value: object) -> str:
    return str(value).strip()


def _safe_stem(file_name: str) -> str:
    file_name = file_name.strip()
    if not file_name:
        return ""
    return Path(file_name).stem or file_name


def _iter_files(values: Iterable[object]) -> list[str]:
    files: list[str] = []
    for item in values:
        trimmed = _clean_str(item)
        if trimmed:
            files.append(trimmed)
    return files


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _dedupe_ci(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in values:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _normalize_ref(value: object) -> str:
    ref = str(value or "").strip()
    if not ref:
        return ""
    if ref.startswith("git+"):
        ref = ref[4:]
    ref = ref.rstrip("/")
    return ref


def _ref_variants(value: object) -> list[str]:
    ref = _normalize_ref(value)
    if not ref:
        return []
    variants = {ref}
    if ref.endswith(".git"):
        variants.add(ref[:-4])
    return list(variants)


def _build_plugin_index(payload: object) -> dict[str, dict]:
    if payload is None:
        return {}
    items = payload
    if isinstance(payload, dict):
        if "custom_nodes" in payload and isinstance(payload["custom_nodes"], list):
            items = payload["custom_nodes"]
        elif "nodes" in payload and isinstance(payload["nodes"], list):
            items = payload["nodes"]
    if not isinstance(items, list):
        return {}
    index: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for ref in _ref_variants(item.get("reference")):
            if ref and ref not in index:
                index[ref] = item
        files = item.get("files")
        if isinstance(files, list):
            for file_ref in files:
                for ref in _ref_variants(file_ref):
                    if ref and ref not in index:
                        index[ref] = item
        item_id = str(item.get("id") or "").strip()
        if item_id and item_id not in index:
            index[item_id] = item
    return index


def _extract_node_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        if not value:
            return []
        if isinstance(value[0], list):
            return [str(item).strip() for item in value[0] if str(item).strip()]
        if all(isinstance(item, str) for item in value):
            return [item.strip() for item in value if item.strip()]
    if isinstance(value, dict):
        for key in ("nodes", "node_list", "node_keys"):
            nodes = value.get(key)
            if isinstance(nodes, list):
                return [str(item).strip() for item in nodes if str(item).strip()]
    return []


def _build_node_reference_map(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    mapping: dict[str, str] = {}
    for ref, value in payload.items():
        nodes = _extract_node_list(value)
        if not nodes:
            continue
        ref_norm = _normalize_ref(ref)
        for node in nodes:
            if node not in mapping:
                mapping[node] = ref_norm
    return mapping


def _build_model_index(payload: object) -> dict[tuple[str, str], dict]:
    if payload is None:
        return {}
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    elif isinstance(payload, list):
        items = payload
    else:
        return {}
    index: dict[tuple[str, str], dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        file_name = _clean_str(item.get("file_name"))
        model_type = _clean_str(item.get("model_type"))
        if not file_name or not model_type:
            continue
        index[(file_name, model_type)] = item
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed ComfyUI baseline snapshot and optional catalogs.")
    parser.add_argument("--executor-id", required=True, help="Executor ID for the baseline ComfyUI server")
    parser.add_argument(
        "--output",
        help="Output JSON path (default: reports/comfyui_baseline_<executor>_<timestamp>.json)",
    )
    parser.add_argument("--seed-models", action="store_true", help="Insert missing UNET/CLIP/VAE model entries")
    parser.add_argument("--seed-plugins", action="store_true", help="Insert missing plugin node entries")
    parser.add_argument("--seed-loras", action="store_true", help="Insert missing LoRA entries into DB")
    parser.add_argument(
        "--model-source",
        help=(
            "Optional model catalog JSON (path or URL). When provided, matching records will be "
            "used to fill download/source info."
        ),
    )
    parser.add_argument(
        "--plugin-list",
        help="Optional plugin list JSON (path or URL, e.g. custom-node-list.json).",
    )
    parser.add_argument(
        "--node-map",
        help="Optional node→plugin map JSON (path or URL, e.g. extension-node-map.json).",
    )
    parser.add_argument("--report", help="Optional output path for a missing-resources report JSON")
    parser.add_argument("--insecure", action="store_true", help="Allow insecure HTTPS fetch for remote JSON sources")
    parser.add_argument("--dry-run", action="store_true", help="Print summary only, do not write DB changes")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.core.db import get_session  # noqa: E402
    from app.models.integration import (  # noqa: E402
        ComfyuiLora,
        ComfyuiModelCatalog,
        ComfyuiPluginCatalog,
        Executor,
    )
    from app.services.integration_test import integration_test_service  # noqa: E402

    executor_id = args.executor_id.strip()
    if not executor_id:
        raise SystemExit("executor_id is required")

    with get_session() as session:
        executor = session.get(Executor, executor_id)
        if not executor:
            raise SystemExit(f"Executor not found: {executor_id}")

        model_source = args.model_source
        if not model_source:
            default_source = repo_root / DEFAULT_MODEL_SOURCE
            if default_source.exists():
                model_source = str(default_source)
        model_payload = _load_json_source(model_source, insecure=args.insecure) if model_source else None
        model_index = _build_model_index(model_payload)

        plugin_payload = _load_json_source(args.plugin_list, insecure=args.insecure) if args.plugin_list else None
        node_map_payload = _load_json_source(args.node_map, insecure=args.insecure) if args.node_map else None
        plugin_index = _build_plugin_index(plugin_payload)
        node_reference_map = _build_node_reference_map(node_map_payload)

        catalog = integration_test_service.get_comfyui_model_catalog(
            executor_id=executor_id,
            include_nodes=True,
        )

        snapshot = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "executor": {
                "id": executor.id,
                "name": executor.name,
                "type": executor.type,
                "status": executor.status,
                "base_url": executor.base_url,
            },
            "catalog": {
                "models": catalog.get("models", {}),
                "nodeKeys": catalog.get("nodeKeys") or [],
                "nodeCount": catalog.get("nodeCount") or 0,
                "baseUrl": catalog.get("baseUrl"),
            },
        }

        output_path = args.output
        if not output_path:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(repo_root / "reports" / f"comfyui_baseline_{executor_id}_{ts}.json")
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[snapshot] saved: {output_file}")

        if args.seed_models:
            model_files: dict[str, list[str]] = {}
            for model_type in MODEL_TYPES:
                model_files[model_type] = _iter_files(catalog.get("models", {}).get(model_type) or [])

            all_files = [file for files in model_files.values() for file in files]
            existing_pairs: set[tuple[str, str]] = set()
            if all_files:
                existing_pairs = {
                    (row.file_name, row.model_type)
                    for row in session.query(ComfyuiModelCatalog.file_name, ComfyuiModelCatalog.model_type)
                    .filter(
                        ComfyuiModelCatalog.model_type.in_(MODEL_TYPES),
                        ComfyuiModelCatalog.file_name.in_(all_files),
                    )
                    .all()
                }

            to_insert: list[ComfyuiModelCatalog] = []
            for model_type, files in model_files.items():
                for file_name in files:
                    key = (file_name, model_type)
                    if key in existing_pairs:
                        continue
                    display_name = _safe_stem(file_name) or file_name
                    to_insert.append(
                        ComfyuiModelCatalog(
                            file_name=file_name,
                            display_name=display_name,
                            model_type=model_type,
                            status="active",
                        )
                    )
            total_models = sum(len(files) for files in model_files.values())
            print(f"[model] total={total_models} new={len(to_insert)}")
            if not args.dry_run and to_insert:
                session.add_all(to_insert)
                session.commit()
                print("[model] inserted.")
            elif args.dry_run:
                print("[model] dry-run; no DB changes.")

            if model_index:
                updated = 0
                for model_type, files in model_files.items():
                    for file_name in files:
                        row = (
                            session.query(ComfyuiModelCatalog)
                            .filter(
                                ComfyuiModelCatalog.file_name == file_name,
                                ComfyuiModelCatalog.model_type == model_type,
                            )
                            .one_or_none()
                        )
                        if row is None:
                            continue
                        data = model_index.get((file_name, model_type))
                        if not data:
                            continue
                        download_url = _clean_str(data.get("download_url"))
                        source_url = _clean_str(data.get("source_url"))
                        description = _clean_str(data.get("description"))
                        display_name = _clean_str(data.get("display_name"))
                        tags = data.get("tags")

                        changed = False
                        if download_url and not row.download_url:
                            row.download_url = download_url
                            changed = True
                        if source_url and not row.source_url:
                            row.source_url = source_url
                            changed = True
                        if description and not row.description:
                            row.description = description
                            changed = True
                        if display_name and (row.display_name == row.file_name):
                            row.display_name = display_name
                            changed = True
                        if tags and not row.tags:
                            cleaned = [_clean_str(tag) for tag in tags if _clean_str(tag)]
                            if cleaned:
                                row.tags = cleaned
                                changed = True

                        if changed and not args.dry_run:
                            session.add(row)
                            updated += 1
                        elif changed:
                            updated += 1
                if not args.dry_run and updated:
                    session.commit()
                print(f"[model] metadata matched={updated}")

        if args.seed_plugins:
            node_keys = catalog.get("nodeKeys") or []
            node_keys = _dedupe_ci([_clean_str(item) for item in node_keys if _clean_str(item)])
            existing_keys: set[str] = set()
            if node_keys:
                existing_keys = {
                    row.node_key.lower()
                    for row in session.query(ComfyuiPluginCatalog.node_key)
                    .filter(ComfyuiPluginCatalog.node_key.in_(node_keys))
                    .all()
                }

            to_insert: list[ComfyuiPluginCatalog] = []
            for node_key in node_keys:
                if node_key.lower() in existing_keys:
                    continue
                to_insert.append(
                    ComfyuiPluginCatalog(
                        node_key=node_key,
                        display_name=node_key,
                        status="active",
                    )
                )
            print(f"[plugin] total={len(node_keys)} new={len(to_insert)}")
            if not args.dry_run and to_insert:
                session.add_all(to_insert)
                session.commit()
                print("[plugin] inserted.")
            elif args.dry_run:
                print("[plugin] dry-run; no DB changes.")

            if node_reference_map and plugin_index:
                existing_rows = {}
                if node_keys:
                    rows = (
                        session.query(ComfyuiPluginCatalog)
                        .filter(ComfyuiPluginCatalog.node_key.in_(node_keys))
                        .all()
                    )
                    existing_rows = {row.node_key.lower(): row for row in rows}
                updated = 0
                unmatched = 0
                for node_key in node_keys:
                    ref = node_reference_map.get(node_key)
                    if not ref:
                        unmatched += 1
                        continue
                    item = None
                    for variant in _ref_variants(ref):
                        item = plugin_index.get(variant)
                        if item:
                            break
                    if item is None:
                        unmatched += 1
                        continue
                    row = existing_rows.get(node_key.lower())
                    if row is None:
                        continue

                    display_name = _clean_str(item.get("title")) or _clean_str(item.get("name"))
                    package_name = _clean_str(item.get("id")) or _clean_str(item.get("package"))
                    description = _clean_str(item.get("description"))
                    source_url = _clean_str(item.get("reference"))
                    download_url = None
                    files = item.get("files")
                    if isinstance(files, list):
                        for file_ref in files:
                            if _is_url(str(file_ref)):
                                download_url = _clean_str(file_ref)
                                break
                    if not download_url:
                        download_url = source_url

                    changed = False
                    if package_name and not row.package_name:
                        row.package_name = package_name
                        changed = True
                    if display_name and row.display_name == row.node_key:
                        row.display_name = display_name
                        changed = True
                    if description and not row.description:
                        row.description = description
                        changed = True
                    if source_url and not row.source_url:
                        row.source_url = source_url
                        changed = True
                    if download_url and not row.download_url:
                        row.download_url = download_url
                        changed = True

                    if changed and not args.dry_run:
                        session.add(row)
                        updated += 1
                    elif changed:
                        updated += 1
                if not args.dry_run and updated:
                    session.commit()
                print(f"[plugin] metadata matched={updated} unmatched={unmatched}")
            elif args.plugin_list or args.node_map:
                print("[plugin] metadata match skipped: missing plugin list or node map")

        if args.seed_loras:
            lora_files = _iter_files(catalog.get("models", {}).get("lora") or [])
            existing = {
                row.file_name
                for row in session.query(ComfyuiLora.file_name).filter(ComfyuiLora.file_name.in_(lora_files)).all()
            }
            to_insert = []
            for file_name in lora_files:
                if file_name in existing:
                    continue
                display_name = _safe_stem(file_name) or file_name
                to_insert.append(
                    ComfyuiLora(
                        file_name=file_name,
                        display_name=display_name,
                        status="active",
                    )
                )
            print(f"[lora] total={len(lora_files)} new={len(to_insert)}")
            if not args.dry_run and to_insert:
                session.add_all(to_insert)
                session.commit()
                print("[lora] inserted.")
            elif args.dry_run:
                print("[lora] dry-run; no DB changes.")

        if args.report:
            report = {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "executor_id": executor_id,
                "models": {},
                "plugins": {},
            }
            model_missing: list[str] = []
            model_missing_items: list[dict[str, Any]] = []
            model_files = {}
            for model_type in MODEL_TYPES:
                model_files[model_type] = _iter_files(catalog.get("models", {}).get(model_type) or [])
            all_model_files = [file for files in model_files.values() for file in files]
            existing_models = {}
            if all_model_files:
                rows = (
                    session.query(ComfyuiModelCatalog)
                    .filter(
                        ComfyuiModelCatalog.model_type.in_(MODEL_TYPES),
                        ComfyuiModelCatalog.file_name.in_(all_model_files),
                    )
                    .all()
                )
                existing_models = {(row.file_name, row.model_type): row for row in rows}
            for model_type, files in model_files.items():
                for file_name in files:
                    row = existing_models.get((file_name, model_type))
                    if row is None or not row.download_url:
                        model_missing.append(file_name)
                        model_missing_items.append(
                            {
                                "file_name": file_name,
                                "model_type": model_type,
                                "download_url": row.download_url if row else None,
                                "source_url": row.source_url if row else None,
                            }
                        )
            report["models"] = {
                "total": sum(len(files) for files in model_files.values()),
                "missing_download": sorted(set(model_missing)),
                "missing_items": model_missing_items,
            }

            node_keys = _dedupe_ci([_clean_str(item) for item in (catalog.get("nodeKeys") or []) if _clean_str(item)])
            plugin_missing: list[str] = []
            plugin_missing_repo: list[str] = []
            repo_groups: dict[str, dict[str, Any]] = {}
            existing_plugins = {}
            if node_keys:
                rows = (
                    session.query(ComfyuiPluginCatalog)
                    .filter(ComfyuiPluginCatalog.node_key.in_(node_keys))
                    .all()
                )
                existing_plugins = {row.node_key.lower(): row for row in rows}
            for node_key in node_keys:
                row = existing_plugins.get(node_key.lower())
                if row is None or not row.download_url:
                    plugin_missing.append(node_key)
                if row is None:
                    plugin_missing_repo.append(node_key)
                    continue
                repo = (row.source_url or row.download_url or "").strip()
                if not repo:
                    plugin_missing_repo.append(node_key)
                    continue
                group = repo_groups.setdefault(
                    repo,
                    {
                        "repo": repo,
                        "package_name": row.package_name,
                        "download_url": row.download_url,
                        "nodes": [],
                    },
                )
                group["nodes"].append(node_key)
            report["plugins"] = {
                "total": len(node_keys),
                "missing_download": sorted(set(plugin_missing)),
                "missing_repo": sorted(set(plugin_missing_repo)),
                "repos": sorted(repo_groups.values(), key=lambda item: item.get("repo") or ""),
            }

            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[report] saved: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
