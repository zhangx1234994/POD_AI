#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TMP_DIR="${TMP_DIR:-$(mktemp -d "/tmp/pod_migration_selfcheck.XXXXXX")}"
KEEP_TMP="${KEEP_TMP:-0}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

mkdir -p "$TMP_DIR"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[selfcheck] ERROR: python3.11/python3 not found" >&2
  exit 2
fi

cleanup() {
  if [[ "$KEEP_TMP" != "1" ]]; then
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup EXIT

log() {
  printf '[selfcheck] %s\n' "$1"
}

run_cmd() {
  local name="$1"
  shift
  log "$name"
  "$@"
}

log "tmp dir: $TMP_DIR"

run_cmd "shell syntax: run_coze_control_plane_cutover.sh" \
  bash -n scripts/run_coze_control_plane_cutover.sh
run_cmd "shell syntax: rollback_coze_control_plane.sh" \
  bash -n scripts/rollback_coze_control_plane.sh
run_cmd "shell syntax: rollback_verify_coze_control_plane.sh" \
  bash -n scripts/rollback_verify_coze_control_plane.sh
run_cmd "shell syntax: deploy_coze_control_plane_nodocker.sh" \
  bash -n scripts/deploy_coze_control_plane_nodocker.sh
run_cmd "shell syntax: deploy_coze_backend_image_ops_only.sh" \
  bash -n scripts/deploy_coze_backend_image_ops_only.sh
run_cmd "shell syntax: check_coze_control_plane_bundle.sh" \
  bash -n scripts/check_coze_control_plane_bundle.sh
run_cmd "shell syntax: smoke_coze_primary_workflows.sh" \
  bash -n scripts/smoke_coze_primary_workflows.sh
run_cmd "shell syntax: capture_coze_control_plane_baseline.sh" \
  bash -n scripts/capture_coze_control_plane_baseline.sh
run_cmd "shell syntax: prod_write_backend_env.sh" \
  bash -n scripts/prod_write_backend_env.sh
run_cmd "shell syntax: prod_write_image_ops_env.sh" \
  bash -n scripts/prod_write_image_ops_env.sh
run_cmd "shell syntax: prod_write_coze_control_plane_envs.sh" \
  bash -n scripts/prod_write_coze_control_plane_envs.sh

run_cmd "python compile: compare baselines" \
  "$PYTHON_BIN" -m py_compile scripts/compare_coze_control_plane_baselines.py
run_cmd "python compile: completeness audit" \
  "$PYTHON_BIN" -m py_compile scripts/check_coze_migration_pack_completeness.py
run_cmd "python compile: host phasing check" \
  "$PYTHON_BIN" -m py_compile scripts/check_coze_host_cutover_refs.py
run_cmd "python compile: inventory collection" \
  "$PYTHON_BIN" -m py_compile scripts/collect_coze_migration_inventory.py
run_cmd "python compile: image ops smoke" \
  "$PYTHON_BIN" -m py_compile scripts/smoke_image_ops_via_backend.py

run_cmd "migration pack completeness" \
  "$PYTHON_BIN" scripts/check_coze_migration_pack_completeness.py --root "$ROOT_DIR"

run_cmd "first-wave host reference check" \
  "$PYTHON_BIN" scripts/check_coze_host_cutover_refs.py --root "$ROOT_DIR"

run_cmd "collect inventory snapshot" \
  "$PYTHON_BIN" scripts/collect_coze_migration_inventory.py --root "$ROOT_DIR" --output "$TMP_DIR/inventory.md"

run_cmd "cutover plan output" \
  bash scripts/run_coze_control_plane_cutover.sh plan >"$TMP_DIR/cutover-plan.txt"

run_cmd "rollback verify help" \
  bash scripts/rollback_verify_coze_control_plane.sh --help >"$TMP_DIR/rollback-verify-help.txt"

run_cmd "baseline capture" \
  env OUT_DIR="$TMP_DIR/baseline" bash scripts/capture_coze_control_plane_baseline.sh

run_cmd "baseline compare" \
  "$PYTHON_BIN" scripts/compare_coze_control_plane_baselines.py --before "$TMP_DIR/baseline" --after "$TMP_DIR/baseline" >"$TMP_DIR/baseline-diff.json"

log "all checks passed"
log "artifacts: $TMP_DIR"
