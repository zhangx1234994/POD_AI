#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
ENABLE_WEBS="${ENABLE_WEBS:-0}"

echo "[coze-control-plane] source repo: $ROOT_DIR"
echo "[coze-control-plane] target root: $TARGET_ROOT"
echo "[coze-control-plane] enable webs: $ENABLE_WEBS"

mkdir -p "$TARGET_ROOT"

ensure_dir() {
  local dir="$1"
  mkdir -p "$dir"
}

copy_tree() {
  local src="$1"
  local dst="$2"
  ensure_dir "$(dirname "$dst")"
  rm -rf "$dst"
  cp -R "$src" "$dst"
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
  python3 -m venv .venv
fi
./.venv/bin/pip install -U pip >/dev/null
./.venv/bin/pip install -e . >/dev/null
./.venv/bin/alembic upgrade head

echo "[coze-control-plane] image-ops setup..."
cd "$TARGET_ROOT/image-ops-service"
python3 -m pip install -U pip >/dev/null
python3 -m pip install . >/dev/null

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
