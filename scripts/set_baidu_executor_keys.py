#!/usr/bin/env python3
"""Set Baidu executor credentials in PODI DB (internal-only convenience).

We avoid committing secrets into the repo by prompting interactively and storing
them into the `executors.config` for the Baidu executor.
"""

from __future__ import annotations

import sys
import os
from getpass import getpass

REPO_ROOT = __file__.rsplit("/", 2)[0]
sys.path.insert(0, REPO_ROOT + "/backend")

from app.core.db import get_session  # noqa: E402
from app.models.integration import Executor  # noqa: E402


def main() -> None:
    executor_id = "executor_baidu_image_default"
    # Prefer env vars for automation; fallback to interactive prompts.
    api_key = (os.getenv("BAIDU_API_KEY") or "").strip() or input("Baidu API Key: ").strip()
    secret_key = (os.getenv("BAIDU_SECRET_KEY") or "").strip() or getpass("Baidu Secret Key: ").strip()
    if not api_key or not secret_key:
        raise SystemExit("Both API Key and Secret Key are required.")

    with get_session() as session:
        ex = session.get(Executor, executor_id)
        if not ex:
            raise SystemExit(f"Executor not found: {executor_id}")
        cfg = dict(ex.config or {})
        cfg["apiKey"] = api_key
        cfg["secretKey"] = secret_key
        ex.config = cfg
        session.add(ex)
        session.commit()

    # Don't print secrets; only confirm lengths.
    print(f"Updated {executor_id}: apiKey_len={len(api_key)} secretKey_len={len(secret_key)}")


if __name__ == "__main__":
    main()
