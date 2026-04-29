#!/usr/bin/env bash
set -euo pipefail

# Check the source tree before it is packaged or deployed.
# This catches two high-risk release issues:
# 1) packaging from a local branch/dirty tree instead of origin/main
# 2) broken Alembic migration graph or macOS AppleDouble files copied into the package

REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"
CHECK_GIT_SYNC="${CHECK_GIT_SYNC:-1}"
CHECK_APPLEDOUBLE="${CHECK_APPLEDOUBLE:-1}"
CHECK_ALEMBIC="${CHECK_ALEMBIC:-1}"
CHECK_DB_CURRENT="${CHECK_DB_CURRENT:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"
GIT_FETCH_TIMEOUT_SECONDS="${GIT_FETCH_TIMEOUT_SECONDS:-30}"

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

ok() {
  echo "[OK] $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

warn() {
  echo "[WARN] $1"
  WARN_COUNT=$((WARN_COUNT + 1))
}

fail() {
  echo "[FAIL] $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

repo_root() {
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
  else
    pwd
  fi
}

ROOT="$(repo_root)"
cd "$ROOT"

echo "== PODI Release Source Preflight =="
echo "ROOT=$ROOT"
echo "REMOTE=$REMOTE"
echo "BRANCH=$BRANCH"
echo "CHECK_GIT_SYNC=$CHECK_GIT_SYNC"
echo "CHECK_APPLEDOUBLE=$CHECK_APPLEDOUBLE"
echo "CHECK_ALEMBIC=$CHECK_ALEMBIC"
echo "CHECK_DB_CURRENT=$CHECK_DB_CURRENT"
echo "ALLOW_DIRTY=$ALLOW_DIRTY"
echo "GIT_FETCH_TIMEOUT_SECONDS=$GIT_FETCH_TIMEOUT_SECONDS"
echo ""

fetch_with_timeout() {
  local remote="$1"
  local branch="$2"
  local timeout_seconds="$3"
  git fetch --quiet "$remote" "$branch" &
  local pid=$!
  local deadline=$((SECONDS + timeout_seconds))
  while kill -0 "$pid" >/dev/null 2>&1; do
    if [[ "$SECONDS" -ge "$deadline" ]]; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
      return 124
    fi
    sleep 1
  done
  wait "$pid"
}

if [[ "$CHECK_GIT_SYNC" == "1" ]]; then
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fail "当前目录不是 git 工作区，不能确认发版源。"
  else
    if fetch_with_timeout "$REMOTE" "$BRANCH" "$GIT_FETCH_TIMEOUT_SECONDS"; then
      local_head="$(git rev-parse HEAD)"
      remote_head="$(git rev-parse "$REMOTE/$BRANCH")"
      if [[ "$local_head" == "$remote_head" ]]; then
        ok "当前 HEAD 与 ${REMOTE}/${BRANCH} 完全一致：${local_head:0:8}"
      else
        fail "当前 HEAD=${local_head:0:8}，${REMOTE}/${BRANCH}=${remote_head:0:8}，不能从非 main 真源发版。"
      fi
    else
      fail "无法在 ${GIT_FETCH_TIMEOUT_SECONDS}s 内 fetch ${REMOTE}/${BRANCH}，不能确认发版源。"
    fi

    status="$(git status --porcelain)"
    if [[ -z "$status" ]]; then
      ok "工作区干净。"
    elif [[ "$ALLOW_DIRTY" == "1" ]]; then
      warn "工作区有未提交改动；当前 ALLOW_DIRTY=1，仅开发联调用。"
      echo "$status"
    else
      fail "工作区有未提交改动，不能打正式发布包。"
      echo "$status"
    fi
  fi
fi

if [[ "$CHECK_APPLEDOUBLE" == "1" ]]; then
  scan_dirs=()
  for dir in backend scripts docs podi-admin-web podi-eval-web vendor-api-ops image-ops-service; do
    if [[ -d "$dir" ]]; then
      scan_dirs+=("$dir")
    fi
  done
  if [[ "${#scan_dirs[@]}" -eq 0 ]]; then
    warn "没有找到需要扫描的代码目录。"
  else
    appledouble_files="$(find "${scan_dirs[@]}" -name '._*' -print | head -50)"
    if [[ -z "$appledouble_files" ]]; then
      ok "未发现 macOS AppleDouble 文件。"
    else
      fail "发现 macOS AppleDouble 文件，必须清理后再打包。"
      echo "$appledouble_files"
    fi
  fi
fi

if [[ "$CHECK_ALEMBIC" == "1" ]]; then
  if [[ ! -d backend/alembic/versions ]]; then
    warn "未发现 backend/alembic/versions，跳过迁移检查。"
  else
    python_bin="${PYTHON_BIN:-}"
    if [[ -z "$python_bin" ]]; then
      if [[ -x backend/.venv/bin/python ]]; then
        python_bin="backend/.venv/bin/python"
      elif command -v python3 >/dev/null 2>&1; then
        python_bin="$(command -v python3)"
      else
        python_bin="$(command -v python)"
      fi
    fi

    migration_files="$(find backend/alembic/versions -name '*.py' ! -name '._*' -print | sort)"
    if [[ -z "$migration_files" ]]; then
      fail "未找到 Alembic migration Python 文件。"
    elif "$python_bin" -m py_compile $migration_files; then
      ok "Alembic migration Python 语法检查通过。"
    else
      fail "Alembic migration Python 语法检查失败。"
    fi

    alembic_cmd=()
    if [[ -x backend/.venv/bin/alembic ]]; then
      alembic_cmd=(backend/.venv/bin/alembic)
    else
      alembic_cmd=("$python_bin" -m alembic)
    fi

    if heads_output="$(cd backend && "${alembic_cmd[@]}" heads 2>&1)"; then
      head_count="$(printf '%s\n' "$heads_output" | grep -c '(head)' || true)"
      if [[ "$head_count" == "1" ]]; then
        ok "Alembic 只有一个 head：$(printf '%s\n' "$heads_output" | tr '\n' ' ')"
      else
        fail "Alembic head 数量异常：$head_count"
        printf '%s\n' "$heads_output"
      fi
    else
      fail "Alembic heads 检查失败。"
      printf '%s\n' "$heads_output"
    fi

    if [[ "$CHECK_DB_CURRENT" == "1" ]]; then
      if current_output="$(cd backend && "${alembic_cmd[@]}" current 2>&1)"; then
        ok "数据库当前 Alembic 版本可被代码识别：$(printf '%s\n' "$current_output" | tr '\n' ' ')"
      else
        fail "数据库当前 Alembic 版本不在代码迁移链中。"
        printf '%s\n' "$current_output"
      fi
    fi
  fi
fi

echo ""
echo "Preflight result: PASS=$PASS_COUNT WARN=$WARN_COUNT FAIL=$FAIL_COUNT"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "Release source preflight failed."
  exit 1
fi
echo "Release source preflight OK."
