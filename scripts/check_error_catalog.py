#!/usr/bin/env python3
"""Validate error catalog coverage for backend error codes.

Usage:
  python3 scripts/check_error_catalog.py
"""

from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs/standards/error-catalog.md"
BACKEND_ROOT = ROOT / "backend/app"


IGNORE_EXACT = {
    "ABILITY_TASK_MAX_WORKERS",
    "ADMIN_API_TOKEN",
    "BAIDU_API_KEY",
    "BAIDU_BASE_URL",
    "BAIDU_SECRET_KEY",
    "COZE_API_TOKEN",
    "COZE_BASE_URL",
    "COZE_COMFYUI_CALLBACK_WORKFLOW_ID",
    "COZE_DEFAULT_TIMEOUT",
    "COZE_LOOP_BASE_URL",
    "COZE_TRUSTED_IPS",
    "COMFYUI_DEFAULT_EXECUTOR_ID",
    "COMFYUI_QUEUE_BATCH_SIZE",
    "COMFYUI_ROUTE_BY_QUEUE",
    "EVAL_ADMIN_TOKEN",
    "EVAL_FANOUT_MAX_WORKERS",
    "EVAL_RUN_MAX_WORKERS",
    "EXECUTOR_CONFIG_PATH",
    "KIE_API_KEY",
    "OSS_CALLBACK_HOST",
    "PODI_INTERNAL_BASE_URL",
    "VOLCENGINE_API_KEY",
    "VOLCENGINE_BASE_URL",
}

IGNORE_SUFFIX = (
    "_TOKEN",
    "_BASE_URL",
    "_DEFAULT_TIMEOUT",
    "_MAX_WORKERS",
    "_CONFIG_PATH",
    "_QUEUE_BATCH_SIZE",
    "_ROUTE_BY_QUEUE",
)


def normalize_token(token: str) -> str:
    base = token.split(":", 1)[0]
    for prefix, mapped in (
        ("COMFYUI_HISTORY_HTTP_", "COMFYUI_HISTORY_HTTP_*"),
        ("COMFYUI_STATUS_", "COMFYUI_STATUS_*"),
        ("COZE_RUN_", "COZE_RUN_*"),
        ("COZE_HTTP_", "COZE_HTTP_*"),
        ("VOLCENGINE_HTTP_", "VOLCENGINE_HTTP_*"),
    ):
        if base.startswith(prefix):
            return mapped
    return base


def load_catalog() -> set[str]:
    if not CATALOG_PATH.exists():
        raise SystemExit(f"missing error catalog: {CATALOG_PATH}")
    codes: set[str] = set()
    for line in CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if not parts:
            continue
        code = parts[0].strip("`")
        if code and code != "编号" and not code.startswith("---"):
            codes.add(code)
    return codes


def should_consider(token: str) -> bool:
    if token in IGNORE_EXACT:
        return False
    if token.endswith(IGNORE_SUFFIX):
        return False
    if not re.search(r"[A-Z]", token):
        return False
    return any(
        token.startswith(prefix)
        for prefix in (
            "ABILITY",
            "ADMIN",
            "AUTH",
            "BAIDU",
            "CALLBACK",
            "COMFYUI",
            "COMMERCIAL",
            "COZE",
            "EXECUTOR",
            "FANOUT",
            "IMAGE",
            "INTERNAL_ONLY",
            "INVALID",
            "KIE",
            "PODI",
            "QUEUE",
            "RUN",
            "TASK",
            "UNAUTHORIZED",
            "USER",
            "VOLCENGINE",
            "WORKFLOW",
        )
    )


def scan_errors() -> set[str]:
    tokens: set[str] = set()
    pattern = re.compile(r"[\"']([A-Z0-9_:-]{6,})[\"']")
    context_keywords = ("detail=", "error_message", "message=", "raise HTTPException", "_mark_failed")
    for path in BACKEND_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not any(k in line for k in context_keywords):
                continue
            for match in pattern.findall(line):
                token = normalize_token(match)
                if should_consider(token):
                    tokens.add(token)
    return tokens


def main() -> int:
    catalog = load_catalog()
    tokens = scan_errors()
    missing = sorted(code for code in tokens if code not in catalog)
    if missing:
        print("Missing error codes in catalog:")
        for code in missing:
            print(f"- {code}")
        return 1
    print("Error catalog check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
