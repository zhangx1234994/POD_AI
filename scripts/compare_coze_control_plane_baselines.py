#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_summary(path: Path) -> dict:
    if path.is_dir():
        path = path / "summary.json"
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two Coze control-plane baseline summaries.")
    parser.add_argument("--before", required=True, help="Before baseline dir or summary.json")
    parser.add_argument("--after", required=True, help="After baseline dir or summary.json")
    args = parser.parse_args()

    before = load_summary(Path(args.before))
    after = load_summary(Path(args.after))

    keys = [
        "backendHealthLoaded",
        "imageOpsHealthLoaded",
        "abilityCount",
        "evalWorkflowCount",
        "listeningPortsCaptured",
    ]

    diffs = []
    for key in keys:
        if before.get(key) != after.get(key):
            diffs.append(
                {
                    "field": key,
                    "before": before.get(key),
                    "after": after.get(key),
                }
            )

    result = {
        "before": before,
        "after": after,
        "diffCount": len(diffs),
        "diffs": diffs,
        "status": "ok" if not diffs else "changed",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
