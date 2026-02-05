#!/usr/bin/env python3
"""Seed ComfyUI baseline snapshot and optional LoRA catalog entries.

Usage:
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --seed-loras
  python3 scripts/comfyui_cold_start_seed.py --executor-id executor_comfyui_xxx --output reports/comfyui_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed ComfyUI baseline snapshot and LoRA catalog.")
    parser.add_argument("--executor-id", required=True, help="Executor ID for the baseline ComfyUI server")
    parser.add_argument(
        "--output",
        help="Output JSON path (default: reports/comfyui_baseline_<executor>_<timestamp>.json)",
    )
    parser.add_argument("--seed-loras", action="store_true", help="Insert missing LoRA entries into DB")
    parser.add_argument("--dry-run", action="store_true", help="Print summary only, do not write DB changes")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.core.db import get_session  # noqa: E402
    from app.models.integration import ComfyuiLora, Executor  # noqa: E402
    from app.services.integration_test import integration_test_service  # noqa: E402

    executor_id = args.executor_id.strip()
    if not executor_id:
        raise SystemExit("executor_id is required")

    with get_session() as session:
        executor = session.get(Executor, executor_id)
        if not executor:
            raise SystemExit(f"Executor not found: {executor_id}")

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

        if args.seed_loras:
            lora_files = catalog.get("models", {}).get("lora") or []
            lora_files = [str(item).strip() for item in lora_files if str(item).strip()]
            existing = {
                row.file_name
                for row in session.query(ComfyuiLora.file_name).filter(ComfyuiLora.file_name.in_(lora_files)).all()
            }
            to_insert = []
            for file_name in lora_files:
                if file_name in existing:
                    continue
                display_name = file_name.replace(".safetensors", "")
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
