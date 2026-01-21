#!/usr/bin/env python3
"""Quick manual test for PODI set_dpi + upscale_resize utils.

Writes previews under `tmp/` (not committed).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.services.podi_image_tools import set_dpi, upscale_resize  # noqa: E402


def _pick_image() -> Path:
    src_dir = REPO / "提取测试图"
    candidates = sorted([p for p in src_dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}])
    if not candidates:
        raise SystemExit("no test images found")
    return candidates[0]


def main() -> int:
    src = _pick_image()
    raw = src.read_bytes()

    out_dir = REPO / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    dpi_bytes, _, dpi_ext = set_dpi(image_bytes=raw, dpi=300)
    dpi_path = out_dir / f"set_dpi_300{dpi_ext}"
    dpi_path.write_bytes(dpi_bytes)

    up_bytes, _, up_ext = upscale_resize(image_bytes=raw, max_long_edge=2048, output_format="png")
    up_path = out_dir / f"upscale_2048{up_ext}"
    up_path.write_bytes(up_bytes)

    print(f"ok: wrote {dpi_path}")
    print(f"ok: wrote {up_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

