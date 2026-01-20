#!/usr/bin/env bash
set -euo pipefail

# Generate backend/.env on the target server (interactive), without committing secrets.
# This keeps "deploy on another box" simple: clone -> run this -> start services.

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
backend_env="$root_dir/backend/.env"

echo "This will write secrets to: $backend_env"
echo "It will NOT commit anything to git."
echo

read -r -p "DATABASE_URL (mysql+pymysql://user:pass@host:3306/db): " database_url
if [ -z "${database_url:-}" ]; then
  echo "DATABASE_URL is required"
  exit 1
fi

read -r -p "SERVICE_API_TOKEN (optional; internal coze->podi auth, leave empty to disable): " service_token

read -r -p "VOLCENGINE_API_KEY (optional): " volc_key
read -r -p "KIE_API_KEY (optional): " kie_key
read -r -p "BAIDU_API_KEY (optional): " baidu_key
read -r -p "BAIDU_SECRET_KEY (optional): " baidu_secret

read -r -p "PODI_INTERNAL_BASE_URL (e.g. http://<podi-host>:8099) [leave empty for coze on same host]: " podi_internal

mkdir -p "$(dirname "$backend_env")"
cat >"$backend_env" <<EOF
DATABASE_URL=${database_url}
${service_token:+SERVICE_API_TOKEN=${service_token}}
${volc_key:+VOLCENGINE_API_KEY=${volc_key}}
${kie_key:+KIE_API_KEY=${kie_key}}
${baidu_key:+BAIDU_API_KEY=${baidu_key}}
${baidu_secret:+BAIDU_SECRET_KEY=${baidu_secret}}
${podi_internal:+PODI_INTERNAL_BASE_URL=${podi_internal}}
EOF

echo
echo "Wrote $backend_env"
echo "Next:"
echo "  - backend: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt (or uv sync) && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8099"
echo "  - migrations: cd backend && .venv/bin/alembic upgrade head"

