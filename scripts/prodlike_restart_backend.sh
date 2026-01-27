#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
backend_dir="$root_dir/backend"
log_dir="$root_dir/logs"
log_file="$log_dir/backend-8099.log"

mkdir -p "$log_dir"

echo "[prodlike] stopping backend (8099)..."
pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8099" 2>/dev/null || true
pkill -f "uvicorn app.main:app --host 127.0.0.1 --port 8099" 2>/dev/null || true

python_bin="${PYTHON_BIN:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "[prodlike] ERROR: python3 not found"
  exit 1
fi

if [ ! -x "$backend_dir/.venv/bin/python" ]; then
  echo "[prodlike] creating backend venv..."
  "$python_bin" -m venv "$backend_dir/.venv"
fi

echo "[prodlike] installing backend deps..."
"$backend_dir/.venv/bin/pip" install --upgrade pip >/dev/null
"$backend_dir/.venv/bin/pip" install -e "$backend_dir" >/dev/null

echo "[prodlike] running migrations..."
(cd "$backend_dir" && "$backend_dir/.venv/bin/alembic" upgrade head)

echo "[prodlike] starting backend..."
nohup bash -lc "cd \"$backend_dir\" && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099" >"$log_file" 2>&1 &
echo $! > "$root_dir/backend_uvicorn.pid"

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:8099/health" >/dev/null 2>&1; then
    echo "[prodlike] backend OK"
    exit 0
  fi
  sleep 1
done

echo "[prodlike] backend FAILED (see $log_file)"
exit 1

