#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$root_dir/scripts/ensure_coze_plugin_podi.py"

