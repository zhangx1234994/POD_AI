FROM python:3.11-slim AS runtime

WORKDIR /app/backend

# Minimal OS deps for common wheels (cryptography, pillow, etc.)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Install backend dependencies declared in pyproject.toml
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

# Entrypoint runs DB migrations then starts uvicorn.
COPY backend/scripts/docker-entrypoint.sh /usr/local/bin/podi-backend-entrypoint
RUN chmod +x /usr/local/bin/podi-backend-entrypoint

EXPOSE 8099

ENV TZ=Asia/Shanghai

ENTRYPOINT ["podi-backend-entrypoint"]

