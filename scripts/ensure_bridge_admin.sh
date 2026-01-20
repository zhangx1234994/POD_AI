#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -x "$root_dir/backend/.venv/bin/python" ]; then
  echo "backend venv not found; create it first via: bash scripts/dev_restart_backend.sh"
  exit 1
fi

# Run from backend/ so pydantic-settings can load backend/.env via env_file=".env".
(
  cd "$root_dir/backend"
  PYTHONPATH="$root_dir/backend" "$root_dir/backend/.venv/bin/python" "$root_dir/scripts/ensure_bridge_admin.py"
)
