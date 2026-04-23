#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


FIRST_WAVE_FILES = {
    "docs/coze/toolbox-inventory.md",
    "docs/coze-integration.md",
    "docs/coze-plugin-podi.md",
    "docs/api/modules/coze.md",
}

SECOND_WAVE_FILES = {
    "comfyui-desktop/installer/podi-agent.iss",
    "comfyui-desktop/installer/install_windows.ps1",
    "comfyui-desktop/installer/build_windows.ps1",
    "comfyui-desktop/installer/publish_windows_release.ps1",
    "comfyui-desktop/README.md",
    "docs/api/modules/agent.md",
}

LOCAL_ALLOWED_FILES = {
    "podi-admin-web/nginx.conf",
    "podi-eval-web/nginx.conf",
    "scripts/prodlike_restart_web_static.sh",
    "scripts/node_static_proxy.mjs",
    "backend/scripts/check_coze_control_plane_migration.py",
    "scripts/check_coze_control_plane_bundle.sh",
}

OLD_BACKEND = "117.50.80.158:8099"
LOCAL_BACKEND = "127.0.0.1:8099"
DOCKER_BACKEND = "host.docker.internal:8099"


def _read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Check host references by cutover phase.")
    parser.add_argument("--root", default=".", help="Repository root.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    failures: list[str] = []

    for rel in sorted(FIRST_WAVE_FILES):
        path = root / rel
        for lineno, line in enumerate(_read(path), start=1):
            if OLD_BACKEND in line:
                failures.append(f"[first-wave] {rel}:{lineno} still references old backend host")

    for rel in sorted(LOCAL_ALLOWED_FILES):
        path = root / rel
        lines = _read(path)
        if rel.endswith("check_coze_control_plane_bundle.sh"):
            continue
        for lineno, line in enumerate(lines, start=1):
            if OLD_BACKEND in line:
                failures.append(f"[local-allowed] {rel}:{lineno} should not reference old backend host")

    for rel in sorted(SECOND_WAVE_FILES):
        path = root / rel
        for lineno, line in enumerate(_read(path), start=1):
            if OLD_BACKEND in line:
                print(f"[second-wave] {rel}:{lineno} still points to old backend host")

    for rel in sorted(FIRST_WAVE_FILES | LOCAL_ALLOWED_FILES):
        path = root / rel
        for lineno, line in enumerate(_read(path), start=1):
            if DOCKER_BACKEND in line and rel in FIRST_WAVE_FILES:
                failures.append(f"[first-wave] {rel}:{lineno} leaked host.docker.internal")
            if LOCAL_BACKEND in line and rel in FIRST_WAVE_FILES and "本地" not in line and "local" not in line.lower():
                failures.append(f"[first-wave] {rel}:{lineno} uses 127.0.0.1 without local-dev context")

    if failures:
        for item in failures:
            print(item)
        return 1

    print("host cutover refs check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
