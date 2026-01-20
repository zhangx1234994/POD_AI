#!/usr/bin/env python3
"""Ensure a fixed "bridge" admin user exists in PODI backend.

This user is meant for internal single-host integration/testing, not for public exposure.
Credentials are read from environment:
  - BRIDGE_USERNAME       (alias)
  - BRIDGE_EMAIL          (alias)
  - BRIDGE_PASSWORD       (alias)
  - BRIDGE_ADMIN_USERNAME (default: bridge_admin)
  - BRIDGE_ADMIN_EMAIL    (default: bridge@podi.local)
  - BRIDGE_ADMIN_PASSWORD (required; set it yourself)
"""

from __future__ import annotations

import os
import uuid

from sqlalchemy import select

from app.core.db import get_session
from app.models.user import User
from app.services.auth_service import auth_service


def main() -> None:
    username = os.getenv("BRIDGE_USERNAME") or os.getenv("BRIDGE_ADMIN_USERNAME", "bridge_admin")
    email = os.getenv("BRIDGE_EMAIL") or os.getenv("BRIDGE_ADMIN_EMAIL", "bridge@podi.local")
    password = os.getenv("BRIDGE_PASSWORD") or os.getenv("BRIDGE_ADMIN_PASSWORD")

    username = username.strip()
    email = email.strip()
    if not password or not password.strip():
        raise SystemExit("BRIDGE_PASSWORD/BRIDGE_ADMIN_PASSWORD is required (refuse to create a user without an explicit password)")

    with get_session() as session:
        existing = session.execute(
            select(User).where((User.username == username) | (User.email == email))
        ).scalars().first()
        if existing:
            # Ensure admin role for the bridge account.
            changed = False
            if existing.role != "admin":
                existing.role = "admin"
                changed = True
            if existing.status != "active":
                existing.status = "active"
                changed = True
            session.add(existing)
            if changed:
                session.commit()
            print(f"bridge admin exists: username={existing.username} email={existing.email} role={existing.role}")
            return

        user = User(
            id=uuid.uuid4().hex,
            email=email,
            username=username,
            password_hash=auth_service.hash_password(password.strip()),
            role="admin",
            status="active",
        )
        session.add(user)
        session.commit()
        print(f"bridge admin created: username={username} email={email}")


if __name__ == "__main__":
    main()
