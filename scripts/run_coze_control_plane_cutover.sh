#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PHASE="${PHASE:-full}"
DEPLOY_SCOPE="${DEPLOY_SCOPE:-backend-image-ops}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8099}"
ADMIN_URL="${ADMIN_URL:-http://127.0.0.1:8199}"
EVAL_URL="${EVAL_URL:-http://127.0.0.1:8200}"
IMAGE_OPS_URL="${IMAGE_OPS_URL:-http://127.0.0.1:8301}"
IMAGE_PATH="${IMAGE_PATH:-}"
IMAGE_URL="${IMAGE_URL:-}"
POLL_SECONDS="${POLL_SECONDS:-90}"
SERVICE_API_TOKEN="${SERVICE_API_TOKEN:-}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_coze_control_plane_cutover.sh [pre|deploy|post|full]

Environment:
  DEPLOY_SCOPE=backend-image-ops|full
  BACKEND_URL=http://127.0.0.1:8099
  ADMIN_URL=http://127.0.0.1:8199
  EVAL_URL=http://127.0.0.1:8200
  IMAGE_OPS_URL=http://127.0.0.1:8301
  IMAGE_PATH=/abs/path/sample.png
  IMAGE_URL=https://...
  POLL_SECONDS=90
  SERVICE_API_TOKEN=<backend service token>
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ge 1 ]]; then
  PHASE="$1"
fi

log() {
  printf '[cutover:%s] %s\n' "$PHASE" "$1"
}

run_pre() {
  log "checking first-wave host references"
  python3 "$ROOT_DIR/scripts/check_coze_host_cutover_refs.py" --root "$ROOT_DIR"
}

run_deploy() {
  log "deploy scope: $DEPLOY_SCOPE"
  case "$DEPLOY_SCOPE" in
    backend-image-ops)
      bash "$ROOT_DIR/scripts/deploy_coze_backend_image_ops_only.sh"
      ;;
    full)
      ENABLE_WEBS=1 bash "$ROOT_DIR/scripts/deploy_coze_control_plane_nodocker.sh"
      ;;
    *)
      echo "Unsupported DEPLOY_SCOPE: $DEPLOY_SCOPE" >&2
      exit 2
      ;;
  esac
}

run_post() {
  log "running bundle checks"
  BACKEND_URL="$BACKEND_URL" \
  ADMIN_URL="$ADMIN_URL" \
  EVAL_URL="$EVAL_URL" \
  IMAGE_OPS_URL="$IMAGE_OPS_URL" \
  bash "$ROOT_DIR/scripts/check_coze_control_plane_bundle.sh"

  log "running image-ops smoke via backend"
  local image_ops_cmd=(python3 "$ROOT_DIR/scripts/smoke_image_ops_via_backend.py")
  if [[ -n "$SERVICE_API_TOKEN" ]]; then
    SERVICE_API_TOKEN="$SERVICE_API_TOKEN" \
    BACKEND_URL="$BACKEND_URL" \
    "${image_ops_cmd[@]}"
  else
    BACKEND_URL="$BACKEND_URL" \
    "${image_ops_cmd[@]}"
  fi

  log "running primary Coze workflow smoke"
  DOCS_URL="$BACKEND_URL/api/evals/docs/workflows" \
  UPLOAD_URL="$BACKEND_URL/api/evals/uploads" \
  TASK_URL="$BACKEND_URL/api/coze/podi/tasks/get" \
  IMAGE_PATH="$IMAGE_PATH" \
  IMAGE_URL="$IMAGE_URL" \
  POLL_SECONDS="$POLL_SECONDS" \
  bash "$ROOT_DIR/scripts/smoke_coze_primary_workflows.sh"
}

case "$PHASE" in
  pre)
    run_pre
    ;;
  deploy)
    run_deploy
    ;;
  post)
    run_post
    ;;
  full)
    run_pre
    run_deploy
    run_post
    ;;
  *)
    echo "Unsupported phase: $PHASE" >&2
    usage
    exit 2
    ;;
esac

log "done"
