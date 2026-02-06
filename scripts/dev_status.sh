#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

check_port() {
  local port="$1"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "LISTEN :$port"
  else
    echo "DOWN   :$port"
  fi
}

echo "== Ports =="
check_port 8099   # backend
check_port 8199   # admin web
check_port 8200   # eval web

echo
echo "== Health =="
if curl -fsS "http://127.0.0.1:8099/health" >/dev/null 2>&1; then
  echo "backend /health OK"
else
  echo "backend /health FAIL"
fi
