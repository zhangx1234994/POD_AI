#!/usr/bin/env bash
set -euo pipefail

# Ensure the same bridge credentials exist across:
# - PODI backend (admin user)
# - Coze Studio
# - Coze Loop
#
# Credentials are read from env or `backend/.env` by the python scripts.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/3] PODI backend bridge admin"
bash "$repo_root/scripts/ensure_bridge_admin.sh"

echo "[2/3] Coze Studio bridge user"
python3 "$repo_root/scripts/ensure_bridge_user_coze_studio.py"

echo "[3/3] Coze Loop bridge user"
python3 "$repo_root/scripts/ensure_bridge_user_coze_loop.py"

echo "Bridge accounts ensured."
