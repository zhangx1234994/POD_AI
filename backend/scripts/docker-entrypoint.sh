#!/usr/bin/env bash
set -euo pipefail

export TZ="${TZ:-Asia/Shanghai}"

echo "[backend] starting (TZ=$TZ)"

# Best-effort DB wait + migration. This makes "pull + docker compose up" reliable.
python - <<'PY'
import os
import time
from sqlalchemy import text
from sqlalchemy.engine import create_engine
from app.core.config import get_settings

db = get_settings().database_url

engine = create_engine(db, pool_pre_ping=True)
deadline = time.time() + 60
last = None
while time.time() < deadline:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        last = None
        break
    except Exception as e:
        last = e
        time.sleep(2)

if last is not None:
    raise SystemExit(f"database not ready after 60s: {last}")
PY

echo "[backend] running alembic migrations..."
alembic upgrade head

echo "[backend] launching uvicorn on 0.0.0.0:8099"
exec uvicorn app.main:app --host 0.0.0.0 --port 8099
