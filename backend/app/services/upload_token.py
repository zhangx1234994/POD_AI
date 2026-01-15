"""上传密钥服务：为前端签发/校验用户级别的上传口令。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings


class UploadTokenService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._secret = self.settings.upload_token_secret
        self._ttl_seconds = max(300, int(self.settings.upload_token_ttl))

    def issue_token(self, *, user_id: str) -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        payload = {
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "scope": "upload",
        }
        token = jwt.encode(payload, self._secret, algorithm="HS256")
        return {
            "uploadKey": token,
            "expiresAt": expires_at.isoformat(),
            "expiresIn": self._ttl_seconds,
        }

    def verify_token(self, token: str) -> str:
        decoded = jwt.decode(token, self._secret, algorithms=["HS256"])
        if decoded.get("scope") != "upload":
            raise jwt.InvalidTokenError("Invalid scope")
        return str(decoded["sub"])


upload_token_service = UploadTokenService()
