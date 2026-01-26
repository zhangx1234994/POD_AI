#!/usr/bin/env python3
"""DB migration helper (safe by default).

Why this exists:
- Some environments have an old Alembic `version_num` that no longer exists in this repo
  (e.g. `Can't locate revision identified by '04bdaedd4ed9'`).
- In that case, `alembic upgrade head` will be blocked until the DB is "stamped" to the
  closest known base revision.

Usage (recommended on the backend host where MySQL is reachable):
  - python3 backend/scripts/db_upgrade.py --check
  - python3 backend/scripts/db_upgrade.py --repair-and-upgrade

The repair action is *destructive to migration history only* (it does NOT drop tables),
but it should still be done intentionally by an operator.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


KNOWN_BASE_REVISION = "dc175558f682"


def _run(*cmd: str) -> tuple[int, str]:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, (proc.stdout or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Only print current/head revisions")
    parser.add_argument(
        "--repair-and-upgrade",
        action="store_true",
        help=f"If current revision is unknown, stamp to {KNOWN_BASE_REVISION} then upgrade head",
    )
    args = parser.parse_args()

    # Prefer venv alembic if present, otherwise fall back to `python -m alembic`.
    alembic = "backend/.venv/bin/alembic"
    if _run("bash", "-lc", f"test -x {alembic}")[0] != 0:
        alembic = "python3 -m alembic"

    def sh(command: str) -> tuple[int, str]:
        return _run("bash", "-lc", f"cd backend && {command}")

    code, out = sh(f"{alembic} heads")
    print("alembic heads:")
    print(out or f"(exit={code})")
    print()

    code, out = sh(f"{alembic} current")
    if code == 0:
        print("alembic current:")
        print(out)
    else:
        print("alembic current failed:")
        print(out)

    if args.check and not args.repair_and_upgrade:
        return 0

    if args.repair_and_upgrade:
        if "Can't locate revision identified by" in out:
            print()
            print(f"Repair: stamping DB to known base revision {KNOWN_BASE_REVISION} ...")
            code, stamp_out = sh(f"{alembic} stamp {KNOWN_BASE_REVISION}")
            print(stamp_out)
            if code != 0:
                return code
        print()
        print("Upgrading DB to head ...")
        code, up_out = sh(f"{alembic} upgrade head")
        print(up_out)
        return code

    print()
    print("No action requested. Use --check or --repair-and-upgrade.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

