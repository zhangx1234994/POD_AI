#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-light}"
TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
PYTHON_BIN="${PYTHON_BIN:-$TARGET_ROOT/backend/.venv/bin/python}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8099}"
EXPECT_SERVER_URL="${EXPECT_SERVER_URL:-}"
MAX_PRODUCTION_PER_CATEGORY="${MAX_PRODUCTION_PER_CATEGORY:-2}"
RECENT_HOURS="${RECENT_HOURS:-1}"
STALE_MINUTES="${STALE_MINUTES:-30}"
SUBMIT_GRACE_MINUTES="${SUBMIT_GRACE_MINUTES:-5}"
BUSINESS_KEYS="${BUSINESS_KEYS:-all}"
BUSINESS_LIVE_KEYS="${BUSINESS_LIVE_KEYS:-pattern_extract,fission,outpaint}"
PATROL_IMAGE_URL="${PATROL_IMAGE_URL:-https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg}"
BUSINESS_LIVE_TIMEOUT="${BUSINESS_LIVE_TIMEOUT:-1200}"
BUSINESS_LIVE_INTERVAL="${BUSINESS_LIVE_INTERVAL:-10}"
EVAL_ROLE="${EVAL_ROLE:-production}"
EVAL_MAX_IN_FLIGHT="${EVAL_MAX_IN_FLIGHT:-1}"
EVAL_TIMEOUT="${EVAL_TIMEOUT:-1800}"
REPORT_DIR="${REPORT_DIR:-$TARGET_ROOT/reports/health-watch}"
RUN_TAG="${RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
RECORD_LIVE_PATROL="${RECORD_LIVE_PATROL:-1}"
RECORD_LIVE_ACCEPTANCE="${RECORD_LIVE_ACCEPTANCE:-0}"

if [[ ! -d "$TARGET_ROOT" ]]; then
  echo "TARGET_ROOT does not exist: $TARGET_ROOT" >&2
  exit 2
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime does not exist or is not executable: $PYTHON_BIN" >&2
  exit 2
fi

cd "$TARGET_ROOT"

if [[ -f "$TARGET_ROOT/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$TARGET_ROOT/backend/.env"
  set +a
fi

mkdir -p "$REPORT_DIR"

run_step() {
  local label="$1"
  shift
  echo "==> $label"
  "$@"
}

make_report_path() {
  local name="$1"
  echo "$REPORT_DIR/${name}_${RUN_TAG}.json"
}

run_release_smoke() {
  local report
  report="$(make_report_path release_smoke)"
  local args=(
    "$PYTHON_BIN" backend/scripts/podi_release_smoke.py
    --base-url "$BACKEND_URL"
    --max-production-per-category "$MAX_PRODUCTION_PER_CATEGORY"
    --report "$report"
  )
  if [[ -n "$EXPECT_SERVER_URL" ]]; then
    args+=(--expect-server-url "$EXPECT_SERVER_URL")
  fi
  run_step "backend release smoke" "${args[@]}"
}

run_business_route() {
  run_step "business API route preview" \
    "$PYTHON_BIN" backend/scripts/patrol_business_api.py \
      --base-url "$BACKEND_URL" \
      --mode route \
      --business "$BUSINESS_KEYS" \
      --report "$(make_report_path business_route)"
}

run_queue_visibility() {
  run_step "ComfyUI queue visibility" \
    "$PYTHON_BIN" backend/scripts/comfyui_capacity_probe.py \
      --backend-url "$BACKEND_URL" \
      --count 0
}

run_eval_health_recent() {
  echo "==> eval operations health"
  set +e
  "$PYTHON_BIN" backend/scripts/check_eval_operations_health.py \
    --recent-hours "$RECENT_HOURS" \
    --stale-minutes "$STALE_MINUTES" \
    --submit-grace-minutes "$SUBMIT_GRACE_MINUTES" \
    --report "$(make_report_path eval_health)"
  local status=$?
  set -e
  if [[ "$status" == "2" ]]; then
    return 2
  fi
  if [[ "$status" == "1" ]]; then
    echo "Eval operations health reported warning; continuing because only critical failures should fail the lightweight timer."
  fi
}

run_business_live() {
  local report
  report="$(make_report_path business_live)"
  local args=(
    "$PYTHON_BIN" backend/scripts/patrol_business_api.py \
      --base-url "$BACKEND_URL" \
      --mode live \
      --business "$BUSINESS_LIVE_KEYS" \
      --image-url "$PATROL_IMAGE_URL" \
      --timeout "$BUSINESS_LIVE_TIMEOUT" \
      --interval "$BUSINESS_LIVE_INTERVAL" \
      --require-executor-evidence \
      --report "$report"
  )
  if [[ "$RECORD_LIVE_PATROL" == "1" ]]; then
    args+=(--record-release-patrol --release-patrol-note "定时真实巡检：三主业务链路")
  fi
  if [[ "$RECORD_LIVE_ACCEPTANCE" == "1" ]]; then
    args+=(--record-acceptance)
  fi
  run_step "business API live patrol" "${args[@]}"
}

run_eval_production_patrol() {
  run_step "eval production patrol" \
    "$PYTHON_BIN" backend/scripts/patrol_eval_workflows.py \
      --base-url "$BACKEND_URL" \
      --role "$EVAL_ROLE" \
      --max-in-flight "$EVAL_MAX_IN_FLIGHT" \
      --timeout "$EVAL_TIMEOUT" \
      --report "$(make_report_path eval_production)"
}

case "$MODE" in
  light)
    run_release_smoke
    run_business_route
    run_queue_visibility
    run_eval_health_recent
    ;;
  live)
    run_business_live
    run_eval_production_patrol
    ;;
  *)
    echo "Unknown mode: $MODE. Use light or live." >&2
    exit 2
    ;;
esac

echo "PODI health watch completed: mode=$MODE reports=$REPORT_DIR tag=$RUN_TAG"
