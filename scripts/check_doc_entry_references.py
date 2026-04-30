#!/usr/bin/env python3
"""Check repository entry documents for broken local path references."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ENTRY_DOCS = [
    Path("AGENTS.md"),
    Path("docs/README.md"),
    Path("docs/strategy/README.md"),
    Path("docs/client/README.md"),
    Path("docs/client/DOC_STATUS.md"),
    Path("docs/client/plans/README.md"),
    Path("docs/client/tech-review-2026-04-16/README.md"),
    Path("docs/handover/README.md"),
    Path("docs/api/INDEX.md"),
    Path("docs/standards/document-maintenance.md"),
]

HISTORICAL_MISSING = {
    "podi-client-web/",
    "podi-client-v2/",
    "podi-design-web-dev/",
    "docs/CREDENTIALS.local.md",
}

CHECK_PREFIXES = (
    "AGENTS.md",
    "config/",
    "docs/",
    "backend/",
    "scripts/",
    "podi-admin-web/",
    "podi-eval-web/",
    "vendor-api-ops/",
    "image-ops-service/",
)

BACKTICK_RE = re.compile(r"`([^`]+)`")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def should_check(target: str) -> bool:
    if not target:
        return False
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return False
    if any(char in target for char in "*{}<>"):
        return False
    if "YYYY" in target:
        return False
    if " " in target:
        return False
    return target.startswith(CHECK_PREFIXES)


def normalize_target(raw: str) -> str:
    target = raw.strip().split("#", 1)[0]
    if target.startswith("./"):
        target = target[2:]
    return target


def iter_targets(text: str):
    for pattern in (BACKTICK_RE, MARKDOWN_LINK_RE):
        for match in pattern.finditer(text):
            target = normalize_target(match.group(1))
            if should_check(target):
                yield target


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing: list[tuple[str, str]] = []

    for doc in ENTRY_DOCS:
        path = root / doc
        if not path.exists():
            missing.append((str(doc), "<entry document missing>"))
            continue

        text = path.read_text(encoding="utf-8")
        for target in sorted(set(iter_targets(text))):
            if target in HISTORICAL_MISSING:
                continue
            target_path = root / target
            exists = target_path.is_dir() if target.endswith("/") else target_path.exists()
            if not exists:
                missing.append((str(doc), target))

    if missing:
        print("[FAIL] Entry document references missing local paths:")
        for doc, target in missing:
            print(f"  - {doc} -> {target}")
        return 1

    print("[OK] Entry document local path references are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
