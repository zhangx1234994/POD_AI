"""
Quick connectivity check for Aliyun OSS credentials.

Usage:
    source .venv/bin/activate
    export OSS_AK=xxx OSS_SK=xxx OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com OSS_BUCKET=podi
    python scripts/test_oss_connection.py

The script will fetch bucket metadata and optionally create a signed URL so we can
confirm the provided configuration matches the live bucket.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import oss2


@dataclass
class OssConfig:
    access_key: str
    secret_key: str
    endpoint: str
    bucket: str

    @classmethod
    def from_env(cls) -> "OssConfig":
        missing = [var for var in ("OSS_AK", "OSS_SK", "OSS_ENDPOINT", "OSS_BUCKET") if not os.getenv(var)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
        return cls(
            access_key=os.environ["OSS_AK"],
            secret_key=os.environ["OSS_SK"],
            endpoint=os.environ["OSS_ENDPOINT"],
            bucket=os.environ["OSS_BUCKET"],
        )


def check_bucket(config: OssConfig) -> dict[str, str]:
    auth = oss2.Auth(config.access_key, config.secret_key)
    bucket = oss2.Bucket(auth, f"https://{config.endpoint}", config.bucket)
    info = bucket.get_bucket_info()
    return {
        "name": info.name,
        "region": info.location,
        "storage_class": info.storage_class,
        "extranet_endpoint": info.extranet_endpoint,
        "intranet_endpoint": info.intranet_endpoint,
    }


def main() -> None:
    try:
        cfg = OssConfig.from_env()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1)

    metadata = check_bucket(cfg)
    print("OSS bucket connectivity OK:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
