#!/usr/bin/env python3
"""Quick manual test for PODI expand_mask_color utility.

Reads a sample image from the repo (folder: 提取测试图), expands canvas with magenta,
and writes a preview PNG under `tmp/` (not committed).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.services.podi_image_tools import expand_with_color


def main() -> int:
    src_dir = REPO / "提取测试图"
    if not src_dir.exists():
        raise SystemExit(f"missing folder: {src_dir}")
    candidates = sorted([p for p in src_dir.iterdir() if p.suffix.lower() in {'.png', '.jpg', '.jpeg'}])
    if not candidates:
        raise SystemExit(f"no images found in: {src_dir}")
    src = candidates[0]
    img = src.read_bytes()

    out = expand_with_color(
        image_bytes=img,
        expand_left=120,
        expand_right=80,
        expand_top=60,
        expand_bottom=40,
    )
    out_dir = REPO / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "expand_mask_preview.png"
    out_path.write_bytes(out)
    print(f"ok: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
