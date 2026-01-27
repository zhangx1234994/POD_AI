#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root_dir"

echo "[deploy-nodocker] repo: $root_dir"
echo "[deploy-nodocker] commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

if [[ ! -f backend/.env ]]; then
  echo "[deploy-nodocker] ERROR: backend/.env missing (copy backend/.env.example and fill DATABASE_URL etc.)"
  exit 1
fi

echo "[deploy-nodocker] restarting backend..."
bash scripts/prodlike_restart_backend.sh

echo "[deploy-nodocker] restarting static web servers..."
bash scripts/prodlike_restart_web_static.sh

echo "[deploy-nodocker] done"

