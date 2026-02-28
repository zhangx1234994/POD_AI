#!/usr/bin/env python3
"""Clean ComfyUI LoRA catalog and align it with functional workflows.

Usage:
  cd backend && python3 ../scripts/cleanup_comfyui_lora_catalog.py --dry-run
  cd backend && python3 ../scripts/cleanup_comfyui_lora_catalog.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import get_session
from app.services.comfyui_lora_catalog_service import (
    collect_functional_lora_names,
    sync_lora_catalog_with_functional_set,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup comfyui_lora_catalog by functional set")
    parser.add_argument("--apply", action="store_true", help="Apply database changes")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would change")
    args = parser.parse_args()

    apply_changes = bool(args.apply and not args.dry_run)

    with get_session() as session:
        functional = collect_functional_lora_names(session)
        stats = sync_lora_catalog_with_functional_set(
            session,
            functional_names=functional,
            deactivate_others=True,
        )
        if apply_changes:
            session.commit()
            action = "APPLIED"
        else:
            session.rollback()
            action = "DRY-RUN"

    print(f"[{action}] functional_lora_count={len(functional)}")
    print(f"[{action}] inserted={stats['inserted']} activated={stats['activated']} deactivated={stats['deactivated']} kept_active={stats['kept_active']} total={stats['total']}")
    print("[FUNCTIONAL LORAS]")
    for name in sorted(functional):
        print(name)


if __name__ == "__main__":
    main()
