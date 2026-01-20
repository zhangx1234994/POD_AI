#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"

apply_patch_if_needed() {
  local repo_dir="$1"
  local patch_file="$2"
  if git -C "$repo_dir" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
    echo "patch already applied: $patch_file"
    return 0
  fi
  echo "applying patch: $patch_file"
  git -C "$repo_dir" apply "$patch_file"
}

apply_patch_if_needed "$root_dir/coze-loop" "$root_dir/patches/coze-loop/local-docker-compose.patch"

echo "Coze patches applied."

