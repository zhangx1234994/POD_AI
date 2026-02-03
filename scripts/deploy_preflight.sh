#!/usr/bin/env bash
set -euo pipefail

# PODI deploy preflight checks (no-docker friendly)
# Usage:
#   BACKEND_URL=http://127.0.0.1:8099 ADMIN_URL=http://127.0.0.1:8199 EVAL_URL=http://127.0.0.1:8200 \
#   bash scripts/deploy_preflight.sh

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8099}"
ADMIN_URL="${ADMIN_URL:-http://127.0.0.1:8199}"
EVAL_URL="${EVAL_URL:-http://127.0.0.1:8200}"

PASS_COUNT=0
FAIL_COUNT=0

print_ok() {
  echo "[OK] $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

print_fail() {
  echo "[FAIL] $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

check_code() {
  local url="$1"
  local ok_codes="$2"
  local name="$3"
  local code
  code="$(curl -s -o /tmp/podi_preflight_out -w "%{http_code}" "$url" || true)"
  if [[ "$code" == "000" ]]; then
    print_fail "$name ($url) -> no response"
    return 1
  fi
  for ok in $ok_codes; do
    if [[ "$code" == "$ok" ]]; then
      print_ok "$name ($url) -> $code"
      return 0
    fi
  done
  print_fail "$name ($url) -> $code"
  return 1
}

echo "== PODI Deploy Preflight =="
echo "BACKEND_URL=$BACKEND_URL"
echo "ADMIN_URL=$ADMIN_URL"
echo "EVAL_URL=$EVAL_URL"
echo ""

# 1) Backend health
check_code "$BACKEND_URL/health" "200" "Backend health"

# 2) Admin proxy to backend (401 is OK; 502 is not)
check_code "$ADMIN_URL/api/admin/workflows" "200 401 403" "Admin API via 8199"

# 3) Backend admin API direct (401/403 OK)
check_code "$BACKEND_URL/api/admin/workflows" "200 401 403" "Admin API via 8099"

# 4) Eval API (public enabled -> 200; disabled -> 404)
check_code "$EVAL_URL/api/evals/workflow-versions?status=active" "200 404" "Eval API via 8200"

# 5) Optional: Coze OpenAPI (internal-only, 200 or 401 is acceptable)
check_code "$BACKEND_URL/api/coze/podi/openapi.json" "200 401" "Coze OpenAPI"

echo ""
echo "Preflight result: PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "Preflight failed. Fix errors before deployment."
  exit 1
fi
echo "Preflight OK."
