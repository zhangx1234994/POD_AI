# Coze Studio Integration

This repo integrates PODI "atomic abilities" into Coze Studio as a Plugin (OpenAPI tools).

Key URLs
- PODI backend: `https://<podi-host>` (local dev: `http://127.0.0.1:8099`)
- PODI admin web: `https://<podi-host>` (local dev: `http://127.0.0.1:8199`)
- Coze Studio web: `https://<coze-host>` (set `COZE_BASE_URL`)

## Plugin OpenAPI

PODI exposes an OpenAPI document for Coze to import:
- `GET https://<podi-host>/api/coze/podi/openapi.json`

If Coze runs in Docker and PODI runs on the host machine, use:
- `GET http://host.docker.internal:8099/api/coze/podi/openapi.json`

Each PODI Ability becomes one Coze tool:
- `POST /api/coze/podi/tools/{provider}/{capability_key}`

Additional monitoring tools:
- `POST /api/coze/podi/comfyui/queue-summary` → returns `totalRunning/totalPending/servers[]` so Coze workflows can check ComfyUI queue health before dispatch.

Coze workflow nodes only show outputs that are declared in the OpenAPI response schema.
This plugin returns a stable response shape across tools:
- `text` / `texts`
- `imageUrl` / `imageUrls`
- `videoUrl` / `videoUrls`
- `taskId` / `taskStatus` (for async tools)
- `podi` (full PODI payload, best-effort)

## Async Behavior (ComfyUI)

ComfyUI tools are executed asynchronously to avoid Coze node timeouts and queue delays:
1) Call a ComfyUI tool (e.g. `comfyui/yinhua_tiqu`) → returns immediately with `taskId`.
2) Poll result with:
   - `POST /api/coze/podi/tasks/get` (tool name: "PODI · 查询任务状态/结果")

### ComfyUI routing (single server in testing)

In early testing we often run only one ComfyUI server to avoid custom-node mismatch.
You can force PODI to route all ComfyUI abilities to a single executor:

```
COMFYUI_DEFAULT_EXECUTOR_ID=executor_comfyui_pattern_extract_158
```

This executor must exist and be `active`.

Note: if you update/publish the plugin, existing workflow nodes may keep old schemas.
If outputs/inputs look wrong, delete the node and re-add it from the plugin.

## Multi-image Output Rule

Some abilities can return multiple images (e.g. Volcengine image generation, KIE market models, ComfyUI batch flows).
We standardize the output as:
- `imageUrls`: all output images (prefer OSS URLs, preserve provider order)
- `imageUrl`: the first image in `imageUrls` (as the "primary" output)

Implementation detail:
- PODI ingests third-party URLs/Base64 into OSS and returns OSS URLs in `resultUrls/assets`.
- Coze plugin flattens PODI outputs into `imageUrl/imageUrls` for easy wiring.

For Volcengine image generation:
- `n` controls the number of requested output images (default 1).
- We clamp `n` to a conservative max of 10. Some models/accounts may enforce a combined limit
  with reference images; PODI will further clamp based on reference count.

## Input Type Convention (Coze)

For easier workflow wiring, Coze plugin tool inputs are exposed as strings (including numbers/booleans).
PODI converts them internally based on `Ability.input_schema`:
- boolean/switch: accepts `true/false/1/0/yes/no/on/off`
- number: accepts integer-like strings

## One-command: create/update + publish plugin

1) Ensure PODI backend is reachable from Coze Studio.
2) Set `COZE_BASE_URL` + `COZE_API_TOKEN` (PAT) in `backend/.env` or env vars.
3) Run:

```bash
bash scripts/ensure_coze_plugin_podi.sh
```

Notes:
- Hosted Coze Studio typically does not allow DB access, so `COZE_FORCE_PASS_DEBUG=0` is recommended.
- Self-hosted Coze Studio can optionally use `scripts/coze_studio_force_debug_pass.py` to bypass
  tool debug gating when needed.

## Troubleshooting

- Plugin imported but not visible in "Tools":
  - It must be published (draft-only plugins won't appear).
  - Re-run `bash scripts/ensure_coze_plugin_podi.sh`.

- Workflow node shows empty outputs:
  - Coze only shows outputs declared in OpenAPI.
  - Ensure you're using the latest published plugin version.
  - Delete/re-add the node in the workflow to refresh the schema.

- Workflow/tool run failed with `..._API_KEY_MISSING`:
  - This means PODI backend does not have a usable vendor key for that provider.
  - Preferred: add keys in PODI admin and bind them to an executor (supports multiple keys + rotation).
    - Create keys: `POST /admin/api-keys` (UI: Integration → API Keys)
    - Bind keys to executor: update executor's `api_key_ids` (UI: Integration → Executors)
  - Legacy fallback: executor `config.apiKey` from `config/executors.yaml` / `backend/.env`.
  - For Baidu (needs apiKey + secretKey), you can set executor config directly:
    - `bash scripts/set_baidu_executor_keys.sh`

- Publish error: `tools in plugin have not debugged yet`:
  - Run:
    - `python3 scripts/coze_studio_force_debug_pass.py --plugin-id <plugin_id>`
  - Then publish again.
