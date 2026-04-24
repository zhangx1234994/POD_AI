# vendor-api-ops

`vendor-api-ops` is the execution surface for third-party vendor APIs.

It is intentionally separate from:

- `backend`: control plane, Coze toolbox contract, task/log/OSS orchestration.
- `image-ops`: local image processing primitives.
- ComfyUI executors: workflow/GPU execution.

## Current Scope

MVP includes:

- `GET /health`
- `GET /v1/providers`
- `POST /v1/providers/{provider}/egress-check`
- `POST /v1/invocations`
- `GET /v1/invocations/{vendorInvocationId}`
- `POST /v1/keys`
- `GET /v1/keys`
- `PATCH /v1/keys/{keyId}`

Provider registry now covers OpenAI, OpenAI-compatible relays, Volcengine,
Baidu, and KIE. Keys, invocations, and usage logs are persisted in SQLite by
default (`runtime/vendor-api-ops.sqlite3`).

## Run

```bash
cd vendor-api-ops
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8310
```

Without `uv`:

```bash
cd vendor-api-ops
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8310
```

## Egress Check

```bash
curl -sS http://127.0.0.1:8310/health
curl -sS http://127.0.0.1:8310/v1/providers
curl -sS -X POST http://127.0.0.1:8310/v1/providers/openai/egress-check \
  -H 'Content-Type: application/json' \
  -d '{"check":"models","includeAuth":false}'
```

`401` from OpenAI is still considered reachable for unauthenticated egress
checks. Timeout means the node does not have a usable route or proxy.

## Invocation Contract

```bash
curl -sS -X POST http://127.0.0.1:8310/v1/invocations \
  -H 'Content-Type: application/json' \
  -d '{
    "provider":"openai",
    "capabilityKey":"gpt_image_2_edit",
    "model":"gpt-image-2",
    "apiType":"image_edit",
    "executionMode":"sync",
    "inputs":{"prompt":"edit image","mockImageUrl":"https://example.com/out.png"}
  }'
```

`sync`/`sync_then_store` returns `succeeded`; `async_submit_poll` and
`callback` return `running` with `vendorInvocationId` and `vendorTaskId`.
Backend stores the platform task and polls this service, not the vendor
directly.

## KIE Adapter

KIE now uses the real submit/poll contract:

- Submit: `POST /api/v1/jobs/createTask`
- Poll: `GET /api/v1/jobs/recordInfo?taskId=...`

Configure a key either through `POST /v1/keys` or `KIE_API_KEY`. Runtime key
reads only expose `keyPreview`, never the raw secret.

## OpenAI / Compatible Adapter

OpenAI image generation/editing now uses the real Images API style contract:

- Generation: `POST /v1/images/generations`
- Edit: `POST /v1/images/edits`
- Edit inputs support `images: [{"image_url": "..."}]` and optional `mask: {"image_url": "..."}`

Use `OPENAI_BASE_URL`/`OPENAI_API_KEY` for OpenAI, or
`OPENAI_COMPATIBLE_BASE_URL`/`OPENAI_COMPATIBLE_API_KEY` for relay providers.
The same values can also be stored through `/v1/keys`.

## Volcengine Adapter

Volcengine now uses the Ark-style contracts already used by backend legacy
tests:

- Chat: `POST /api/v3/chat/completions`
- Images: `POST /api/v3/images/generations`
- Video task submit passthrough: `POST /api/v3/contents/generations/tasks`

Configure `VOLCENGINE_BASE_URL` and `VOLCENGINE_API_KEY`, or create keys with
`provider=volcengine`.

## Baidu Adapter

Baidu image processing now runs in `vendor-api-ops`:

- Token: `POST /oauth/2.0/token`
- Image process endpoint comes from `inputs.request_endpoint`, falling back to
  `/rest/2.0/image-process/v1/image_quality_enhance`
- Source image accepts `image_base64`, `imageBase64`, `image_url`, or input assets

Configure `BAIDU_BASE_URL`, `BAIDU_API_KEY`, and `BAIDU_SECRET_KEY`, or create a
key with both `key` and `secret`.

## Deployment Rule

Coze must not call this service directly.

Stable chain:

```text
Coze -> backend toolbox -> vendor-api executor -> vendor-api-ops -> vendor API
```
