#!/usr/bin/env python3
"""Upsert ComfyUI model catalog entries from a JSON file.

Usage:
  python3 scripts/comfyui_model_catalog_upsert.py --input reports/comfyui_model_catalog_seed_20260205.json
  python3 scripts/comfyui_model_catalog_upsert.py --input reports/... --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _safe_str(value: object) -> str:
    return str(value).strip()


def _default_display_name(file_name: str) -> str:
    if not file_name:
        return ""
    stem = Path(file_name).stem
    return stem or file_name


def main() -> int:
    parser = argparse.ArgumentParser(description="Upsert ComfyUI model catalog entries.")
    parser.add_argument("--input", required=True, help="Path to JSON list of catalog entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.core.db import get_session  # noqa: E402
    from app.models.integration import ComfyuiModelCatalog  # noqa: E402

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("Input JSON must be a list of entries")

    created = 0
    updated = 0
    skipped = 0

    with get_session() as session:
        for raw in payload:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            file_name = _safe_str(raw.get("file_name"))
            model_type = _safe_str(raw.get("model_type"))
            if not file_name or not model_type:
                skipped += 1
                continue

            row = (
                session.query(ComfyuiModelCatalog)
                .filter(
                    ComfyuiModelCatalog.file_name == file_name,
                    ComfyuiModelCatalog.model_type == model_type,
                )
                .one_or_none()
            )

            data = {
                "file_name": file_name,
                "display_name": _safe_str(raw.get("display_name")) or _default_display_name(file_name),
                "model_type": model_type,
                "download_url": _safe_str(raw.get("download_url")) or None,
                "source_url": _safe_str(raw.get("source_url")) or None,
                "description": _safe_str(raw.get("description")) or None,
                "status": _safe_str(raw.get("status")) or "active",
            }

            tags = raw.get("tags")
            if isinstance(tags, (list, tuple, set)):
                cleaned = [_safe_str(item) for item in tags if _safe_str(item)]
                data["tags"] = cleaned or None
            elif isinstance(tags, str) and tags.strip():
                data["tags"] = [tags.strip()]

            if row is None:
                if not args.dry_run:
                    session.add(ComfyuiModelCatalog(**data))
                created += 1
            else:
                for key, value in data.items():
                    if value is None and key in {"download_url", "source_url", "description", "tags"}:
                        continue
                    setattr(row, key, value)
                if not args.dry_run:
                    session.add(row)
                updated += 1

        if not args.dry_run:
            session.commit()

    print(f"[model-catalog] created={created} updated={updated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
