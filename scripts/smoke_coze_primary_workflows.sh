#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOCS_URL="${DOCS_URL:-http://127.0.0.1:8099/api/evals/docs/workflows}"
UPLOAD_URL="${UPLOAD_URL:-http://127.0.0.1:8099/api/evals/uploads}"
TASK_URL="${TASK_URL:-http://127.0.0.1:8099/api/coze/podi/tasks/get}"
IMAGE_PATH="${IMAGE_PATH:-}"
IMAGE_URL="${IMAGE_URL:-}"
POLL_SECONDS="${POLL_SECONDS:-90}"
OUT_FILE="${OUT_FILE:-$ROOT_DIR/runtime/coze_primary_workflows_$(date +%Y%m%d_%H%M%S).json}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

mkdir -p "$(dirname "$OUT_FILE")"

echo "[coze-primary-smoke] docs: $DOCS_URL"
echo "[coze-primary-smoke] upload: $UPLOAD_URL"
echo "[coze-primary-smoke] task: $TASK_URL"
echo "[coze-primary-smoke] output: $OUT_FILE"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[coze-primary-smoke] ERROR: python3.11/python3 not found" >&2
  exit 2
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/coze_workflow_smoke.py" \
  --docs-url "$DOCS_URL" \
  --upload-url "$UPLOAD_URL" \
  --task-url "$TASK_URL" \
  ${IMAGE_PATH:+--image "$IMAGE_PATH"} \
  ${IMAGE_URL:+--image-url "$IMAGE_URL"} \
  --poll "$POLL_SECONDS" \
  --out "$OUT_FILE" \
  --workflow-id 7598563505054154752 \
  --workflow-id 7598587935331450880 \
  --workflow-id 7631174682116358144 \
  --workflow-id 7615600173695107072 \
  --workflow-id 7629023903431524352 \
  --workflow-id 7629023041988591616 \
  --workflow-id 7622190276932534272 \
  --workflow-id 7622193261276299264 \
  --workflow-id 7629024620879806464 \
  --workflow-id 7629026792103215104 \
  --workflow-id 7631838631375667200

echo "[coze-primary-smoke] done"
echo "[coze-primary-smoke] report: $OUT_FILE"
