#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/image-ops-service"
LOG_DIR="$ROOT_DIR/runtime/logs"
LOG_FILE="$LOG_DIR/image_ops.log"
PORT="${IMAGE_OPS_PORT:-8301}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

if [[ ! -d "$SERVICE_DIR" ]]; then
  echo "[image-ops] ERROR: service directory missing: $SERVICE_DIR"
  exit 1
fi

mkdir -p "$LOG_DIR"

echo "[image-ops] repo: $ROOT_DIR"
echo "[image-ops] service dir: $SERVICE_DIR"
echo "[image-ops] port: $PORT"
echo "[image-ops] python bin: ${PYTHON_BIN:-<missing>}"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[image-ops] ERROR: python3.11/python3 not found"
  exit 2
fi

pkill -f "uvicorn app.main:app.*--port ${PORT}" 2>/dev/null || true
pkill -f "uvicorn app.main:app.*${SERVICE_DIR}" 2>/dev/null || true

cd "$SERVICE_DIR"

if [[ ! -f ".env" ]]; then
  echo "[image-ops] WARN: .env missing, using process environment only"
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "[image-ops] creating service venv..."
  "$PYTHON_BIN" -m venv .venv
fi

echo "[image-ops] installing deps..."
./.venv/bin/pip install -U pip >/dev/null
./.venv/bin/pip install -e . >/dev/null

nohup ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" >"$LOG_FILE" 2>&1 &

sleep 2
if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "[image-ops] healthy on :$PORT"
  echo "[image-ops] log: $LOG_FILE"
  exit 0
fi

echo "[image-ops] ERROR: health check failed, see $LOG_FILE"
exit 1
