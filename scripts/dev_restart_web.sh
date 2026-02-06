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

echo "Stopping eval web (port 8200)..."
pkill -f "podi-eval-web/node_modules/.bin/vite --port 8200" 2>/dev/null || true

echo "Starting eval web..."
nohup bash -lc "cd \"$root_dir/podi-eval-web\" && npm run dev -- --port 8200 --host 0.0.0.0" >"$log_dir/eval-web-8200.log" 2>&1 &
echo $! > "$root_dir/podi-eval-web.dev.pid"

sleep 1
echo "admin web:  http://127.0.0.1:8199"
echo "eval web:   http://127.0.0.1:8200"
