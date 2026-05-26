from types import SimpleNamespace

from app.core.db import _engine_options_from_settings


def test_engine_options_use_explicit_pool_settings_for_mysql() -> None:
    options = _engine_options_from_settings(
        SimpleNamespace(
            database_url="mysql+pymysql://user:pass@127.0.0.1:3306/podi",
            database_pool_size=30,
            database_max_overflow=15,
            database_pool_timeout=12,
            database_pool_recycle=900,
        )
    )

    assert options["pool_pre_ping"] is True
    assert options["pool_size"] == 30
    assert options["max_overflow"] == 15
    assert options["pool_timeout"] == 12
    assert options["pool_recycle"] == 900


def test_engine_options_skip_pool_settings_for_sqlite_memory() -> None:
    options = _engine_options_from_settings(
        SimpleNamespace(
            database_url="sqlite+pysqlite:///:memory:",
            database_pool_size=30,
            database_max_overflow=15,
            database_pool_timeout=12,
            database_pool_recycle=900,
        )
    )

    assert options == {"echo": False, "future": True, "pool_pre_ping": True}
