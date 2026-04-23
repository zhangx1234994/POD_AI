from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

_MINIMAL_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8B9l8AAAAASUVORK5CYII="
)


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_requires_token_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_OPS_SERVICE_TOKEN", "secret")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post("/internal/image-ops/set-dpi", json={"imageBase64": "abc", "params": {"dpi": 300}})
    assert response.status_code == 401
    assert response.json()["detail"] == "IMAGE_OPS_UNAUTHORIZED"
    get_settings.cache_clear()


def test_upscale_resize_contract(monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_OPS_SERVICE_TOKEN", "secret")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post(
        "/internal/image-ops/upscale-resize",
        headers={"Authorization": "Bearer secret"},
        json={
            "imageBase64": base64.b64encode(_MINIMAL_PNG_BYTES).decode("utf-8"),
            "params": {"max_long_edge": 64, "output_format": "png"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contentType"] == "image/png"
    assert data["fileExt"] == ".png"
    assert isinstance(data["contentBase64"], str) and data["contentBase64"]
    get_settings.cache_clear()
