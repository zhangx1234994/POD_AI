#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

echo "[coze-envs] writing backend/.env"
bash "$root_dir/scripts/prod_write_backend_env.sh"
echo
echo "[coze-envs] writing image-ops-service/.env"
bash "$root_dir/scripts/prod_write_image_ops_env.sh"
echo
echo "[coze-envs] done"
