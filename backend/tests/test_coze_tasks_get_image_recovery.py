from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.db import get_session
from app.main import app
from app.models.integration import AbilityInvocationLog, AbilityTask


client = TestClient(app)


def test_tasks_get_recovers_images_from_ability_log_when_success_payload_empty():
    task_id = uuid4().hex
    image_url = "https://oss.example.com/recovered.png"

    with get_session() as session:
        log = AbilityInvocationLog(
            ability_provider="comfyui",
            capability_key="sifang_lianxu",
            ability_name="四方连续",
            status="success",
            source="coze",
            response_payload={"images": [{"ossUrl": image_url}]},
            result_assets=[{"ossUrl": image_url}],
        )
        session.add(log)
        session.flush()
        session.add(
            AbilityTask(
                id=task_id,
                ability_id="comfyui_sifang_lianxu",
                ability_name="四方连续",
                ability_provider="comfyui",
                capability_key="sifang_lianxu",
                status="succeeded",
                log_id=log.id,
                request_payload={"metadata": {"expectedImageCount": 1}},
                result_payload={"status": "succeeded", "texts": [], "images": [], "metadata": {}},
            )
        )
        session.commit()

    response = client.post("/api/coze/podi/tasks/get", json={"taskId": task_id})

    assert response.status_code == 200
    data = response.json()
    assert data["taskStatus"] == "succeeded"
    assert data["imageUrl"] == image_url
    assert data["imageUrls"] == [image_url]


def test_tasks_get_accepts_string_image_urls_in_success_payload():
    task_id = uuid4().hex
    image_url = "https://oss.example.com/string-image.png"

    with get_session() as session:
        session.add(
            AbilityTask(
                id=task_id,
                ability_id="comfyui_sifang_lianxu",
                ability_name="四方连续",
                ability_provider="comfyui",
                capability_key="sifang_lianxu",
                status="succeeded",
                request_payload={"metadata": {"expectedImageCount": 1}},
                result_payload={"status": "succeeded", "texts": [], "images": [image_url], "metadata": {}},
            )
        )
        session.commit()

    response = client.post("/api/coze/podi/tasks/get", json={"taskId": task_id})

    assert response.status_code == 200
    data = response.json()
    assert data["taskStatus"] == "succeeded"
    assert data["imageUrl"] == image_url
    assert data["imageUrls"] == [image_url]


def test_tasks_get_does_not_return_success_when_expected_images_are_not_ready():
    task_id = uuid4().hex

    with get_session() as session:
        session.add(
            AbilityTask(
                id=task_id,
                ability_id="comfyui_sifang_lianxu",
                ability_name="四方连续",
                ability_provider="comfyui",
                capability_key="sifang_lianxu",
                status="succeeded",
                request_payload={"metadata": {"expectedImageCount": 1}},
                result_payload={"status": "succeeded", "texts": [], "images": [], "metadata": {}},
            )
        )
        session.commit()

    response = client.post("/api/coze/podi/tasks/get", json={"taskId": task_id})

    assert response.status_code == 200
    data = response.json()
    assert data["taskStatus"] == "running"
    assert data["debugResponse"] == "RESULT_IMAGES_NOT_READY"
    assert data["imageUrls"] == []
