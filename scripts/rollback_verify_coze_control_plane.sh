#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OLD_BACKEND_URL="${OLD_BACKEND_URL:-}"
IMAGE_PATH="${IMAGE_PATH:-}"
IMAGE_URL="${IMAGE_URL:-}"
POLL_SECONDS="${POLL_SECONDS:-90}"
SKIP_WORKFLOWS="${SKIP_WORKFLOWS:-0}"

usage() {
  cat <<'EOF'
Usage:
  OLD_BACKEND_URL=http://old-backend:8099 \
  IMAGE_PATH=/abs/path/sample.png \
  bash scripts/rollback_verify_coze_control_plane.sh

Environment:
  OLD_BACKEND_URL=http://old-backend:8099
  IMAGE_PATH=/abs/path/sample.png
  IMAGE_URL=https://...
  POLL_SECONDS=90
  SKIP_WORKFLOWS=0|1
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$OLD_BACKEND_URL" ]]; then
  echo "OLD_BACKEND_URL is required" >&2
  exit 2
fi

log() {
  printf '[rollback-verify] %s\n' "$1"
}

log "old backend: $OLD_BACKEND_URL"

log "checking old backend health"
curl --fail --silent --show-error "$OLD_BACKEND_URL/health" >/dev/null

log "checking old backend abilities"
curl --fail --silent --show-error "$OLD_BACKEND_URL/api/abilities" >/dev/null

log "checking old backend eval workflows"
curl --fail --silent --show-error "$OLD_BACKEND_URL/api/evals/workflow-versions" >/dev/null

if [[ "$SKIP_WORKFLOWS" == "1" ]]; then
  log "workflow smoke skipped"
  exit 0
fi

log "running primary Coze workflow smoke against old backend"
DOCS_URL="$OLD_BACKEND_URL/api/evals/docs/workflows" \
UPLOAD_URL="$OLD_BACKEND_URL/api/evals/uploads" \
TASK_URL="$OLD_BACKEND_URL/api/coze/podi/tasks/get" \
IMAGE_PATH="$IMAGE_PATH" \
IMAGE_URL="$IMAGE_URL" \
POLL_SECONDS="$POLL_SECONDS" \
bash "$ROOT_DIR/scripts/smoke_coze_primary_workflows.sh"

log "rollback verification done"
