"""Seed default business quality samples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.business_quality_sample_seed import ensure_default_product_design_quality_samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed default business quality samples.")
    parser.add_argument("--dry-run", action="store_true", help="Validate sample payloads without writing to the database.")
    args = parser.parse_args()
    result = ensure_default_product_design_quality_samples(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if int(result.get("failed") or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
