#!/usr/bin/env python3
"""Initialize wallet accounts for users missing wallet rows.

Usage:
  python3 backend/scripts/init_wallet_accounts.py --dry-run
  python3 backend/scripts/init_wallet_accounts.py --apply
  python3 backend/scripts/init_wallet_accounts.py --apply --default-balance 500
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "backend")

from sqlalchemy import select

from app.core.db import get_session
from app.models.user import User
from app.models.wallet import WalletAccount


def run(*, apply: bool, default_balance: int, include_inactive: bool) -> tuple[int, int]:
    with get_session() as session:
        user_stmt = select(User.id)
        if not include_inactive:
            user_stmt = user_stmt.where(User.status == "active")
        user_ids = [str(row[0]) for row in session.execute(user_stmt).all()]
        existing_user_ids = {
            str(row[0]) for row in session.execute(select(WalletAccount.user_id).where(WalletAccount.user_id.in_(user_ids)))
        }
        missing = [user_id for user_id in user_ids if user_id not in existing_user_ids]
        created = 0
        if apply:
            for user_id in missing:
                session.add(
                    WalletAccount(
                        user_id=user_id,
                        balance=default_balance,
                        frozen_balance=0,
                        currency="CNY",
                        status="active",
                    )
                )
                created += 1
            session.commit()
    return len(missing), created


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize missing wallet accounts.")
    parser.add_argument("--apply", action="store_true", help="Write rows to DB. Default is dry-run mode.")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode (default behavior).")
    parser.add_argument(
        "--default-balance",
        type=int,
        default=500,
        help="Default points for newly created wallets.",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Also initialize wallets for inactive users.",
    )
    args = parser.parse_args()

    apply = bool(args.apply and not args.dry_run)
    missing_count, created_count = run(
        apply=apply,
        default_balance=max(0, int(args.default_balance)),
        include_inactive=bool(args.include_inactive),
    )

    print("[wallet-init]")
    print(f"- mode: {'apply' if apply else 'dry-run'}")
    print(f"- missing_users: {missing_count}")
    print(f"- created_wallets: {created_count}")
    if not apply:
        print("- hint: rerun with --apply to write rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
