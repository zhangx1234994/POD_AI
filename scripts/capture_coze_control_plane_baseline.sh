#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8099}"
ADMIN_URL="${ADMIN_URL:-http://127.0.0.1:8199}"
EVAL_URL="${EVAL_URL:-http://127.0.0.1:8200}"
IMAGE_OPS_URL="${IMAGE_OPS_URL:-http://127.0.0.1:8301}"
TARGET_ROOT="${TARGET_ROOT:-/srv/pod}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/runtime/baseline_$(date +%Y%m%d_%H%M%S)}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

mkdir -p "$OUT_DIR"

echo "[baseline] output: $OUT_DIR"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "[baseline] ERROR: python3.11/python3 not found" >&2
  exit 2
fi

capture_cmd() {
  local name="$1"
  shift
  {
    echo "# command: $*"
    "$@"
  } >"$OUT_DIR/$name" 2>&1 || true
}

capture_http() {
  local name="$1"
  local url="$2"
  curl --silent --show-error "$url" >"$OUT_DIR/$name" 2>"$OUT_DIR/$name.stderr" || true
}

capture_cmd "timestamp.txt" date
capture_cmd "uname.txt" uname -a
capture_cmd "pwd.txt" pwd
capture_cmd "disk.txt" df -h
capture_cmd "memory.txt" free -h
capture_cmd "swap.txt" swapon --show
capture_cmd "listening_ports.txt" sh -c "ss -ltnp || netstat -ltnp"
capture_cmd "systemctl_podi_backend.txt" systemctl status podi-backend --no-pager --full
capture_cmd "systemctl_image_ops.txt" systemctl status image-ops --no-pager --full
capture_cmd "systemctl_podi_admin_web.txt" systemctl status podi-admin-web --no-pager --full
capture_cmd "systemctl_podi_eval_web.txt" systemctl status podi-eval-web --no-pager --full
capture_cmd "target_root_listing.txt" sh -c "ls -la '$TARGET_ROOT' || true"

capture_http "backend_health.json" "$BACKEND_URL/health"
capture_http "image_ops_health.json" "$IMAGE_OPS_URL/health"
capture_http "abilities.json" "$BACKEND_URL/api/abilities"
capture_http "eval_workflows.json" "$BACKEND_URL/api/evals/workflow-versions"
capture_http "coze_openapi.json" "$BACKEND_URL/api/coze/podi/openapi.json"
capture_http "coze_comfyui_openapi.json" "$BACKEND_URL/api/coze/podi/comfyui/openapi.json"

"$PYTHON_BIN" - "$OUT_DIR" "$BACKEND_URL" "$ADMIN_URL" "$EVAL_URL" "$IMAGE_OPS_URL" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
backend_url, admin_url, eval_url, image_ops_url = sys.argv[2:6]


def load_json(name: str):
    path = out_dir / name
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def read_text(name: str) -> str:
    path = out_dir / name
    try:
        return path.read_text()
    except Exception:
        return ""


abilities = load_json("abilities.json") or {}
eval_workflows = load_json("eval_workflows.json") or {}
backend_health = load_json("backend_health.json") or {}
image_ops_health = load_json("image_ops_health.json") or {}

summary = {
    "backendUrl": backend_url,
    "adminUrl": admin_url,
    "evalUrl": eval_url,
    "imageOpsUrl": image_ops_url,
    "backendHealthLoaded": bool(backend_health),
    "imageOpsHealthLoaded": bool(image_ops_health),
    "abilityCount": len((abilities.get("items") or [])) if isinstance(abilities, dict) else None,
    "evalWorkflowCount": len((eval_workflows.get("items") or [])) if isinstance(eval_workflows, dict) else None,
    "listeningPortsCaptured": "LISTEN" in read_text("listening_ports.txt") or "LISTENING" in read_text("listening_ports.txt"),
    "status": "ok",
}

(out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

echo "[baseline] done"
