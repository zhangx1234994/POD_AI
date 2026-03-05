#!/usr/bin/env bash
set -euo pipefail

# 状态/错误口径专项回归（本地/发版前）
# Usage:
#   bash scripts/status_error_regression.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Status/Error Regression =="
echo "Root: $ROOT_DIR"
echo ""

echo "[1/3] Error catalog consistency"
python3 scripts/check_error_catalog.py
echo ""

echo "[2/3] Eval review contract tests"
python3 -m pytest \
  backend/tests/test_eval_review_progress_contract.py \
  backend/tests/test_eval_review_api_contract.py \
  -q
echo ""

echo "[3/3] Unified status mapping tests"
python3 -m pytest \
  backend/tests/test_task_status_contract.py \
  backend/tests/test_ability_task_status_mapping.py \
  backend/tests/test_ability_invoke_status.py \
  backend/tests/test_coze_task_status_normalize.py \
  -q
echo ""

echo "Status/Error regression passed."
