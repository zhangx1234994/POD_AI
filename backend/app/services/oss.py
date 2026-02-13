"""封装 OSS / STS 行为，支持本地和云端上传。"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import oss2
from aliyunsdkcore.client import AcsClient
from aliyunsdksts.request.v20150401.AssumeRoleRequest import AssumeRoleRequest

from app.core.config import get_settings


class OssService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._bucket_host = f"https://{self.settings.oss_bucket}.{self.settings.oss_region}.aliyuncs.com"
        self._public_domain = (
            self.settings.oss_public_domain or self.settings.download_domain or self._bucket_host
        )
        self._sts_client = self._build_sts_client()
        self._logger = logging.getLogger(__name__)
        self._bucket_client: oss2.Bucket | None = None
        self._connect_timeout = max(5, int(self.settings.oss_connect_timeout or 120))
        self._upload_retries = max(1, int(self.settings.oss_upload_retries or 1))
        self._resumable_threshold = max(1, int(self.settings.oss_resumable_threshold_mb or 8)) * 1024 * 1024
        self._resumable_part_size = max(1, int(self.settings.oss_resumable_part_size_mb or 8)) * 1024 * 1024
        self._resumable_threads = max(1, int(self.settings.oss_resumable_threads or 1))

    def _build_sts_client(self) -> AcsClient | None:
        if not (self.settings.oss_access_key and self.settings.oss_secret_key and self.settings.oss_role_arn):
            return None
        region = self.settings.oss_region
        if region.startswith("oss-"):
            region = region.replace("oss-", "", 1)
        return AcsClient(self.settings.oss_access_key, self.settings.oss_secret_key, region)

    def _assume_role(self, *, session_name: str, object_prefix: str) -> dict[str, Any] | None:
        if not self._sts_client or not self.settings.oss_role_arn:
            return None
        request = AssumeRoleRequest()
        request.set_accept_format("json")
        request.set_RoleArn(self.settings.oss_role_arn)
        request.set_DurationSeconds(min(max(self.settings.oss_sts_duration, 300), 3600))
        request.set_RoleSessionName(session_name[:64])
        policy = {
            "Version": "1",
            "Statement": [
                {
                    "Action": ["oss:PutObject", "oss:PostObject"],
                    "Effect": "Allow",
                    "Resource": [
                        f"acs:oss:*:*:{self.settings.oss_bucket}",
                        f"acs:oss:*:*:{self.settings.oss_bucket}/{object_prefix}*",
                    ],
                }
            ],
        }
        request.set_Policy(json.dumps(policy))
        response = self._sts_client.do_action_with_exception(request)
        return json.loads(response)["Credentials"]

    def build_object_key(self, *, user_id: str, original_name: str) -> str:
        suffix = Path(original_name).suffix or ".bin"
        rand = secrets.token_hex(4)
        date_str = datetime.utcnow().strftime("%Y%m%d")
        prefix = self.settings.oss_root_prefix.strip("/")
        user_part = (user_id or "anonymous").strip("/")
        segments = [segment for segment in [prefix, user_part, date_str] if segment]
        object_dir = "/".join(segments)
        return f"{object_dir}/{rand}-{int(datetime.utcnow().timestamp())}{suffix}"

    def generate_upload_credentials(self, *, user_id: str, file_name: str) -> dict[str, Any]:
        object_key = self.build_object_key(user_id=user_id, original_name=file_name)
        session_name = f"podi-{user_id or 'anonymous'}"
        prefix = self.settings.oss_root_prefix.strip("/")
        user_segment = (user_id or "anonymous").strip("/")
        composed = "/".join(filter(None, [prefix, user_segment]))
        object_prefix = f"{composed}/" if composed else ""
        try:
            credentials = self._assume_role(session_name=session_name, object_prefix=object_prefix)
        except Exception as exc:  # pylint: disable=broad-except
            self._logger.warning("AssumeRole failed, fallback to base credentials: %s", exc)
            credentials = None
        if credentials:
            expire_at = datetime.strptime(credentials["Expiration"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            expiration = int(expire_at.timestamp() * 1000)
            payload = {
                "accessKeyId": credentials["AccessKeyId"],
                "accessKeySecret": credentials["AccessKeySecret"],
                "securityToken": credentials["SecurityToken"],
                "endpoint": self.settings.oss_endpoint,
                "publicDomain": self._public_domain.rstrip("/"),
                "bucket": self.settings.oss_bucket,
                "region": self.settings.oss_region,
                "expiration": expiration,
                "isTemporary": True,
                "rootPrefix": self.settings.oss_root_prefix,
            }
        else:
            expire_at = datetime.utcnow() + timedelta(seconds=600)
            expiration = int(expire_at.timestamp() * 1000)
            payload = {
                "accessKeyId": self.settings.oss_access_key or "",
                "accessKeySecret": self.settings.oss_secret_key or "",
                "securityToken": "",
                "endpoint": self.settings.oss_endpoint,
                "publicDomain": self._public_domain.rstrip("/"),
                "bucket": self.settings.oss_bucket,
                "region": self.settings.oss_region,
                "expiration": expiration,
                "isTemporary": False,
                "rootPrefix": self.settings.oss_root_prefix,
            }
        return {
            "ossCredentials": payload,
            "objectKey": object_key,
            "host": self._bucket_host,
        }

    def sign_download_url(self, object_key: str, ttl: int) -> str:
        expires = int((datetime.utcnow() + timedelta(seconds=ttl)).timestamp())
        return f"{self._public_domain}/{object_key}?token=mock&expires={expires}"

    def _get_bucket(self) -> oss2.Bucket:
        if self._bucket_client is not None:
            return self._bucket_client
        if not (self.settings.oss_access_key and self.settings.oss_secret_key):
            raise RuntimeError("OSS_ACCESS_KEY / OSS_SECRET_KEY 未配置，无法直接上传")
        endpoint = self.settings.oss_endpoint
        if not endpoint.startswith("http"):
            endpoint = f"https://{endpoint}"
        auth = oss2.Auth(self.settings.oss_access_key, self.settings.oss_secret_key)
        self._bucket_client = oss2.Bucket(
            auth,
            endpoint,
            self.settings.oss_bucket,
            connect_timeout=self._connect_timeout,
        )
        return self._bucket_client

    def upload_bytes(
        self,
        *,
        user_id: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        object_key = self.build_object_key(user_id=user_id or "system", original_name=filename)
        bucket = self._get_bucket()
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        size = len(data)
        use_resumable = size >= self._resumable_threshold

        def _should_retry(exc: Exception) -> bool:
            if isinstance(exc, oss2.exceptions.ServerError):
                return exc.status >= 500 or exc.status in {408, 429}
            if isinstance(exc, oss2.exceptions.RequestError):
                return True
            if isinstance(exc, TimeoutError):
                return True
            if isinstance(exc, OSError):
                return True
            return False

        def _sleep_for(attempt: int) -> None:
            base = 0.6
            delay = base * (2 ** attempt)
            time.sleep(min(6, delay))

        last_exc: Exception | None = None
        for attempt in range(self._upload_retries):
            try:
                if use_resumable:
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp.write(data)
                        tmp.flush()
                        os.fsync(tmp.fileno())
                        tmp_path = tmp.name
                    try:
                        oss2.resumable_upload(
                            bucket,
                            object_key,
                            tmp_path,
                            headers=headers or None,
                            multipart_threshold=self._resumable_part_size,
                            part_size=self._resumable_part_size,
                            num_threads=self._resumable_threads,
                        )
                    finally:
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
                else:
                    bucket.put_object(object_key, data, headers=headers or None)
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 - we re-raise if retry fails
                last_exc = exc
                if attempt >= self._upload_retries - 1 or not _should_retry(exc):
                    break
                self._logger.warning(
                    "OSS upload failed, retrying (%s/%s) object=%s size=%s err=%s",
                    attempt + 1,
                    self._upload_retries,
                    object_key,
                    size,
                    exc,
                )
                _sleep_for(attempt)
        if last_exc is not None:
            raise last_exc
        encoded_key = quote(object_key, safe="/")
        url = f"{self._public_domain.rstrip('/')}/{encoded_key}"
        return {
            "bucket": self.settings.oss_bucket,
            "objectKey": object_key,
            "url": url,
            "contentType": content_type,
        }


oss_service = OssService()
