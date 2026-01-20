#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -ne 1 ]; then
  echo "usage: bash scripts/coze_studio_set_admin_emails.sh <email>"
  exit 1
fi

python3 "$root_dir/scripts/coze_studio_set_admin_emails.py" --add "$1"

