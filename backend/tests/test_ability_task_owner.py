from types import SimpleNamespace

from app.services.ability_task_service import AbilityTaskService


def test_serialize_task_owner_keeps_normal_user_id() -> None:
    user = SimpleNamespace(id="user_123", username="alice")

    user_id, user_name = AbilityTaskService._serialize_task_owner(user)

    assert user_id == "user_123"
    assert user_name == "alice"


def test_serialize_task_owner_ignores_service_user_fk() -> None:
    user = SimpleNamespace(id="service", username=None)

    user_id, user_name = AbilityTaskService._serialize_task_owner(user)

    assert user_id is None
    assert user_name is None


def test_serialize_task_owner_ignores_business_api_key_fake_user_fk() -> None:
    user = SimpleNamespace(id="business-api-key:biz_key_fission_partner_20260512", username="业务方图裂变测试 Key")

    user_id, user_name = AbilityTaskService._serialize_task_owner(user)

    assert user_id is None
    assert user_name == "业务方图裂变测试 Key"
