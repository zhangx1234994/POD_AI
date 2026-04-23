#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_FILES = [
    "docs/strategy/coze-control-plane-migration-pack-v1.md",
    "docs/strategy/coze-mid-platform-migration-v1.md",
    "docs/strategy/coze-migration-config-matrix-v1.md",
    "docs/strategy/coze-migration-inventory-v1.md",
    "docs/strategy/coze-host-cutover-sequence-v1.md",
    "docs/strategy/coze-host-reference-phasing-v1.md",
    "docs/strategy/coze-desktop-centerurl-cutover-v1.md",
    "docs/strategy/coze-server-layout-v1.md",
    "docs/strategy/image-ops-service-split-v1.md",
    "docs/testing/README.md",
    "docs/testing/COZE_CONTROL_PLANE_MIGRATION_CHECKLIST.md",
    "docs/testing/COZE_CONTROL_PLANE_MIGRATION_DRILL_v1.md",
    "docs/testing/COZE_CONTROL_PLANE_RUNBOOK_v1.md",
    "docs/testing/COZE_SERVER_COMMANDS_v1.md",
    "docs/testing/IMAGE_OPS_SMOKE_CHECKLIST_v1.md",
    "docs/testing/DESKTOP_CENTERURL_CUTOVER_RUNBOOK_v1.md",
    "scripts/deploy_coze_backend_image_ops_only.sh",
    "scripts/deploy_coze_control_plane_nodocker.sh",
    "scripts/run_coze_control_plane_cutover.sh",
    "scripts/check_coze_control_plane_bundle.sh",
    "scripts/smoke_image_ops_via_backend.py",
    "scripts/smoke_coze_primary_workflows.sh",
    "scripts/rollback_coze_control_plane.sh",
    "scripts/rollback_verify_coze_control_plane.sh",
    "scripts/prod_write_backend_env.sh",
    "scripts/prod_write_image_ops_env.sh",
    "scripts/prod_write_coze_control_plane_envs.sh",
    "scripts/check_coze_host_cutover_refs.py",
    "scripts/collect_coze_migration_inventory.py",
    "image-ops-service/app/main.py",
    "image-ops-service/deploy/image-ops.service",
    "docker-compose.image-ops.yml",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check migration-pack required files.")
    parser.add_argument("--root", default=".", help="Repo root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    missing: list[str] = []
    present: list[str] = []

    for rel in REQUIRED_FILES:
        path = root / rel
        if path.exists():
            present.append(rel)
        else:
            missing.append(rel)

    result = {
        "root": str(root),
        "requiredCount": len(REQUIRED_FILES),
        "presentCount": len(present),
        "missingCount": len(missing),
        "missing": missing,
        "status": "ok" if not missing else "failed",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
