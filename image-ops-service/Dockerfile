FROM python:3.11-slim AS runtime

WORKDIR /app/image-ops-service

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY image-ops-service/pyproject.toml ./pyproject.toml
COPY image-ops-service/app ./app

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

EXPOSE 8301

ENV TZ=Asia/Shanghai

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8301"]
