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
SETTLE_SECONDS="${SETTLE_SECONDS:-120}"
OUT_FILE="${OUT_FILE:-$ROOT_DIR/runtime/coze_primary_workflows_$(date +%Y%m%d_%H%M%S).json}"
WORKFLOW_GROUP="${WORKFLOW_GROUP:-all}"
LIMIT="${LIMIT:-0}"
FAIL_FAST="${FAIL_FAST:-0}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "/srv/pod/backend/.venv/bin/python" ]]; then
    PYTHON_BIN="/srv/pod/backend/.venv/bin/python"
  elif [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/backend/.venv/bin/python"
  else
    PYTHON_BIN="$(command -v python3.11 || command -v python3 || true)"
  fi
fi

mkdir -p "$(dirname "$OUT_FILE")"

echo "[coze-primary-smoke] docs: $DOCS_URL"
echo "[coze-primary-smoke] upload: $UPLOAD_URL"
echo "[coze-primary-smoke] task: $TASK_URL"
echo "[coze-primary-smoke] output: $OUT_FILE"
echo "[coze-primary-smoke] group: $WORKFLOW_GROUP"
echo "[coze-primary-smoke] settle seconds: $SETTLE_SECONDS"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[coze-primary-smoke] ERROR: python3.11/python3 not found" >&2
  exit 2
fi

case "$WORKFLOW_GROUP" in
  core)
    workflow_ids=(
      7598563505054154752
      7631174682116358144
      7629023903431524352
      7629023041988591616
      7631838631375667200
    )
    ;;
  fission)
    workflow_ids=(
      7622190276932534272
      7622193261276299264
      7629024620879806464
      7629026792103215104
      7631838631375667200
    )
    ;;
  outpaint)
    workflow_ids=(
      7598587935331450880
      7631174682116358144
    )
    ;;
  all)
    workflow_ids=(
      7598563505054154752
      7598587935331450880
      7631174682116358144
      7615600173695107072
      7629023903431524352
      7629023041988591616
      7622190276932534272
      7622193261276299264
      7629024620879806464
      7629026792103215104
      7631838631375667200
    )
    ;;
  *)
    echo "[coze-primary-smoke] ERROR: unsupported WORKFLOW_GROUP=$WORKFLOW_GROUP" >&2
    exit 2
    ;;
esac

workflow_args=()
for workflow_id in "${workflow_ids[@]}"; do
  workflow_args+=(--workflow-id "$workflow_id")
done
if [[ "$FAIL_FAST" == "1" || "$FAIL_FAST" == "true" ]]; then
  workflow_args+=(--fail-fast)
fi
if [[ "$LIMIT" != "0" ]]; then
  workflow_args+=(--limit "$LIMIT")
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/coze_workflow_smoke.py" \
  --docs-url "$DOCS_URL" \
  --upload-url "$UPLOAD_URL" \
  --task-url "$TASK_URL" \
  ${IMAGE_PATH:+--image "$IMAGE_PATH"} \
  ${IMAGE_URL:+--image-url "$IMAGE_URL"} \
  --poll "$POLL_SECONDS" \
  --settle-poll "$SETTLE_SECONDS" \
  --out "$OUT_FILE" \
  "${workflow_args[@]}"

echo "[coze-primary-smoke] done"
echo "[coze-primary-smoke] report: $OUT_FILE"
