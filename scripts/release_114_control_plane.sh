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

SSH_BASE=(ssh -p "$SSH_PORT" -o StrictHostKeyChecking=no)
SCP_BASE=(scp -P "$SSH_PORT" -o StrictHostKeyChecking=no)
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

section "Source gate"
if [[ "$RUN_SOURCE_PREFLIGHT" == "1" ]]; then
  bash scripts/release_source_preflight.sh
else
  echo "[release-114] WARN: source preflight skipped. Use only for emergency/manual recovery."
fi

section "Automated tests"
if [[ "$RUN_TESTS" == "1" ]]; then
  python3 -m pytest \
    backend/tests/test_business_api_contract.py \
    backend/tests/test_ability_task_owner.py \
    backend/tests/test_admin_dashboard_release_governance.py \
    backend/tests/test_coze_comfyui_new_toolboxes_openapi.py \
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
  backend docs scripts deploy
python3 scripts/package_release_archive.py \
  --root "$ROOT_DIR" \
  --output "$WEB_ARCHIVE" \
  podi-admin-web/dist podi-eval-web/dist

section "Upload"
remote "mkdir -p '$REMOTE_ARCHIVE_DIR'"
upload "$CONTROL_ARCHIVE" "$REMOTE_ARCHIVE_DIR/"
upload "$WEB_ARCHIVE" "$REMOTE_ARCHIVE_DIR/"

section "Remote deploy"
remote "TARGET_ROOT='$TARGET_ROOT' COMMIT='$COMMIT' INSTALL_DEPS='$INSTALL_DEPS' CONTROL_ARCHIVE='$REMOTE_ARCHIVE_DIR/$(basename "$CONTROL_ARCHIVE")' WEB_ARCHIVE='$REMOTE_ARCHIVE_DIR/$(basename "$WEB_ARCHIVE")' BACKEND_URL_LOCAL='$BACKEND_URL_LOCAL' ADMIN_URL_LOCAL='$ADMIN_URL_LOCAL' EVAL_URL_LOCAL='$EVAL_URL_LOCAL' SERVICE_READY_TIMEOUT_SECONDS='$SERVICE_READY_TIMEOUT_SECONDS' bash -s" <<'REMOTE'
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
if [[ ! -x .venv/bin/python ]]; then
  python3.11 -m venv .venv
fi
if [[ "$INSTALL_DEPS" == "1" ]]; then
  .venv/bin/pip install -e . >/dev/null
elif [[ "$INSTALL_DEPS" == "auto" ]]; then
  echo "[release-114] INSTALL_DEPS=auto: preserving current venv; set INSTALL_DEPS=1 when dependencies changed."
fi
.venv/bin/alembic upgrade head

systemctl restart podi-backend podi-admin-web podi-eval-web
printf '%s' "$COMMIT" > "$TARGET_ROOT/DEPLOYED_COMMIT"
printf '%s' "$COMMIT" > "$TARGET_ROOT/.release_commit"
date -Is > "$TARGET_ROOT/.release_time"
systemctl is-active podi-backend podi-admin-web podi-eval-web
wait_for_http "backend" "${BACKEND_URL_LOCAL:-http://127.0.0.1:8099}/health" "$SERVICE_READY_TIMEOUT_SECONDS"
wait_for_http "admin" "${ADMIN_URL_LOCAL:-http://127.0.0.1:8199}/" "$SERVICE_READY_TIMEOUT_SECONDS"
wait_for_http "eval" "${EVAL_URL_LOCAL:-http://127.0.0.1:8200}/" "$SERVICE_READY_TIMEOUT_SECONDS"
REMOTE

section "Remote verification"
remote "set -e; cd '$TARGET_ROOT'; echo release=\$(cat DEPLOYED_COMMIT); curl -fsS '$BACKEND_URL_LOCAL/health'; echo; BACKEND_URL='$BACKEND_URL_LOCAL' ADMIN_URL='$ADMIN_URL_LOCAL' EVAL_URL='$EVAL_URL_LOCAL' bash scripts/deploy_preflight.sh"

if [[ "$RUN_SMOKE" == "1" ]]; then
  smoke_extra_args="${SMOKE_EXTRA_ARGS:-}"
  if [[ "$SMOKE_ALLOW_COMFYUI_WARNINGS" == "1" ]]; then
    smoke_extra_args="$smoke_extra_args --allow-comfyui-compat-warnings"
  fi
remote "cd '$TARGET_ROOT' && BACKEND_URL_LOCAL='$BACKEND_URL_LOCAL' SMOKE_EXTRA_ARGS='$smoke_extra_args' SMOKE_EXPECT_SERVER_URL='${SMOKE_EXPECT_SERVER_URL:-}' bash -s" <<'REMOTE'
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
backend/.venv/bin/python backend/scripts/podi_release_smoke.py --base-url "$BACKEND_URL_LOCAL" "${expect_arg[@]}" $SMOKE_EXTRA_ARGS
REMOTE
else
  echo "[release-114] WARN: release smoke skipped."
fi

if [[ "$RUN_LIVE_PATROL" == "1" ]]; then
  remote "cd '$TARGET_ROOT' && backend/.venv/bin/python backend/scripts/patrol_business_api.py --base-url '$BACKEND_URL_LOCAL' --mode live --business pattern_extract,fission,outpaint --image-url '$PATROL_IMAGE_URL' --timeout 1200 --interval 10 --require-executor-evidence"
fi

section "Done"
echo "released_commit=$COMMIT"
