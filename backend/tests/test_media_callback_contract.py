from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routers.media as media_module
from app.main import app


client = TestClient(app)


def _settings(**overrides):
    values = {
        "oss_bucket": "podi",
        "oss_root_prefix": "uploads",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_oss_callback_accepts_valid_upload(monkeypatch) -> None:
    monkeypatch.setattr(media_module.oss_service, "settings", _settings())

    response = client.post(
        "/api/media/v1/oss-callback",
        json={
            "bucket": "podi",
            "object": "uploads/u1/20260425/input.png",
            "size": 128,
            "mimeType": "image/png",
            "meta": {"taskId": "task_1", "action": "ability-test", "userId": "u1"},
        },
    )

    assert response.status_code == 204


def test_oss_callback_rejects_wrong_bucket(monkeypatch) -> None:
    monkeypatch.setattr(media_module.oss_service, "settings", _settings())

    response = client.post(
        "/api/media/v1/oss-callback",
        json={
            "bucket": "other",
            "object": "uploads/u1/20260425/input.png",
            "size": 128,
            "mimeType": "image/png",
            "meta": {"taskId": "task_1", "action": "ability-test", "userId": "u1"},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "MEDIA_CALLBACK_BUCKET_MISMATCH"


def test_oss_callback_rejects_out_of_scope_object(monkeypatch) -> None:
    monkeypatch.setattr(media_module.oss_service, "settings", _settings())

    response = client.post(
        "/api/media/v1/oss-callback",
        json={
            "bucket": "podi",
            "object": "other/u1/20260425/input.png",
            "size": 128,
            "mimeType": "image/png",
            "meta": {"taskId": "task_1", "action": "ability-test", "userId": "u1"},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "MEDIA_CALLBACK_OBJECT_OUT_OF_SCOPE"
