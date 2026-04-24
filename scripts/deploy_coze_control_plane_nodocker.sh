#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
ENABLE_WEBS="${ENABLE_WEBS:-0}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

echo "[coze-control-plane] source repo: $ROOT_DIR"
echo "[coze-control-plane] target root: $TARGET_ROOT"
echo "[coze-control-plane] enable webs: $ENABLE_WEBS"
echo "[coze-control-plane] python bin: ${PYTHON_BIN:-<missing>}"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[coze-control-plane] ERROR: python3.11/python3 not found"
  exit 2
fi

mkdir -p "$TARGET_ROOT"

ensure_dir() {
  local dir="$1"
  mkdir -p "$dir"
}

copy_tree() {
  local src="$1"
  local dst="$2"
  ensure_dir "$(dirname "$dst")"
  local env_backup=""
  if [[ -f "$dst/.env" ]]; then
    env_backup="$(mktemp)"
    cp "$dst/.env" "$env_backup"
  fi
  rm -rf "$dst"
  cp -R "$src" "$dst"
  if [[ -n "$env_backup" ]]; then
    cp "$env_backup" "$dst/.env"
    rm -f "$env_backup"
  fi
}

echo "[coze-control-plane] syncing backend/image-ops/scripts/deploy..."
copy_tree "$ROOT_DIR/backend" "$TARGET_ROOT/backend"
copy_tree "$ROOT_DIR/image-ops-service" "$TARGET_ROOT/image-ops-service"
copy_tree "$ROOT_DIR/scripts" "$TARGET_ROOT/scripts"
copy_tree "$ROOT_DIR/deploy" "$TARGET_ROOT/deploy"

if [[ "$ENABLE_WEBS" == "1" ]]; then
  echo "[coze-control-plane] syncing admin/eval web..."
  copy_tree "$ROOT_DIR/podi-admin-web" "$TARGET_ROOT/podi-admin-web"
  copy_tree "$ROOT_DIR/podi-eval-web" "$TARGET_ROOT/podi-eval-web"
fi

ensure_dir "$TARGET_ROOT/logs"
ensure_dir "$TARGET_ROOT/runtime"

echo "[coze-control-plane] checking env files..."
if [[ ! -f "$TARGET_ROOT/backend/.env" ]]; then
  echo "[coze-control-plane] WARN: $TARGET_ROOT/backend/.env missing"
fi
if [[ ! -f "$TARGET_ROOT/image-ops-service/.env" ]]; then
  echo "[coze-control-plane] WARN: $TARGET_ROOT/image-ops-service/.env missing"
fi

echo "[coze-control-plane] backend setup..."
cd "$TARGET_ROOT/backend"
if [[ ! -x ".venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
./.venv/bin/pip install -U pip >/dev/null
./.venv/bin/pip install -e . >/dev/null
./.venv/bin/alembic upgrade head

echo "[coze-control-plane] image-ops setup..."
cd "$TARGET_ROOT/image-ops-service"
if [[ ! -x ".venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
./.venv/bin/pip install -U pip >/dev/null
./.venv/bin/pip install -e . >/dev/null

echo "[coze-control-plane] installing systemd units..."
cp "$TARGET_ROOT/deploy/systemd/podi-backend.service" /etc/systemd/system/podi-backend.service
cp "$TARGET_ROOT/image-ops-service/deploy/image-ops.service" /etc/systemd/system/image-ops.service

if [[ "$ENABLE_WEBS" == "1" ]]; then
  if [[ -d "$TARGET_ROOT/podi-admin-web" ]]; then
    cd "$TARGET_ROOT/podi-admin-web"
    npm install
    npm run build
  fi
  if [[ -d "$TARGET_ROOT/podi-eval-web" ]]; then
    cd "$TARGET_ROOT/podi-eval-web"
    npm install
    npm run build
  fi
  cp "$TARGET_ROOT/deploy/systemd/podi-admin-web.service" /etc/systemd/system/podi-admin-web.service
  cp "$TARGET_ROOT/deploy/systemd/podi-eval-web.service" /etc/systemd/system/podi-eval-web.service
fi

systemctl daemon-reload
systemctl enable podi-backend image-ops >/dev/null
systemctl restart podi-backend image-ops

if [[ "$ENABLE_WEBS" == "1" ]]; then
  systemctl enable podi-admin-web podi-eval-web >/dev/null
  systemctl restart podi-admin-web podi-eval-web
fi

echo "[coze-control-plane] services:"
systemctl --no-pager --full status podi-backend --lines=0 || true
systemctl --no-pager --full status image-ops --lines=0 || true
if [[ "$ENABLE_WEBS" == "1" ]]; then
  systemctl --no-pager --full status podi-admin-web --lines=0 || true
  systemctl --no-pager --full status podi-eval-web --lines=0 || true
fi

echo "[coze-control-plane] done"
