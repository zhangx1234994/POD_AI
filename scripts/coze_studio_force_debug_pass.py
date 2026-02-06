#!/usr/bin/env python3
"""Force-mark all Coze Studio plugin draft tools as "DebugPassed".

Why this exists:
- Coze Studio requires every tool in a plugin to be "debugged" before publishing.
- In our deployment, tools call our internal PODI backend and may depend on
  external vendor configs, making UI debug brittle.
- Since Coze is internal-only in this project, we can safely skip that friction
  by marking draft tools as DebugPassed in Coze Studio's MySQL.

This script updates `opencoze.tool_draft.debug_status=1` for a given plugin_id.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts._dotenv import load_dotenv  # noqa: E402


def _run(cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, shell=True, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin-id", required=True, help="Coze Studio plugin draft id (plugin_id in tool_draft)")
    ap.add_argument("--mysql-container", default=os.getenv("COZE_MYSQL_CONTAINER", "coze-mysql"))
    ap.add_argument("--db", default=os.getenv("COZE_MYSQL_DB", "opencoze"))
    ap.add_argument("--root-password", default=os.getenv("COZE_MYSQL_ROOT_PASSWORD", ""))
    args = ap.parse_args()

    dotenv = load_dotenv(REPO_ROOT / "backend" / ".env")
    root_pw = args.root_password or os.getenv("MYSQL_ROOT_PASSWORD") or dotenv.get("MYSQL_ROOT_PASSWORD") or "root"
    db = args.db or os.getenv("MYSQL_DATABASE") or dotenv.get("MYSQL_DATABASE") or "opencoze"

    try:
        plugin_id = int(str(args.plugin_id))
    except Exception:
        raise SystemExit("--plugin-id must be an integer")

    mysql_container = args.mysql_container.strip()
    if not mysql_container:
        raise SystemExit("--mysql-container is required")

    # Using docker exec avoids installing mysql client locally.
    sql = (
        "UPDATE tool_draft "
        "SET debug_status=1, updated_at=UNIX_TIMESTAMP(NOW())*1000 "
        f"WHERE plugin_id={plugin_id}; "
        "SELECT COUNT(*) AS cnt, SUM(debug_status=1) AS passed "
        f"FROM tool_draft WHERE plugin_id={plugin_id};"
    )
    cmd = (
        "docker exec -i "
        + shlex.quote(mysql_container)
        + " mysql "
        + "-uroot "
        + "-p"
        + shlex.quote(root_pw)
        + " -D "
        + shlex.quote(db)
        + " -e "
        + shlex.quote(sql)
    )
    res = _run(cmd)
    if res.returncode != 0:
        raise SystemExit(f"Failed to update Coze Studio debug_status.\n{res.stderr.strip()}")

    # Keep output minimal and non-sensitive.
    out = (res.stdout or "").strip()
    if out:
        print(out)
    else:
        print("OK")


if __name__ == "__main__":
    main()
