#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
BACKEND_ENV="${BACKEND_ENV:-$TARGET_ROOT/backend/.env}"
IMAGE_OPS_BASE_URL="${IMAGE_OPS_BASE_URL:-}"
IMAGE_OPS_TIMEOUT_SECONDS="${IMAGE_OPS_TIMEOUT_SECONDS:-120}"
IMAGE_OPS_LOCAL_FALLBACK_ENABLED="${IMAGE_OPS_LOCAL_FALLBACK_ENABLED:-false}"
DISABLE_LOCAL_HEAVY_IMAGE_TASKS="${DISABLE_LOCAL_HEAVY_IMAGE_TASKS:-true}"
RESTART_BACKEND="${RESTART_BACKEND:-1}"

if [[ -z "$IMAGE_OPS_BASE_URL" ]]; then
  echo "[image-ops-switch] ERROR: IMAGE_OPS_BASE_URL is required" >&2
  echo "[image-ops-switch] example: IMAGE_OPS_BASE_URL=http://117.50.80.158:8099 bash scripts/switch_backend_image_ops_base.sh" >&2
  exit 2
fi

if [[ ! -f "$BACKEND_ENV" ]]; then
  echo "[image-ops-switch] ERROR: backend env not found: $BACKEND_ENV" >&2
  exit 3
fi

backup="${BACKEND_ENV}.before_image_ops_switch_$(date +%Y%m%d_%H%M%S)"
cp "$BACKEND_ENV" "$backup"

upsert_env() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "$BACKEND_ENV"; then
    sed -i "s#^${key}=.*#${key}=${value}#" "$BACKEND_ENV"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$BACKEND_ENV"
  fi
}

upsert_env "IMAGE_OPS_BASE_URL" "$IMAGE_OPS_BASE_URL"
upsert_env "IMAGE_OPS_TIMEOUT_SECONDS" "$IMAGE_OPS_TIMEOUT_SECONDS"
upsert_env "IMAGE_OPS_LOCAL_FALLBACK_ENABLED" "$IMAGE_OPS_LOCAL_FALLBACK_ENABLED"
upsert_env "DISABLE_LOCAL_HEAVY_IMAGE_TASKS" "$DISABLE_LOCAL_HEAVY_IMAGE_TASKS"

echo "[image-ops-switch] backup: $backup"
echo "[image-ops-switch] IMAGE_OPS_BASE_URL=$IMAGE_OPS_BASE_URL"
echo "[image-ops-switch] IMAGE_OPS_LOCAL_FALLBACK_ENABLED=$IMAGE_OPS_LOCAL_FALLBACK_ENABLED"
echo "[image-ops-switch] DISABLE_LOCAL_HEAVY_IMAGE_TASKS=$DISABLE_LOCAL_HEAVY_IMAGE_TASKS"

if [[ "$RESTART_BACKEND" == "1" ]]; then
  systemctl restart podi-backend
  sleep 3
  systemctl is-active podi-backend
  curl -fsS http://127.0.0.1:8099/health
  echo
fi

