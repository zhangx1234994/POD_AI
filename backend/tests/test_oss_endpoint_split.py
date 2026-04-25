from __future__ import annotations

from types import SimpleNamespace

from app.services import oss as oss_module


def _settings(**overrides):
    values = {
        "oss_access_key": "ak",
        "oss_secret_key": "sk",
        "oss_role_arn": None,
        "oss_bucket": "podi",
        "oss_region": "oss-cn-hangzhou",
        "oss_endpoint": "oss-cn-hangzhou.aliyuncs.com",
        "oss_internal_endpoint": "oss-cn-hangzhou-internal.aliyuncs.com",
        "oss_public_domain": "https://podi.oss-cn-hangzhou.aliyuncs.com",
        "download_domain": "https://fallback.example.com",
        "oss_root_prefix": "uploads",
        "oss_sts_duration": 900,
        "oss_connect_timeout": 30,
        "oss_upload_retries": 1,
        "oss_resumable_threshold_mb": 8,
        "oss_resumable_part_size_mb": 8,
        "oss_resumable_threads": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_browser_upload_credentials_keep_public_oss_endpoint(monkeypatch):
    monkeypatch.setattr(oss_module, "get_settings", lambda: _settings())

    service = oss_module.OssService()
    credentials = service.generate_upload_credentials(user_id="u1", file_name="a.png")

    assert credentials["ossCredentials"]["endpoint"] == "oss-cn-hangzhou.aliyuncs.com"
    assert credentials["ossCredentials"]["publicDomain"] == "https://podi.oss-cn-hangzhou.aliyuncs.com"


def test_backend_bucket_prefers_internal_endpoint(monkeypatch):
    captured = {}

    def fake_bucket(auth, endpoint, bucket_name, connect_timeout):  # noqa: ANN001
        captured.update(
            {
                "endpoint": endpoint,
                "bucket_name": bucket_name,
                "connect_timeout": connect_timeout,
            }
        )
        return object()

    monkeypatch.setattr(oss_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(oss_module.oss2, "Bucket", fake_bucket)

    service = oss_module.OssService()
    service._get_bucket()

    assert captured == {
        "endpoint": "https://oss-cn-hangzhou-internal.aliyuncs.com",
        "bucket_name": "podi",
        "connect_timeout": 30,
    }


def test_backend_bucket_falls_back_to_public_endpoint(monkeypatch):
    captured = {}

    def fake_bucket(auth, endpoint, bucket_name, connect_timeout):  # noqa: ANN001
        captured["endpoint"] = endpoint
        return object()

    monkeypatch.setattr(oss_module, "get_settings", lambda: _settings(oss_internal_endpoint=None))
    monkeypatch.setattr(oss_module.oss2, "Bucket", fake_bucket)

    service = oss_module.OssService()
    service._get_bucket()

    assert captured["endpoint"] == "https://oss-cn-hangzhou.aliyuncs.com"
