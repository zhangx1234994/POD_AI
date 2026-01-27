#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prodlike.yml}"

echo "[deploy] repo: $ROOT_DIR"
echo "[deploy] commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "[deploy] compose: $COMPOSE_FILE"

if ! command -v docker >/dev/null 2>&1; then
  echo "[deploy] ERROR: docker not found"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[deploy] ERROR: docker compose not available"
  exit 1
fi

if [[ ! -f backend/.env ]]; then
  echo "[deploy] ERROR: backend/.env missing (copy backend/.env.example and fill DATABASE_URL etc.)"
  exit 1
fi

echo "[deploy] building images..."
docker compose -f "$COMPOSE_FILE" build --pull

echo "[deploy] starting containers..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

echo "[deploy] health check..."
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8099/health" >/dev/null 2>&1; then
    echo "[deploy] backend healthy"
    break
  fi
  sleep 2
done

echo "[deploy] urls:"
echo "  - backend:   http://127.0.0.1:8099/health"
echo "  - admin web: http://127.0.0.1:8199/"
echo "  - eval web:  http://127.0.0.1:8200/"

