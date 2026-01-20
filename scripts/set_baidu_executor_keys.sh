#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$root_dir/scripts/set_baidu_executor_keys.py"

