#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

bash "$root_dir/scripts/dev_restart_backend.sh"
bash "$root_dir/scripts/dev_restart_web.sh"
bash "$root_dir/scripts/dev_status.sh"

