#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
PYTHON_BIN="${PYTHON_BIN:-$TARGET_ROOT/backend/.venv/bin/python}"
RECENT_HOURS="${RECENT_HOURS:-24}"
STALE_MINUTES="${STALE_MINUTES:-30}"
SUBMIT_GRACE_MINUTES="${SUBMIT_GRACE_MINUTES:-5}"
ENABLE_TIMER="${ENABLE_TIMER:-1}"
ALLOW_CRITICAL="${ALLOW_CRITICAL:-0}"
STRICT_WARNINGS="${STRICT_WARNINGS:-0}"

if [[ "$(id -u)" != "0" ]]; then
  echo "This installer must run as root because it writes systemd units." >&2
  exit 2
fi

if [[ ! -d "$TARGET_ROOT" ]]; then
  echo "TARGET_ROOT does not exist: $TARGET_ROOT" >&2
  exit 2
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python runtime does not exist or is not executable: $PYTHON_BIN" >&2
  exit 2
fi

SERVICE_SRC="$TARGET_ROOT/deploy/systemd/podi-eval-health-watch.service"
TIMER_SRC="$TARGET_ROOT/deploy/systemd/podi-eval-health-watch.timer"
if [[ ! -f "$SERVICE_SRC" || ! -f "$TIMER_SRC" ]]; then
  echo "Missing systemd unit templates under $TARGET_ROOT/deploy/systemd." >&2
  exit 2
fi

cd "$TARGET_ROOT"

echo "Running eval health precheck before installing timer..."
set +e
"$PYTHON_BIN" backend/scripts/check_eval_operations_health.py \
  --recent-hours "$RECENT_HOURS" \
  --stale-minutes "$STALE_MINUTES" \
  --submit-grace-minutes "$SUBMIT_GRACE_MINUTES"
PRECHECK_CODE=$?
set -e

if [[ "$PRECHECK_CODE" == "2" && "$ALLOW_CRITICAL" != "1" ]]; then
  echo "Precheck found critical issues. Fix them first, or rerun with ALLOW_CRITICAL=1 if this is intentional." >&2
  exit 2
fi

if [[ "$PRECHECK_CODE" == "1" && "$STRICT_WARNINGS" == "1" ]]; then
  echo "Precheck found warnings and STRICT_WARNINGS=1 is set." >&2
  exit 1
fi

install -m 0644 "$SERVICE_SRC" /etc/systemd/system/podi-eval-health-watch.service
install -m 0644 "$TIMER_SRC" /etc/systemd/system/podi-eval-health-watch.timer
systemctl daemon-reload

if [[ "$ENABLE_TIMER" == "1" ]]; then
  systemctl enable --now podi-eval-health-watch.timer
  systemctl list-timers podi-eval-health-watch.timer --no-pager
else
  echo "Timer installed but not enabled because ENABLE_TIMER=$ENABLE_TIMER."
fi

echo "Health watch installed."
echo "Inspect logs with: journalctl -u podi-eval-health-watch.service -n 80 --no-pager"
