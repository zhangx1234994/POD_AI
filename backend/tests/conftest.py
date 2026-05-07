import os
import sys
import tempfile
from pathlib import Path


# Allow `from app...` imports when running tests from repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Keep broad test runs self-contained. Individual tests can still monkeypatch
# database/session dependencies when they need tighter isolation.
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+pysqlite:///{Path(tempfile.gettempdir()) / 'podi_backend_tests.db'}",
)
os.environ.setdefault("SERVICE_API_TOKEN", "podi-test-service-token")
os.environ.setdefault("COZE_TRUSTED_IPS", "testclient")
os.environ.setdefault("EVAL_ADMIN_TOKEN", "podi-test-eval-admin-token")


def pytest_sessionstart(session):  # noqa: ANN001
    # Import all model modules before create_all so SQLAlchemy metadata contains
    # every table used by OpenAPI seed helpers and lightweight API contract tests.
    from app import models as _models  # noqa: F401, PLC0415
    from app.models import agent_management as _agent_management  # noqa: F401, PLC0415
    from app.models import eval as _eval_models  # noqa: F401, PLC0415
    from app.models import integration as _integration  # noqa: F401, PLC0415
    from app.models import task as _task  # noqa: F401, PLC0415
    from app.models import user as _user  # noqa: F401, PLC0415
    from app.models import wallet as _wallet  # noqa: F401, PLC0415
    from app.core.db import Base, engine  # noqa: PLC0415

    Base.metadata.create_all(bind=engine)
