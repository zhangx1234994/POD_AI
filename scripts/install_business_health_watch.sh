#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
PYTHON_BIN="${PYTHON_BIN:-$TARGET_ROOT/backend/.venv/bin/python}"
ENABLE_LIGHT_TIMER="${ENABLE_LIGHT_TIMER:-1}"
ENABLE_LIVE_TIMER="${ENABLE_LIVE_TIMER:-1}"
RUN_LIVE_PRECHECK="${RUN_LIVE_PRECHECK:-0}"

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

required_files=(
  "$TARGET_ROOT/scripts/run_podi_health_watch.sh"
  "$TARGET_ROOT/deploy/systemd/podi-business-health-watch.service"
  "$TARGET_ROOT/deploy/systemd/podi-business-health-watch.timer"
  "$TARGET_ROOT/deploy/systemd/podi-business-live-patrol.service"
  "$TARGET_ROOT/deploy/systemd/podi-business-live-patrol.timer"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file" >&2
    exit 2
  fi
done

cd "$TARGET_ROOT"

echo "Running lightweight business health precheck before installing timers..."
PYTHON_BIN="$PYTHON_BIN" "$TARGET_ROOT/scripts/run_podi_health_watch.sh" light

if [[ "$RUN_LIVE_PRECHECK" == "1" ]]; then
  echo "Running live business patrol precheck. This submits real tasks."
  PYTHON_BIN="$PYTHON_BIN" "$TARGET_ROOT/scripts/run_podi_health_watch.sh" live
fi

chmod 0755 "$TARGET_ROOT/scripts/run_podi_health_watch.sh"
install -m 0644 "$TARGET_ROOT/deploy/systemd/podi-business-health-watch.service" /etc/systemd/system/podi-business-health-watch.service
install -m 0644 "$TARGET_ROOT/deploy/systemd/podi-business-health-watch.timer" /etc/systemd/system/podi-business-health-watch.timer
install -m 0644 "$TARGET_ROOT/deploy/systemd/podi-business-live-patrol.service" /etc/systemd/system/podi-business-live-patrol.service
install -m 0644 "$TARGET_ROOT/deploy/systemd/podi-business-live-patrol.timer" /etc/systemd/system/podi-business-live-patrol.timer

systemctl daemon-reload

if [[ "$ENABLE_LIGHT_TIMER" == "1" ]]; then
  systemctl enable --now podi-business-health-watch.timer
else
  systemctl disable --now podi-business-health-watch.timer 2>/dev/null || true
fi

if [[ "$ENABLE_LIVE_TIMER" == "1" ]]; then
  systemctl enable --now podi-business-live-patrol.timer
else
  systemctl disable --now podi-business-live-patrol.timer 2>/dev/null || true
fi

systemctl list-timers \
  podi-business-health-watch.timer \
  podi-business-live-patrol.timer \
  --no-pager

echo "Business health watch installed."
echo "Inspect lightweight logs with: journalctl -u podi-business-health-watch.service -n 120 --no-pager"
echo "Inspect live patrol logs with: journalctl -u podi-business-live-patrol.service -n 160 --no-pager"
