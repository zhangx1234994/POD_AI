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
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/run_coze_control_plane_cutover.sh [plan|pre|deploy|post|full]

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

run_plan() {
  cat <<EOF
[cutover:plan] planned phase: $PHASE
[cutover:plan] deploy scope: $DEPLOY_SCOPE
[cutover:plan] backend:     $BACKEND_URL
[cutover:plan] admin:       $ADMIN_URL
[cutover:plan] eval:        $EVAL_URL
[cutover:plan] image-ops:   $IMAGE_OPS_URL
[cutover:plan] image path:  ${IMAGE_PATH:-<empty>}
[cutover:plan] image url:   ${IMAGE_URL:-<empty>}
[cutover:plan] poll secs:   $POLL_SECONDS
[cutover:plan] python bin:  ${PYTHON_BIN:-<missing>}

[cutover:plan] step 1: first-wave host reference check
  ${PYTHON_BIN:-python3} scripts/check_coze_host_cutover_refs.py --root "$ROOT_DIR"

[cutover:plan] step 2: deploy
EOF

  case "$DEPLOY_SCOPE" in
    backend-image-ops)
      cat <<EOF
  bash scripts/deploy_coze_backend_image_ops_only.sh
EOF
      ;;
    full)
      cat <<EOF
  ENABLE_WEBS=1 bash scripts/deploy_coze_control_plane_nodocker.sh
EOF
      ;;
  esac

  cat <<EOF

[cutover:plan] step 3: bundle check
  BACKEND_URL="$BACKEND_URL" ADMIN_URL="$ADMIN_URL" EVAL_URL="$EVAL_URL" IMAGE_OPS_URL="$IMAGE_OPS_URL" PYTHON_BIN="${PYTHON_BIN:-python3}" \\
  bash scripts/check_coze_control_plane_bundle.sh

[cutover:plan] step 4: image-ops smoke via backend
  BACKEND_URL="$BACKEND_URL" SERVICE_API_TOKEN="<optional>" \\
  ${PYTHON_BIN:-python3} scripts/smoke_image_ops_via_backend.py

[cutover:plan] step 5: primary Coze workflows smoke
  DOCS_URL="$BACKEND_URL/api/evals/docs/workflows" \\
  UPLOAD_URL="$BACKEND_URL/api/evals/uploads" \\
  TASK_URL="$BACKEND_URL/api/coze/podi/tasks/get" \\
  IMAGE_PATH="${IMAGE_PATH:-/abs/path/sample.png}" \\
  IMAGE_URL="${IMAGE_URL:-}" \\
  PYTHON_BIN="${PYTHON_BIN:-python3}" \\
  POLL_SECONDS="$POLL_SECONDS" \\
  bash scripts/smoke_coze_primary_workflows.sh
EOF
}

run_pre() {
  log "checking first-wave host references"
  if [[ -z "$PYTHON_BIN" ]]; then
    echo "[cutover:$PHASE] ERROR: python3.11/python3 not found" >&2
    exit 2
  fi
  "$PYTHON_BIN" "$ROOT_DIR/scripts/check_coze_host_cutover_refs.py" --root "$ROOT_DIR"
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
  if [[ -z "$PYTHON_BIN" ]]; then
    echo "[cutover:$PHASE] ERROR: python3.11/python3 not found" >&2
    exit 2
  fi

  log "running bundle checks"
  BACKEND_URL="$BACKEND_URL" \
  ADMIN_URL="$ADMIN_URL" \
  EVAL_URL="$EVAL_URL" \
  PYTHON_BIN="$PYTHON_BIN" \
  IMAGE_OPS_URL="$IMAGE_OPS_URL" \
  bash "$ROOT_DIR/scripts/check_coze_control_plane_bundle.sh"

  log "running image-ops smoke via backend"
  local image_ops_cmd=("$PYTHON_BIN" "$ROOT_DIR/scripts/smoke_image_ops_via_backend.py")
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
  PYTHON_BIN="$PYTHON_BIN" \
  POLL_SECONDS="$POLL_SECONDS" \
  bash "$ROOT_DIR/scripts/smoke_coze_primary_workflows.sh"
}

case "$PHASE" in
  plan)
    run_plan
    ;;
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
