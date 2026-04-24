#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8099}"
ADMIN_URL="${ADMIN_URL:-http://127.0.0.1:8199}"
EVAL_URL="${EVAL_URL:-http://127.0.0.1:8200}"
IMAGE_OPS_URL="${IMAGE_OPS_URL:-http://127.0.0.1:8301}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

echo "[bundle-check] backend:   $BACKEND_URL"
echo "[bundle-check] admin:     $ADMIN_URL"
echo "[bundle-check] eval:      $EVAL_URL"
echo "[bundle-check] image-ops: $IMAGE_OPS_URL"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[bundle-check] ERROR: python3.11/python3 not found" >&2
  exit 2
fi

"$PYTHON_BIN" backend/scripts/check_coze_control_plane_migration.py \
  --backend-base "$BACKEND_URL" \
  --admin-base "$ADMIN_URL" \
  --eval-base "$EVAL_URL" \
  --image-ops-base "$IMAGE_OPS_URL"
