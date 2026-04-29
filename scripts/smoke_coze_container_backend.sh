#!/usr/bin/env bash
set -euo pipefail

# Run this on the Coze/backend host after deployment.
# It checks the real path used by Coze Studio containers:
# coze-server container -> PODI backend toolbox -> task polling endpoint.

COZE_CONTAINER="${COZE_CONTAINER:-coze-server}"
BACKEND_URL="${BACKEND_URL:-http://114.55.0.56:8099}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-8}"
EXPECT_EXTERNAL_BLOCKED="${EXPECT_EXTERNAL_BLOCKED:-0}"

tmp_openapi="/tmp/podi_coze_openapi_smoke.json"
tmp_task="/tmp/podi_coze_task_smoke.json"

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

pass() {
  echo "[PASS] $*"
}

command -v docker >/dev/null 2>&1 || fail "docker is not installed on this host"
docker inspect "$COZE_CONTAINER" >/dev/null 2>&1 || fail "container not found: $COZE_CONTAINER"

openapi_status="$(
  docker exec "$COZE_CONTAINER" curl -sS --max-time "$TIMEOUT_SECONDS" \
    -o "$tmp_openapi" \
    -w "%{http_code}" \
    "$BACKEND_URL/api/coze/podi/openapi.json"
)"

if [[ "$openapi_status" != "200" ]]; then
  echo "[DEBUG] OpenAPI response:"
  docker exec "$COZE_CONTAINER" sh -lc "cat '$tmp_openapi' 2>/dev/null | head -c 500" || true
  echo
  fail "Coze container cannot read backend OpenAPI. status=$openapi_status url=$BACKEND_URL"
fi
pass "Coze container can read backend OpenAPI. status=$openapi_status url=$BACKEND_URL"

task_status="$(
  docker exec "$COZE_CONTAINER" curl -sS --max-time "$TIMEOUT_SECONDS" \
    -X POST "$BACKEND_URL/api/coze/podi/tasks/get" \
    -H "Content-Type: application/json" \
    -d '{"taskId":"__coze_container_smoke_not_found__"}' \
    -o "$tmp_task" \
    -w "%{http_code}"
)"
task_body="$(docker exec "$COZE_CONTAINER" sh -lc "cat '$tmp_task' 2>/dev/null" || true)"

if [[ "$task_status" != "404" ]] || [[ "$task_body" != *"TASK_NOT_FOUND"* ]]; then
  echo "[DEBUG] tasks/get response: $task_body"
  fail "Coze container cannot reach trusted task polling endpoint. status=$task_status"
fi
pass "Coze container can reach trusted task polling endpoint. status=$task_status detail=TASK_NOT_FOUND"

if [[ "$EXPECT_EXTERNAL_BLOCKED" == "1" ]]; then
  external_status="$(
    curl -sS --max-time "$TIMEOUT_SECONDS" \
      -X POST "$BACKEND_URL/api/coze/podi/tasks/get" \
      -H "Content-Type: application/json" \
      -d '{"taskId":"__external_boundary_smoke__"}' \
      -o /tmp/podi_external_task_smoke.json \
      -w "%{http_code}" \
      || true
  )"
  if [[ "$external_status" == "401" ]]; then
    pass "Current caller is blocked by INTERNAL_ONLY. status=$external_status"
  else
    fail "Current caller is not blocked. status=$external_status; check COZE_TRUSTED_IPS and network boundary."
  fi
else
  echo "[INFO] Skipped external blocking check. Run from an untrusted machine with EXPECT_EXTERNAL_BLOCKED=1 when needed."
fi
