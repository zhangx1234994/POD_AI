#!/usr/bin/env bash
set -euo pipefail

# Release backend + admin/eval static builds to the 114 control-plane host.
# Secrets are intentionally not stored here. Use SSH key auth, or export SSHPASS
# and make sure sshpass is installed locally.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_HOST="${TARGET_HOST:-114.55.0.56}"
TARGET_USER="${TARGET_USER:-root}"
TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
SSH_PORT="${SSH_PORT:-22}"

RUN_SOURCE_PREFLIGHT="${RUN_SOURCE_PREFLIGHT:-1}"
RUN_TESTS="${RUN_TESTS:-1}"
RUN_FRONTEND_LINT="${RUN_FRONTEND_LINT:-1}"
RUN_FRONTEND_BUILD="${RUN_FRONTEND_BUILD:-1}"
RUN_SMOKE="${RUN_SMOKE:-1}"
RUN_LIVE_PATROL="${RUN_LIVE_PATROL:-0}"
INSTALL_DEPS="${INSTALL_DEPS:-auto}"
SMOKE_ALLOW_COMFYUI_WARNINGS="${SMOKE_ALLOW_COMFYUI_WARNINGS:-0}"
SERVICE_READY_TIMEOUT_SECONDS="${SERVICE_READY_TIMEOUT_SECONDS:-60}"

BACKEND_URL_LOCAL="${BACKEND_URL_LOCAL:-http://127.0.0.1:8099}"
ADMIN_URL_LOCAL="${ADMIN_URL_LOCAL:-http://127.0.0.1:8199}"
EVAL_URL_LOCAL="${EVAL_URL_LOCAL:-http://127.0.0.1:8200}"
PATROL_IMAGE_URL="${PATROL_IMAGE_URL:-https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/98904c502d9d4dd78432ec2bd1f79def/20260424/228be55f-1777009905.jpg}"

cd "$ROOT_DIR"

COMMIT="$(git rev-parse --short=8 HEAD)"
ARCHIVE_DIR="$ROOT_DIR/.release"
CONTROL_ARCHIVE="$ARCHIVE_DIR/podi-control-plane-$COMMIT.tgz"
WEB_ARCHIVE="$ARCHIVE_DIR/podi-web-dist-$COMMIT.tgz"
REMOTE_ARCHIVE_DIR="$TARGET_ROOT/.deploy_tmp/$COMMIT"
TEMP_FILES=()

cleanup_temp_files() {
  local file
  if ((${#TEMP_FILES[@]} == 0)); then
    return 0
  fi
  for file in "${TEMP_FILES[@]}"; do
    if [[ -n "$file" ]]; then
      rm -f "$file"
    fi
  done
}
trap cleanup_temp_files EXIT

SSH_CONNECT_TIMEOUT_SECONDS="${SSH_CONNECT_TIMEOUT_SECONDS:-15}"
SSH_SERVER_ALIVE_INTERVAL_SECONDS="${SSH_SERVER_ALIVE_INTERVAL_SECONDS:-10}"
SSH_SERVER_ALIVE_COUNT_MAX="${SSH_SERVER_ALIVE_COUNT_MAX:-3}"
REMOTE_OP_RETRIES="${REMOTE_OP_RETRIES:-3}"
REMOTE_OP_RETRY_SLEEP_SECONDS="${REMOTE_OP_RETRY_SLEEP_SECONDS:-5}"

SSH_BASE=(
  ssh
  -p "$SSH_PORT"
  -o StrictHostKeyChecking=no
  -o ConnectTimeout="$SSH_CONNECT_TIMEOUT_SECONDS"
  -o ServerAliveInterval="$SSH_SERVER_ALIVE_INTERVAL_SECONDS"
  -o ServerAliveCountMax="$SSH_SERVER_ALIVE_COUNT_MAX"
  -o NumberOfPasswordPrompts=1
)
SCP_BASE=(
  scp
  -P "$SSH_PORT"
  -o StrictHostKeyChecking=no
  -o ConnectTimeout="$SSH_CONNECT_TIMEOUT_SECONDS"
  -o ServerAliveInterval="$SSH_SERVER_ALIVE_INTERVAL_SECONDS"
  -o ServerAliveCountMax="$SSH_SERVER_ALIVE_COUNT_MAX"
  -o NumberOfPasswordPrompts=1
)
if [[ -n "${SSHPASS:-}" ]]; then
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "[release-114] ERROR: SSHPASS is set but sshpass is not installed." >&2
    exit 2
  fi
  SSH_BASE=(sshpass -e "${SSH_BASE[@]}" -o PreferredAuthentications=password -o PubkeyAuthentication=no)
  SCP_BASE=(sshpass -e "${SCP_BASE[@]}" -o PreferredAuthentications=password -o PubkeyAuthentication=no)
fi

remote() {
  "${SSH_BASE[@]}" "$TARGET_USER@$TARGET_HOST" "$@"
}

upload() {
  "${SCP_BASE[@]}" "$1" "$TARGET_USER@$TARGET_HOST:$2"
}

with_retry() {
  local label="$1"
  shift
  local attempt=1
  local status=0

  while true; do
    if "$@"; then
      return 0
    else
      status=$?
    fi
    if (( attempt >= REMOTE_OP_RETRIES )); then
      echo "[release-114] ERROR: ${label} failed after ${attempt} attempt(s), exit=${status}." >&2
      return "$status"
    fi
    echo "[release-114] WARN: ${label} failed on attempt ${attempt}/${REMOTE_OP_RETRIES}, retrying in ${REMOTE_OP_RETRY_SLEEP_SECONDS}s..." >&2
    sleep "$REMOTE_OP_RETRY_SLEEP_SECONDS"
    attempt=$((attempt + 1))
  done
}

remote_retry() {
  local label="$1"
  shift
  with_retry "$label" remote "$@"
}

upload_retry() {
  local label="$1"
  local source="$2"
  local target="$3"
  with_retry "$label" upload "$source" "$target"
}

remote_script_retry() {
  local label="$1"
  local remote_command="$2"
  local script_file="$3"
  local attempt=1
  local status=0

  while true; do
    if remote "$remote_command" < "$script_file"; then
      return 0
    else
      status=$?
    fi
    if (( attempt >= REMOTE_OP_RETRIES )); then
      echo "[release-114] ERROR: ${label} failed after ${attempt} attempt(s), exit=${status}." >&2
      return "$status"
    fi
    echo "[release-114] WARN: ${label} failed on attempt ${attempt}/${REMOTE_OP_RETRIES}, retrying in ${REMOTE_OP_RETRY_SLEEP_SECONDS}s..." >&2
    sleep "$REMOTE_OP_RETRY_SLEEP_SECONDS"
    attempt=$((attempt + 1))
  done
}

section() {
  echo ""
  echo "== $1 =="
}

section "Release context"
echo "root=$ROOT_DIR"
echo "commit=$COMMIT"
echo "target=$TARGET_USER@$TARGET_HOST:$TARGET_ROOT"
echo "run_source_preflight=$RUN_SOURCE_PREFLIGHT"
echo "run_tests=$RUN_TESTS"
echo "run_frontend_lint=$RUN_FRONTEND_LINT"
echo "run_frontend_build=$RUN_FRONTEND_BUILD"
echo "run_smoke=$RUN_SMOKE"
echo "run_live_patrol=$RUN_LIVE_PATROL"
echo "install_deps=$INSTALL_DEPS"
echo "service_ready_timeout_seconds=$SERVICE_READY_TIMEOUT_SECONDS"
echo "remote_op_retries=$REMOTE_OP_RETRIES"

section "Source gate"
if [[ "$RUN_SOURCE_PREFLIGHT" == "1" ]]; then
  bash scripts/release_source_preflight.sh
else
  echo "[release-114] WARN: source preflight skipped. Use only for emergency/manual recovery."
fi

section "Automated tests"
if [[ "$RUN_TESTS" == "1" ]]; then
  # 发版校验固定读取仓库生产 executor 配置，避免开发机 backend/.env 的 3090 配置污染结果。
  EXECUTOR_CONFIG_PATH=config/executors.yaml python3 -m pytest \
    backend/tests/test_business_api_contract.py \
    backend/tests/test_ability_task_owner.py \
    backend/tests/test_admin_dashboard_release_governance.py \
    backend/tests/test_coze_comfyui_new_toolboxes_openapi.py \
    backend/tests/test_comfyui_executor_retirement.py \
    backend/tests/test_main_startup_catalog_seed.py \
    backend/tests/test_workflow_seed_refresh.py \
    backend/tests/test_routing_governance.py \
    backend/tests/test_workflow_seed_new_comfyui_toolboxes.py \
    backend/tests/test_podi_release_smoke.py \
    backend/tests/test_release_archive_packaging.py \
    -q
else
  echo "[release-114] WARN: backend tests skipped."
fi

if [[ "$RUN_FRONTEND_LINT" == "1" ]]; then
  (cd podi-admin-web && npm run lint)
  (cd podi-eval-web && npm run lint)
else
  echo "[release-114] WARN: frontend lint skipped."
fi

if [[ "$RUN_FRONTEND_BUILD" == "1" ]]; then
  (cd podi-admin-web && npm run build)
  (cd podi-eval-web && npm run build)
else
  echo "[release-114] WARN: frontend build skipped; existing dist will be packaged."
fi

section "Package"
mkdir -p "$ARCHIVE_DIR"
python3 scripts/package_release_archive.py \
  --root "$ROOT_DIR" \
  --output "$CONTROL_ARCHIVE" \
  backend config/executors.yaml docs scripts deploy
python3 scripts/package_release_archive.py \
  --root "$ROOT_DIR" \
  --output "$WEB_ARCHIVE" \
  podi-admin-web/dist podi-eval-web/dist

section "Upload"
remote_retry "create remote archive dir" "mkdir -p '$REMOTE_ARCHIVE_DIR'"
upload_retry "upload control archive" "$CONTROL_ARCHIVE" "$REMOTE_ARCHIVE_DIR/"
upload_retry "upload web archive" "$WEB_ARCHIVE" "$REMOTE_ARCHIVE_DIR/"

section "Remote deploy"
REMOTE_DEPLOY_SCRIPT="$(mktemp)"
TEMP_FILES+=("$REMOTE_DEPLOY_SCRIPT")
cat > "$REMOTE_DEPLOY_SCRIPT" <<'REMOTE'
set -euo pipefail
cd "$TARGET_ROOT"

wait_for_http() {
  local name="$1"
  local url="$2"
  local timeout_seconds="${3:-60}"
  local deadline=$((SECONDS + timeout_seconds))

  echo "[release-114] waiting for ${name}: ${url} (timeout=${timeout_seconds}s)"
  until curl -fsS "$url" >/dev/null 2>&1; do
    if [[ "$SECONDS" -ge "$deadline" ]]; then
      echo "[release-114] ERROR: ${name} is not ready after ${timeout_seconds}s: ${url}" >&2
      systemctl --no-pager --full status podi-backend podi-admin-web podi-eval-web >&2 || true
      journalctl -u podi-backend -n 80 --no-pager >&2 || true
      return 1
    fi
    sleep 2
  done
  echo "[release-114] ${name} ready"
}

ENV_BACKUP=""
VENV_BACKUP=""
if [[ -f backend/.env ]]; then
  ENV_BACKUP="$(mktemp)"
  cp backend/.env "$ENV_BACKUP"
fi
if [[ -d backend/.venv ]]; then
  VENV_BACKUP="/tmp/podi-backend-venv-$COMMIT"
  rm -rf "$VENV_BACKUP"
  mv backend/.venv "$VENV_BACKUP"
fi

rm -rf backend docs scripts deploy
rm -f config/executors.yaml
tar --no-same-owner -xzf "$CONTROL_ARCHIVE" -C "$TARGET_ROOT"

if [[ -n "$ENV_BACKUP" ]]; then
  cp "$ENV_BACKUP" backend/.env
  rm -f "$ENV_BACKUP"
fi
if [[ -n "$VENV_BACKUP" && -d "$VENV_BACKUP" ]]; then
  rm -rf backend/.venv
  mv "$VENV_BACKUP" backend/.venv
fi

rm -rf podi-admin-web/dist podi-eval-web/dist
tar --no-same-owner -xzf "$WEB_ARCHIVE" -C "$TARGET_ROOT"

cd "$TARGET_ROOT/backend"
# backend/.env 的配置优先级高于默认值；若生产仍指向开发机专用 YAML，启动 seed 会把 233
# 重新标记为 active。这里只校验路径并在异常时阻断发布，不自动修改服务器环境文件。
configured_executor_path="$(
  grep -E '^[[:space:]]*EXECUTOR_CONFIG_PATH[[:space:]]*=' .env 2>/dev/null \
    | tail -1 \
    | cut -d= -f2- \
    | tr -d '\r' \
    | xargs 2>/dev/null \
    || true
)"
case "$configured_executor_path" in
  ""|"config/executors.yaml"|"./config/executors.yaml"|"../config/executors.yaml"|"./../config/executors.yaml"|"$TARGET_ROOT/config/executors.yaml")
    ;;
  *)
    echo "[release-114] ERROR: backend/.env EXECUTOR_CONFIG_PATH points outside production config: $configured_executor_path" >&2
    exit 2
    ;;
esac
if [[ ! -x .venv/bin/python ]]; then
  python3.11 -m venv .venv
fi
if [[ "$INSTALL_DEPS" == "1" ]]; then
  .venv/bin/pip install -e . >/dev/null
elif [[ "$INSTALL_DEPS" == "auto" ]]; then
  echo "[release-114] INSTALL_DEPS=auto: preserving current venv; set INSTALL_DEPS=1 when dependencies changed."
fi
.venv/bin/alembic upgrade head
EXECUTOR_CONFIG_PATH="$TARGET_ROOT/config/executors.yaml" .venv/bin/python scripts/refresh_workflow_seeds.py

systemctl restart podi-backend podi-admin-web podi-eval-web
printf '%s' "$COMMIT" > "$TARGET_ROOT/DEPLOYED_COMMIT"
printf '%s' "$COMMIT" > "$TARGET_ROOT/.release_commit"
date -Is > "$TARGET_ROOT/.release_time"
systemctl is-active podi-backend podi-admin-web podi-eval-web
wait_for_http "backend" "${BACKEND_URL_LOCAL:-http://127.0.0.1:8099}/health" "$SERVICE_READY_TIMEOUT_SECONDS"
wait_for_http "admin" "${ADMIN_URL_LOCAL:-http://127.0.0.1:8199}/" "$SERVICE_READY_TIMEOUT_SECONDS"
wait_for_http "eval" "${EVAL_URL_LOCAL:-http://127.0.0.1:8200}/" "$SERVICE_READY_TIMEOUT_SECONDS"
REMOTE
remote_script_retry "remote deploy" "TARGET_ROOT='$TARGET_ROOT' COMMIT='$COMMIT' INSTALL_DEPS='$INSTALL_DEPS' CONTROL_ARCHIVE='$REMOTE_ARCHIVE_DIR/$(basename "$CONTROL_ARCHIVE")' WEB_ARCHIVE='$REMOTE_ARCHIVE_DIR/$(basename "$WEB_ARCHIVE")' BACKEND_URL_LOCAL='$BACKEND_URL_LOCAL' ADMIN_URL_LOCAL='$ADMIN_URL_LOCAL' EVAL_URL_LOCAL='$EVAL_URL_LOCAL' SERVICE_READY_TIMEOUT_SECONDS='$SERVICE_READY_TIMEOUT_SECONDS' bash -s" "$REMOTE_DEPLOY_SCRIPT"
rm -f "$REMOTE_DEPLOY_SCRIPT"

section "Remote verification"
remote_retry "remote verification" "set -e; cd '$TARGET_ROOT'; echo release=\$(cat DEPLOYED_COMMIT); curl -fsS '$BACKEND_URL_LOCAL/health'; echo; BACKEND_URL='$BACKEND_URL_LOCAL' ADMIN_URL='$ADMIN_URL_LOCAL' EVAL_URL='$EVAL_URL_LOCAL' bash scripts/deploy_preflight.sh"

if [[ "$RUN_SMOKE" == "1" ]]; then
  smoke_extra_args="${SMOKE_EXTRA_ARGS:-}"
  if [[ "$SMOKE_ALLOW_COMFYUI_WARNINGS" == "1" ]]; then
    smoke_extra_args="$smoke_extra_args --allow-comfyui-compat-warnings"
  fi
  REMOTE_SMOKE_SCRIPT="$(mktemp)"
  TEMP_FILES+=("$REMOTE_SMOKE_SCRIPT")
  cat > "$REMOTE_SMOKE_SCRIPT" <<'REMOTE'
set -euo pipefail
if [[ -f backend/.env ]]; then
  eval "$(backend/.venv/bin/python - <<'PY'
from pathlib import Path
import shlex

keys = {"SERVICE_API_TOKEN", "ADMIN_API_TOKEN", "EVAL_ADMIN_TOKEN"}
for raw_line in Path("backend/.env").read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if key not in keys:
        continue
    value = value.strip().strip("\"'")
    if value:
        print(f"export {key}={shlex.quote(value)}")
PY
)"
fi
expect_server_url="${SMOKE_EXPECT_SERVER_URL:-}"
if [[ -z "$expect_server_url" && -f backend/.env ]]; then
  expect_server_url="$(awk -F= '/^PODI_INTERNAL_BASE_URL=/{print $2; exit}' backend/.env | tr -d '\r' | sed 's/^"//;s/"$//')"
fi
expect_arg=()
if [[ -n "$expect_server_url" ]]; then
  expect_arg=(--expect-server-url "$expect_server_url")
fi
release_backend_log_since_raw="$(cat .release_time 2>/dev/null || echo '30 min ago')"
export RELEASE_BACKEND_LOG_SINCE="$(backend/.venv/bin/python - "$release_backend_log_since_raw" <<'PY'
from datetime import datetime
import sys

raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
try:
    parsed = datetime.fromisoformat(raw)
except ValueError:
    print(raw or "30 min ago")
else:
    print(parsed.strftime("%Y-%m-%d %H:%M:%S"))
PY
)"
backend/.venv/bin/python backend/scripts/podi_release_smoke.py --base-url "$BACKEND_URL_LOCAL" "${expect_arg[@]}" $SMOKE_EXTRA_ARGS
REMOTE
  remote_script_retry "release smoke" "cd '$TARGET_ROOT' && BACKEND_URL_LOCAL='$BACKEND_URL_LOCAL' SMOKE_EXTRA_ARGS='$smoke_extra_args' SMOKE_EXPECT_SERVER_URL='${SMOKE_EXPECT_SERVER_URL:-}' bash -s" "$REMOTE_SMOKE_SCRIPT"
  rm -f "$REMOTE_SMOKE_SCRIPT"
else
  echo "[release-114] WARN: release smoke skipped."
fi

if [[ "$RUN_LIVE_PATROL" == "1" ]]; then
  remote_retry "live patrol" "cd '$TARGET_ROOT' && backend/.venv/bin/python backend/scripts/patrol_business_api.py --base-url '$BACKEND_URL_LOCAL' --mode live --business pattern_extract,fission,outpaint --image-url '$PATROL_IMAGE_URL' --timeout 1200 --interval 10 --require-executor-evidence"
fi

section "Done"
echo "released_commit=$COMMIT"
