#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
image_ops_env="$root_dir/image-ops-service/.env"

echo "This will write secrets to: $image_ops_env"
echo "It will NOT commit anything to git."
echo

read -r -p "IMAGE_OPS_SERVICE_TOKEN (required): " service_token
if [ -z "${service_token:-}" ]; then
  echo "IMAGE_OPS_SERVICE_TOKEN is required"
  exit 1
fi

read -r -p "IMAGE_OPS_HOST [default 0.0.0.0]: " image_ops_host
read -r -p "IMAGE_OPS_PORT [default 8301]: " image_ops_port

image_ops_host="${image_ops_host:-0.0.0.0}"
image_ops_port="${image_ops_port:-8301}"

mkdir -p "$(dirname "$image_ops_env")"
cat >"$image_ops_env" <<EOF
IMAGE_OPS_SERVICE_TOKEN=${service_token}
IMAGE_OPS_HOST=${image_ops_host}
IMAGE_OPS_PORT=${image_ops_port}
EOF

echo
echo "Wrote $image_ops_env"
echo "Next:"
echo "  - start image-ops via systemd or docker compose"
echo "  - verify: curl http://${image_ops_host}:${image_ops_port}/health"
