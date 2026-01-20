#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -ne 2 ]; then
  echo "usage: bash scripts/coze_studio_publish_plugin.sh <space_id> <plugin_id>"
  exit 1
fi

python3 "$root_dir/scripts/coze_studio_publish_plugin.py" --space-id "$1" --plugin-id "$2"

