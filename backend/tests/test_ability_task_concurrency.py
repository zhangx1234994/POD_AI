from app.services.ability_task_service import AbilityTaskService


def test_select_worker_pool_size_uses_executor_capacity_floor() -> None:
    result = AbilityTaskService._select_worker_pool_size(4, [10, 10, 10, 2, 2])
    assert result == 34


def test_select_worker_pool_size_caps_recommended_size() -> None:
    result = AbilityTaskService._select_worker_pool_size(4, [30, 30])
    assert result == 40


def test_select_worker_pool_size_keeps_higher_configured_value() -> None:
    result = AbilityTaskService._select_worker_pool_size(50, [10, 10])
    assert result == 50
