#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
PYTHON_BIN="${PYTHON_BIN:-$TARGET_ROOT/backend/.venv/bin/python}"
WINDOW_HOURS="${WINDOW_HOURS:-168}"
ENABLE_TIMER="${ENABLE_TIMER:-1}"

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

SERVICE_SRC="$TARGET_ROOT/deploy/systemd/podi-strategy-weekly-report.service"
TIMER_SRC="$TARGET_ROOT/deploy/systemd/podi-strategy-weekly-report.timer"
if [[ ! -f "$SERVICE_SRC" || ! -f "$TIMER_SRC" ]]; then
  echo "Missing systemd unit templates under $TARGET_ROOT/deploy/systemd." >&2
  exit 2
fi

cd "$TARGET_ROOT"

echo "Creating one strategy weekly report before installing timer..."
"$PYTHON_BIN" backend/scripts/create_strategy_snapshot.py \
  --weekly-report \
  --window-hours "$WINDOW_HOURS" \
  --note "install-precheck"

install -m 0644 "$SERVICE_SRC" /etc/systemd/system/podi-strategy-weekly-report.service
install -m 0644 "$TIMER_SRC" /etc/systemd/system/podi-strategy-weekly-report.timer
systemctl daemon-reload

if [[ "$ENABLE_TIMER" == "1" ]]; then
  systemctl enable --now podi-strategy-weekly-report.timer
  systemctl list-timers podi-strategy-weekly-report.timer --no-pager
else
  echo "Timer installed but not enabled because ENABLE_TIMER=$ENABLE_TIMER."
fi

echo "Strategy weekly report timer installed."
echo "Inspect logs with: journalctl -u podi-strategy-weekly-report.service -n 80 --no-pager"
