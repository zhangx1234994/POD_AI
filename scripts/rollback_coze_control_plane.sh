#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
OLD_BACKEND_URL="${OLD_BACKEND_URL:-}"
NEW_BACKEND_URL="${NEW_BACKEND_URL:-http://127.0.0.1:8099}"
STOP_WEBS="${STOP_WEBS:-0}"
CONFIRM_TOOLBOX_ROLLBACK_DONE="${CONFIRM_TOOLBOX_ROLLBACK_DONE:-0}"
ARCHIVE_DIR="${ARCHIVE_DIR:-$TARGET_ROOT/runtime/rollback_$(date +%Y%m%d_%H%M%S)}"

usage() {
  cat <<'EOF'
Usage:
  OLD_BACKEND_URL=http://old-backend:8099 \
  CONFIRM_TOOLBOX_ROLLBACK_DONE=1 \
  bash scripts/rollback_coze_control_plane.sh

Environment:
  TARGET_ROOT=/srv/pod
  OLD_BACKEND_URL=http://old-backend:8099
  NEW_BACKEND_URL=http://127.0.0.1:8099
  STOP_WEBS=0|1
  CONFIRM_TOOLBOX_ROLLBACK_DONE=0|1
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

log() {
  printf '[rollback] %s\n' "$1"
}

if [[ -z "$OLD_BACKEND_URL" ]]; then
  echo "OLD_BACKEND_URL is required" >&2
  exit 2
fi

log "old backend: $OLD_BACKEND_URL"
log "new backend: $NEW_BACKEND_URL"

if [[ "$CONFIRM_TOOLBOX_ROLLBACK_DONE" != "1" ]]; then
  cat <<EOF
[rollback] 先完成以下动作，再重新执行本脚本并带上 CONFIRM_TOOLBOX_ROLLBACK_DONE=1

1. 把所有 Coze toolbox 指向切回旧 backend:
   $OLD_BACKEND_URL
2. 把 Coze workflow 里引用的新 OpenAPI/toolbox 恢复成旧 backend 版本
3. 确认主工作流重新提交成功，再停新控制面服务

当前脚本不会继续往下执行。
EOF
  exit 3
fi

log "archiving current service status to $ARCHIVE_DIR"
mkdir -p "$ARCHIVE_DIR"
systemctl status podi-backend >"$ARCHIVE_DIR/podi-backend.status.txt" 2>&1 || true
systemctl status image-ops >"$ARCHIVE_DIR/image-ops.status.txt" 2>&1 || true
if [[ "$STOP_WEBS" == "1" ]]; then
  systemctl status podi-admin-web >"$ARCHIVE_DIR/podi-admin-web.status.txt" 2>&1 || true
  systemctl status podi-eval-web >"$ARCHIVE_DIR/podi-eval-web.status.txt" 2>&1 || true
fi

log "stopping new control-plane services"
systemctl stop image-ops || true
systemctl stop podi-backend || true

if [[ "$STOP_WEBS" == "1" ]]; then
  systemctl stop podi-admin-web || true
  systemctl stop podi-eval-web || true
fi

cat <<EOF
[rollback] 已停止新控制面服务。

后续确认项：
1. Coze toolbox 当前应全部指向旧 backend:
   $OLD_BACKEND_URL
2. 旧 backend 健康检查:
   curl $OLD_BACKEND_URL/health
3. 旧 backend 关键接口:
   curl $OLD_BACKEND_URL/api/abilities
   curl $OLD_BACKEND_URL/api/evals/workflow-versions
4. 再跑一轮 Coze 主工作流抽检

归档目录：
  $ARCHIVE_DIR
EOF
