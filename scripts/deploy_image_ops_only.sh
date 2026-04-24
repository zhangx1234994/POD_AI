#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"
REUSE_8099="${REUSE_8099:-0}"
REUSE_8200="${REUSE_8200:-0}"

echo "[image-ops-only] source repo: $ROOT_DIR"
echo "[image-ops-only] target root: $TARGET_ROOT"
echo "[image-ops-only] python bin: ${PYTHON_BIN:-<missing>}"
echo "[image-ops-only] reuse 8099: $REUSE_8099"
echo "[image-ops-only] reuse 8200: $REUSE_8200"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[image-ops-only] ERROR: python3.11/python3 not found" >&2
  exit 2
fi

copy_tree_preserve_env() {
  local src="$1"
  local dst="$2"
  local env_backup=""
  local src_real=""
  local dst_real=""
  mkdir -p "$(dirname "$dst")"
  src_real="$(cd "$src" && pwd -P)"
  if [[ -d "$dst" ]]; then
    dst_real="$(cd "$dst" && pwd -P)"
  fi
  if [[ -n "$dst_real" && "$src_real" == "$dst_real" ]]; then
    echo "[image-ops-only] skip self-copy: $src_real"
    find "$dst" -name '._*' -delete
    return
  fi
  if [[ -f "$dst/.env" ]]; then
    env_backup="$(mktemp)"
    cp "$dst/.env" "$env_backup"
  fi
  rm -rf "$dst"
  cp -R "$src" "$dst"
  find "$dst" -name '._*' -delete
  if [[ -n "$env_backup" ]]; then
    cp "$env_backup" "$dst/.env"
    rm -f "$env_backup"
  fi
}

mkdir -p "$TARGET_ROOT/runtime" "$TARGET_ROOT/logs"

echo "[image-ops-only] syncing image-ops-service/scripts/deploy..."
copy_tree_preserve_env "$ROOT_DIR/image-ops-service" "$TARGET_ROOT/image-ops-service"
copy_tree_preserve_env "$ROOT_DIR/scripts" "$TARGET_ROOT/scripts"
copy_tree_preserve_env "$ROOT_DIR/deploy" "$TARGET_ROOT/deploy"

if [[ ! -f "$TARGET_ROOT/image-ops-service/.env" ]]; then
  echo "[image-ops-only] ERROR: $TARGET_ROOT/image-ops-service/.env missing" >&2
  echo "[image-ops-only] create it with scripts/prod_write_image_ops_env.sh before deploy." >&2
  exit 3
fi

configured_port="$(grep -E '^IMAGE_OPS_PORT=' "$TARGET_ROOT/image-ops-service/.env" | tail -1 | cut -d= -f2- || true)"
configured_port="${configured_port:-8301}"

kill_listeners_on_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [[ -n "${pids:-}" ]]; then
      echo "[image-ops-only] killing remaining listeners on ${port}: $pids"
      kill $pids 2>/dev/null || true
      sleep 1
    fi
  fi
}

if [[ "$configured_port" == "8099" ]]; then
  if [[ "$REUSE_8099" != "1" ]]; then
    echo "[image-ops-only] ERROR: IMAGE_OPS_PORT=8099 requires REUSE_8099=1" >&2
    echo "[image-ops-only] This avoids accidentally replacing the old backend rollback port." >&2
    exit 4
  fi
  echo "[image-ops-only] stopping old 8099 web/backend services before starting image-ops..."
  systemctl stop podi-backend 2>/dev/null || true
  systemctl disable podi-backend 2>/dev/null || true
  systemctl stop podi-admin-web podi-eval-web 2>/dev/null || true
  systemctl disable podi-admin-web podi-eval-web 2>/dev/null || true
  kill_listeners_on_port 8099
fi

if [[ "$configured_port" == "8200" ]]; then
  if [[ "$REUSE_8200" != "1" ]]; then
    echo "[image-ops-only] ERROR: IMAGE_OPS_PORT=8200 requires REUSE_8200=1" >&2
    echo "[image-ops-only] This avoids accidentally replacing the eval web port." >&2
    exit 5
  fi
  echo "[image-ops-only] stopping old 8200 eval service before starting image-ops..."
  systemctl stop podi-eval-web 2>/dev/null || true
  systemctl disable podi-eval-web 2>/dev/null || true
  kill_listeners_on_port 8200
fi

echo "[image-ops-only] installing image-ops deps..."
cd "$TARGET_ROOT/image-ops-service"
if [[ ! -x ".venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
./.venv/bin/pip install -U pip >/dev/null
./.venv/bin/pip install -e . >/dev/null

echo "[image-ops-only] installing systemd unit..."
cp "$TARGET_ROOT/image-ops-service/deploy/image-ops.service" /etc/systemd/system/image-ops.service
systemctl daemon-reload
systemctl enable image-ops >/dev/null
systemctl restart image-ops

sleep 2
echo "[image-ops-only] service status:"
systemctl --no-pager --full status image-ops --lines=0 || true

echo "[image-ops-only] health:"
curl -fsS "http://127.0.0.1:${configured_port}/health"
echo
echo "[image-ops-only] listening:"
ss -lntp | grep -E ":(${configured_port})" || true
