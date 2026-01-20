#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
backend_dir="$root_dir/backend"
log_dir="$root_dir/logs"
log_file="$log_dir/backend-8099.log"

mkdir -p "$log_dir"

echo "Stopping backend (port 8099)..."
pkill -f "uvicorn app.main:app --host 127.0.0.1 --port 8099" 2>/dev/null || true

if [ ! -x "$backend_dir/.venv/bin/python" ]; then
  echo "Creating backend venv..."
  /opt/homebrew/bin/python3.11 -m venv "$backend_dir/.venv"
fi

echo "Starting backend..."
# Bind to 0.0.0.0 so Coze containers (Lima VM) can reach the host backend via host.docker.internal.
nohup bash -lc "cd \"$backend_dir\" && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099 --reload" >"$log_file" 2>&1 &
echo $! > "$root_dir/backend_uvicorn.pid"

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8099/health" >/dev/null 2>&1; then
    echo "backend OK"
    exit 0
  fi
  sleep 1
done

echo "backend FAILED (see $log_file)"
exit 1
