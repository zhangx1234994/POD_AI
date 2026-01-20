#!/usr/bin/env python3
"""Tiny dotenv loader (no external deps).

We avoid importing python-dotenv to keep scripts runnable with system Python.
"""

from __future__ import annotations

from pathlib import Path


def load_dotenv(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}

    env: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        # Strip simple quotes.
        if len(v) >= 2 and ((v[0] == v[-1] == "'") or (v[0] == v[-1] == '"')):
            v = v[1:-1]
        env[k] = v
    return env

