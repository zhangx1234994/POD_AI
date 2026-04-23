#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[coze-backend-image-ops-only] repo: $ROOT_DIR"
echo "[coze-backend-image-ops-only] deploying backend + image-ops only"

TARGET_ROOT="${TARGET_ROOT:-/srv/pod}" \
ENABLE_WEBS=0 \
bash "$ROOT_DIR/scripts/deploy_coze_control_plane_nodocker.sh"
