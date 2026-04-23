#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


DEFAULT_PATTERNS = [
    r"117\.50\.80\.158:8099",
    r"127\.0\.0\.1:8099",
    r"host\.docker\.internal",
    r"<podi-backend-host>",
]


def _collect_matches(root: Path, patterns: list[str]) -> list[tuple[str, int, str]]:
    compiled = [re.compile(pattern) for pattern in patterns]
    results: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {"node_modules", "dist", ".git", "__pycache__"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in compiled):
                results.append((str(path.relative_to(root)), lineno, line.strip()))
    return results


def _collect_toolbox_routes(router_file: Path) -> list[tuple[str, str]]:
    text = router_file.read_text(encoding="utf-8")
    pairs: list[tuple[str, str]] = []
    pattern = re.compile(
        r'@router\.get\("(/comfyui/execute/[^"]+/openapi\.json)"\).*?allowed = \{\s+"(/api/coze/podi/tools/comfyui/[^"]+)"',
        re.S,
    )
    for match in pattern.finditer(text):
        pairs.append((f"/api/coze/podi{match.group(1)}", match.group(2)))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect current Coze migration inventory from repo.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--output", default="", help="Optional markdown output path.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    router_file = root / "backend/app/routers/coze_podi_plugin.py"
    matches = _collect_matches(root, DEFAULT_PATTERNS)
    toolbox_pairs = _collect_toolbox_routes(router_file)

    lines: list[str] = []
    lines.append("# Coze 迁移 inventory 快照")
    lines.append("")
    lines.append("## 1. 单功能 toolbox")
    lines.append("")
    for openapi_path, tool_path in toolbox_pairs:
        lines.append(f"- `{openapi_path}` -> `{tool_path}`")
    lines.append("")
    lines.append("## 2. Host 引用命中")
    lines.append("")
    for rel_path, lineno, line in matches:
        lines.append(f"- `{rel_path}:{lineno}` {line}")
    text = "\n".join(lines) + "\n"

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
