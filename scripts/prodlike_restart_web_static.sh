#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
log_dir="$root_dir/logs"
mkdir -p "$log_dir"

restart_site() {
  local name="$1"
  local dir="$2"
  local port="$3"
  local pid_file="$4"
  local log_file="$5"

  echo "[prodlike] building $name..."
  (cd "$dir" && npm ci >/dev/null && VITE_API_BASE_URL="" npm run build >/dev/null)

  echo "[prodlike] stopping $name (port $port)..."
  # Kill by port first (most reliable).
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [[ -n "${pids:-}" ]]; then
      kill $pids 2>/dev/null || true
    fi
  fi
  if [[ -f "$pid_file" ]]; then
    kill "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file"
  fi
  pkill -f "node .*node_static_proxy\\.mjs .*--port ${port}" 2>/dev/null || true
  pkill -f "vite.*--port ${port}" 2>/dev/null || true
  pkill -f "vite preview.*--port ${port}" 2>/dev/null || true

  echo "[prodlike] starting $name..."
  nohup bash -lc "cd \"$root_dir\" && node ./scripts/node_static_proxy.mjs --root \"$dir/dist\" --port \"$port\" --api \"http://127.0.0.1:8099\"" >"$log_file" 2>&1 &
  echo $! > "$pid_file"
}

restart_site "admin-web" "$root_dir/podi-admin-web" "8199" "$root_dir/podi-admin-web.prod.pid" "$log_dir/admin-web-8199.log"
restart_site "eval-web" "$root_dir/podi-eval-web" "8200" "$root_dir/podi-eval-web.prod.pid" "$log_dir/eval-web-8200.log"

echo "[prodlike] admin web: http://127.0.0.1:8199"
echo "[prodlike] eval web:  http://127.0.0.1:8200"
