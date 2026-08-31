from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import app.main as main_module


def test_backend_startup_synchronizes_catalog_before_business_and_workers(monkeypatch) -> None:
    """backend 每次启动都应按外键依赖同步目录，确保下线配置无需人工执行 UPDATE SQL。"""

    calls: list[str] = []

    @contextmanager
    def fake_get_session():
        """启动顺序测试不访问真实数据库，只提供可识别的会话占位对象。"""

        yield object()

    def record_seed(name: str):
        """生成 seed 记录函数，便于直接断言启动时的实际调用顺序。"""

        def _record(_session) -> bool:
            """记录单个 seed 名称并模拟无需更新数据库。"""

            calls.append(name)
            return False

        return _record

    monkeypatch.setattr(main_module, "get_session", fake_get_session)
    monkeypatch.setattr(main_module, "ensure_default_executors", record_seed("executors"))
    monkeypatch.setattr(main_module, "ensure_default_workflows", record_seed("workflows"))
    monkeypatch.setattr(main_module, "ensure_default_bindings", record_seed("bindings"))
    monkeypatch.setattr(main_module, "ensure_default_abilities", record_seed("abilities"))
    monkeypatch.setattr(main_module, "ensure_default_business_capabilities", record_seed("business"))
    monkeypatch.setattr(
        main_module,
        "get_background_worker_decision",
        lambda: SimpleNamespace(enabled=False, reason="startup-seed-test"),
    )

    app = main_module.create_app()
    startup_handler = next(handler for handler in app.router.on_startup if handler.__name__ == "_warmup_services")
    startup_handler()

    assert calls == ["executors", "workflows", "bindings", "abilities", "business"]
