#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
log_dir="$root_dir/logs"
mkdir -p "$log_dir"

echo "Stopping admin web (port 8199)..."
pkill -f "podi-admin-web/node_modules/.bin/vite --port 8199" 2>/dev/null || true

echo "Starting admin web..."
nohup bash -lc "cd \"$root_dir/podi-admin-web\" && npm run dev -- --port 8199 --host 0.0.0.0" >"$log_dir/admin-web-8199.log" 2>&1 &
echo $! > "$root_dir/podi-admin-web.dev.pid"

echo "Stopping client web (port 8080)..."
pkill -f "podi-design-web-dev/node_modules/.bin/vite --port 8080" 2>/dev/null || true

echo "Starting client web..."
nohup bash -lc "cd \"$root_dir/podi-design-web-dev\" && npm run dev -- --port 8080 --host 0.0.0.0" >"$log_dir/client-web-8080.log" 2>&1 &
echo $! > "$root_dir/podi-design-web-dev.dev.pid"

sleep 1
echo "admin web:  http://127.0.0.1:8199"
echo "client web: http://127.0.0.1:8080"

