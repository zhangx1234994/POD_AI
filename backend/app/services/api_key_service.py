"""API Key acquisition and rotation logic."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.core.db import get_session
from app.models.integration import ApiKey


class ApiKeyService:
    """Simple round-robin acquisition for provider API keys."""

    def acquire(self, provider: str | None) -> Optional[ApiKey]:
        """Fetch an active key for the given provider and bump usage count."""
        if not provider:
            return None

        with get_session() as session:
            stmt = (
                select(ApiKey)
                .where(ApiKey.provider == provider, ApiKey.status == "active")
                .order_by(ApiKey.usage_count.asc(), ApiKey.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            api_key = session.execute(stmt).scalars().first()
            if not api_key:
                return None

            api_key.usage_count += 1
            if api_key.daily_quota and api_key.usage_count >= api_key.daily_quota:
                api_key.status = "exhausted"
                api_key.extra_metadata = (api_key.extra_metadata or {}) | {
                    "exhausted_at": datetime.utcnow().isoformat()
                }

            session.add(api_key)
            session.commit()
            session.refresh(api_key)
            return api_key


api_key_service = ApiKeyService()
