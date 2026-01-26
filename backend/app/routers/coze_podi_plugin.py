"""Coze Studio plugin endpoints for PODI abilities.

We expose a custom OpenAPI document that Coze can import as a plugin, with one
tool per ability. Requests are trusted internal calls (single-host deployment),
so we keep auth lightweight and rely on network isolation + optional service token.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import Ability, AbilityTask, Executor
from app.schemas import abilities as ability_schemas
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_task_service import get_ability_task_service
from app.services.task_id_codec import decode_task_id, encode_task_id
from app.services.executor_seed import ensure_default_executors
from app.services.auth_service import auth_service
from app.services.executors.registry import registry


router = APIRouter(prefix="/api/coze/podi", tags=["coze-plugin"])


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _is_internal_request(request: Request) -> bool:
    # NOTE: In our local single-host setup, Coze containers reach the host via
    # host.docker.internal and port-forwarding; remote_addr is commonly 127.0.0.1.
    # When behind reverse proxies, trust the first hop in X-Forwarded-For / X-Real-IP.
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    host = forwarded_for or real_ip or ((request.client.host if request.client else "") or "")
    settings = get_settings()
    trusted = (settings.coze_trusted_ips or "").strip()
    if trusted:
        allow = {ip.strip() for ip in trusted.split(",") if ip.strip()}
        if host in allow:
            return True
    if host.startswith("127.") or host == "::1":
        return True
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
        return True
    return False


def _require_internal(request: Request) -> None:
    settings = get_settings()
    # Allow internal network OR explicit service token.
    authz = request.headers.get("authorization") or ""
    token = authz.split(" ", 1)[1].strip() if authz.lower().startswith("bearer ") else None
    if token and settings.service_api_token and token == settings.service_api_token:
        return
    if _is_internal_request(request):
        return
    # Keep the error simple; Coze shows error messages directly.
    from fastapi import HTTPException, status

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INTERNAL_ONLY")


def _field_to_schema(field: dict[str, Any]) -> dict[str, Any]:
    ftype = (field.get("type") or "text").lower()
    schema: dict[str, Any]

    # For Coze workflows, string-typed inputs are much easier to wire/transform.
    # We accept everything as string here and let PODI convert types internally.
    if ftype in {"select"}:
        schema = {"type": "string", "nullable": True}
        options = field.get("options") or []
        enum = []
        for opt in options:
            if isinstance(opt, dict):
                v = opt.get("value")
            else:
                v = opt
            if v is not None:
                enum.append(v)
        if enum:
            schema["enum"] = enum
    elif ftype in {"switch", "boolean"}:
        schema = {"type": "string", "enum": ["true", "false"], "nullable": True}
    elif ftype in {"image"}:
        # Coze's file/image upload often ends up as a URL string. We accept a URL here.
        # NOTE: Coze's schema validator is strict and rejects `format: uri` in some cases,
        # especially for array items. Use plain string for maximum compatibility.
        schema = {"type": "string", "nullable": True}
    else:
        # text / textarea / number (we keep number as string to reduce coercion issues)
        schema = {"type": "string", "nullable": True}

    desc = field.get("description") or field.get("help") or None
    label = field.get("label") or None
    if label and desc:
        schema["description"] = f"{label} - {desc}"
    elif label:
        schema["description"] = str(label)
    elif desc:
        schema["description"] = str(desc)

    default = field.get("default")
    if default is not None:
        # Coze's OpenAPI validator is strict about `default` matching the schema type.
        # We represent most inputs as strings (including "number"), so coerce defaults.
        if schema.get("type") == "string" and not isinstance(default, str):
            default = str(default)
        if schema.get("enum") == ["true", "false"]:
            # Normalize boolean defaults to the allowed enum.
            if str(default).strip().lower() in {"true", "1", "yes", "y", "on"}:
                default = "true"
            else:
                default = "false"
        schema["default"] = default
        # Also mirror defaults into description to make Coze UI clearer.
        schema["description"] = f"{schema.get('description','').strip()} (default={default})".strip()

    return schema


def _extract_urls_from_value(value: Any) -> list[str]:
    """Best-effort URL extraction for Coze tool inputs.

    Coze may send:
    - a plain string (single URL, or multiple lines)
    - a list of strings / dicts
    - a dict with keys like url/ossUrl/sourceUrl
    """

    if value is None:
        return []
    urls: list[str] = []
    if isinstance(value, str):
        normalized = value.replace(",", "\n")
        urls.extend([line.strip() for line in normalized.splitlines() if line.strip()])
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            urls.extend(_extract_urls_from_value(item))
    elif isinstance(value, dict):
        # Common shapes: {"url": "..."} / {"ossUrl": "..."} / {"sourceUrl": "..."}
        for key in ("url", "ossUrl", "oss_url", "sourceUrl", "source_url"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                urls.append(candidate.strip())
                break
        # Nested shapes: {"file": {"url": "..."}} / {"data": {...}} etc.
        if not urls:
            for nested in value.values():
                urls.extend(_extract_urls_from_value(nested))
    # preserve order, de-dup
    seen: set[str] = set()
    dedup: list[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        dedup.append(u)
    return dedup


def _build_openapi(*, podi_server: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    # This plugin runs on our backend. Coze must be able to reach this URL.
    # Prefer the caller-provided server (derived from request host), fallback to config.
    podi_server = (podi_server or settings.podi_internal_base_url).rstrip("/")

    with get_session() as session:
        # Ensure the DB has a usable baseline of executors + abilities.
        # Coze invokes tools without going through our admin UI, so we must seed here.
        ensure_default_executors(session)
        ensure_default_abilities(session)
        abilities = (
            session.execute(
                select(Ability)
                .where(Ability.status == "active")
                .order_by(Ability.provider.asc(), Ability.capability_key.asc())
            )
            .scalars()
            .all()
        )

    paths: dict[str, Any] = {}
    # Coze's OpenAPI importer is strict and tends to reject schemas with complex objects
    # (e.g. additionalProperties). Keep tool responses minimal/primitives only.
    def _nullable_str(desc: str) -> dict[str, Any]:
        return {"type": "string", "nullable": True, "description": desc}

    response_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "text": _nullable_str("First text output (if any)."),
            "texts": {"type": "array", "items": {"type": "string"}, "description": "All text outputs."},
            "imageUrl": _nullable_str("First image URL (OSS preferred)."),
            "imageUrls": {"type": "array", "items": {"type": "string"}, "description": "All image URLs (OSS preferred)."},
            "videoUrl": _nullable_str("First video URL (OSS preferred)."),
            "videoUrls": {"type": "array", "items": {"type": "string"}, "description": "All video URLs (OSS preferred)."},
            "taskId": _nullable_str("Async task id (if submitted asynchronously)."),
            "taskStatus": _nullable_str("Async task status: queued/running/succeeded/failed."),
            "expectedImageCount": {
                "type": "integer",
                "nullable": True,
                "description": "Hint: expected number of output images (e.g. ComfyUI batch).",
            },
            "logId": {"type": "integer", "nullable": True, "description": "PODI log id (if available)."},
            "requestId": _nullable_str("PODI request id (if available)."),
            # String-typed debug fields so Coze never strips them.
            "debugRequest": _nullable_str("Debug: provider request payload (truncated)."),
            "debugResponse": _nullable_str("Debug: provider response payload (truncated)."),
        },
    }

    task_response_schema: dict[str, Any] = response_schema
    for ability in abilities:
        provider = ability.provider
        key = ability.capability_key
        op_id = f"podi_{provider}_{key}"
        display_name = ability.display_name or f"{provider}:{key}"
        description = ability.description or ""
        metadata = ability.extra_metadata or {}

        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                # Keep inputs minimal. Executor selection is handled by PODI (bindings/weights).
            },
        }
        requires_image = bool(metadata.get("requires_image_input"))
        has_image_field = False
        required: list[str] = []
        input_schema = ability.input_schema or {}
        for f in input_schema.get("fields", []) or []:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            name = str(f["name"])
            ftype = (f.get("type") or "").lower()
            if ftype == "image" or name.lower() in {"image", "imageurl", "image_url", "image_urls", "input_urls"}:
                has_image_field = True
            prop_schema = _field_to_schema(f)
            # If the field doesn't specify a default, try to use ability.default_params.
            if "default" not in prop_schema:
                defaults = ability.default_params or {}
                if isinstance(defaults, dict) and name in defaults and defaults[name] is not None:
                    dv = defaults[name]
                    if prop_schema.get("type") == "string" and not isinstance(dv, str):
                        dv = str(dv)
                    if prop_schema.get("enum") == ["true", "false"]:
                        # Normalize boolean defaults to the allowed enum.
                        if str(dv).strip().lower() in {"true", "1", "yes", "y", "on"}:
                            dv = "true"
                        else:
                            dv = "false"
                    prop_schema["default"] = dv
                    prop_schema["description"] = f"{prop_schema.get('description','').strip()} (default={dv})".strip()
            schema["properties"][name] = prop_schema
            if _truthy(f.get("required")):
                required.append(name)

        if requires_image and not has_image_field:
            schema["properties"]["imageUrl"] = {
                "type": "string",
                "nullable": True,
                "description": "Required image URL (recommend OSS URL).",
            }
            # Do NOT mark as required: Coze may send null for unfilled fields, which
            # fails schema validation before reaching our backend. Backend will still
            # enforce required-image semantics (IMAGE_REQUIRED).
        if required:
            schema["required"] = required

        path = f"/api/coze/podi/tools/{provider}/{key}"
        paths[path] = {
            "post": {
                "operationId": op_id,
                "summary": display_name,
                "description": description,
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": schema}},
                },
                "responses": {
                    "200": {
                        "description": "Ability invocation result",
                        "content": {
                            "application/json": {
                                "schema": response_schema,
                            }
                        },
                    }
                },
            }
        }

    # Generic poll tool for async tasks (used for ComfyUI and any long-running ability).
    paths["/api/coze/podi/tasks/get"] = {
        "post": {
            "operationId": "podi_task_get",
            "summary": "PODI · 查询任务状态/结果",
            "description": "输入 taskId 查询任务状态，若已完成返回结果（imageUrl/imageUrls/text 等）。",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"taskId": {"type": "string", "description": "Ability task id"}},
                            "required": ["taskId"],
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Task status/result",
                    "content": {"application/json": {"schema": task_response_schema}},
                }
            },
        }
    }

    return {
        "openapi": "3.0.0",
        "info": {
            "title": "PODI Abilities",
            "version": "0.1.0",
            "description": "Expose PODI atomic abilities as Coze tools (one tool per ability).",
        },
        "servers": [{"url": podi_server}],
        "components": {},
        "paths": paths,
    }

def _server_from_request(request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").strip()
    host = forwarded_host or (request.headers.get("host") or "").strip()
    scheme = forwarded_proto or request.url.scheme
    if host:
        return f"{scheme}://{host}"
    return str(request.base_url).rstrip("/")


def _build_openapi_filtered(
    *,
    request: Request,
    providers: set[str],
    title: str,
    description: str,
    # Coze workflows and our internal docs prefer a single image input key `url`.
    # For provider plugins (especially ComfyUI), we expose `url` instead of `image_url`
    # to reduce wiring/transform overhead in Coze.
    prefer_url_field: bool = True,
) -> dict[str, Any]:
    server = _server_from_request(request)
    doc = _build_openapi(podi_server=server)

    with get_session() as session:
        ensure_default_executors(session)
        ensure_default_abilities(session)
        abilities = (
            session.execute(
                select(Ability)
                .where(Ability.status == "active", Ability.provider.in_(sorted(providers)))
                .order_by(Ability.provider.asc(), Ability.capability_key.asc())
            )
            .scalars()
            .all()
        )

    # Restrict to the selected abilities + common task polling.
    paths = doc.get("paths") or {}
    allowed = {f"/api/coze/podi/tools/{a.provider}/{a.capability_key}" for a in abilities}
    allowed.add("/api/coze/podi/tasks/get")
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    doc["info"]["title"] = title
    doc["info"]["description"] = description

    if not prefer_url_field:
        return doc

    # Rewrite request schemas: `image_url`/`imageUrl`/image-type fields -> `url`.
    # (Backend is permissive and still accepts legacy keys, but this keeps Coze tools stable.)
    for path, item in (doc.get("paths") or {}).items():
        post = item.get("post") if isinstance(item, dict) else None
        if not isinstance(post, dict):
            continue
        rb = post.get("requestBody") if isinstance(post.get("requestBody"), dict) else None
        content = rb.get("content") if isinstance(rb, dict) else None
        app_json = content.get("application/json") if isinstance(content, dict) else None
        schema = app_json.get("schema") if isinstance(app_json, dict) else None
        props = schema.get("properties") if isinstance(schema, dict) else None
        if not isinstance(props, dict):
            continue

        # If a tool already exposes `url`, keep it.
        if "url" in props:
            continue

        # Detect common image keys and collapse into one `url` field.
        image_keys = []
        for key in ("image_url", "imageUrl", "image", "images"):
            if key in props:
                image_keys.append(key)
        # Some abilities use `image_urls`/`input_urls`, but those may be multi-line arrays;
        # we keep them as-is and only provide a single-url shortcut.
        if not image_keys:
            continue

        # Pick the best description we can (prefer the schema's description).
        desc = None
        for k in image_keys:
            d = props.get(k, {}).get("description") if isinstance(props.get(k), dict) else None
            if isinstance(d, str) and d.strip():
                desc = d.strip()
                break
        props["url"] = {
            "type": "string",
            "nullable": True,
            "description": desc or "Input image URL (recommend OSS URL).",
        }
        # Drop the legacy single-image keys from the schema to avoid confusing Coze users.
        # (Backend still accepts them for backward compatibility.)
        for k in image_keys:
            props.pop(k, None)

    return doc


@router.get("/openapi.json")
def get_openapi(request: Request) -> dict[str, Any]:
    _require_internal(request)
    return _build_openapi(podi_server=_server_from_request(request))


@router.get("/utils/openapi.json")
def get_utils_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI Utils plugin (only provider=podi utilities)."""
    _require_internal(request)
    server = _server_from_request(request)

    with get_session() as session:
        ensure_default_executors(session)
        ensure_default_abilities(session)
        abilities = (
            session.execute(
                select(Ability)
                .where(Ability.status == "active", Ability.provider == "podi")
                .order_by(Ability.capability_key.asc())
            )
            .scalars()
            .all()
        )

    doc = _build_openapi(podi_server=server)
    paths = doc.get("paths") or {}
    allowed = {f"/api/coze/podi/tools/podi/{a.capability_key}" for a in abilities}
    allowed.add("/api/coze/podi/tasks/get")
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    doc["info"]["title"] = "PODI Utils"
    doc["info"]["description"] = "Internal utility tools (image helpers) for workflows."
    return doc


@router.get("/comfyui/openapi.json")
def get_comfyui_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI ComfyUI plugin."""
    _require_internal(request)
    return _build_openapi_filtered(
        request=request,
        providers={"comfyui"},
        title="PODI ComfyUI",
        description="ComfyUI workflows as Coze tools (URL-based image input).",
        prefer_url_field=True,
    )


@router.get("/kie/openapi.json")
def get_kie_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI KIE plugin."""
    _require_internal(request)
    return _build_openapi_filtered(
        request=request,
        providers={"kie"},
        title="PODI KIE",
        description="KIE Market models as Coze tools.",
        prefer_url_field=True,
    )


@router.get("/baidu/openapi.json")
def get_baidu_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI Baidu plugin."""
    _require_internal(request)
    return _build_openapi_filtered(
        request=request,
        providers={"baidu"},
        title="PODI Baidu",
        description="Baidu image processing tools.",
        prefer_url_field=True,
    )


@router.get("/volcengine/openapi.json")
def get_volcengine_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI Volcengine plugin."""
    _require_internal(request)
    return _build_openapi_filtered(
        request=request,
        providers={"volcengine"},
        title="PODI Volcengine",
        description="Volcengine (Doubao) tools.",
        prefer_url_field=True,
    )


@router.get("/abilities", response_model=ability_schemas.AbilityListResponse)
def list_abilities_for_coze(request: Request) -> ability_schemas.AbilityListResponse:
    _require_internal(request)
    items = ability_invocation_service.list_public_abilities()
    return ability_schemas.AbilityListResponse(items=items)


@router.post("/tools/{provider}/{capability_key}")
def invoke_tool(
    provider: str,
    capability_key: str,
    request: Request,
    body: dict[str, Any],
) -> dict[str, Any]:
    _require_internal(request)
    with get_session() as session:
        # Same as above: Coze may call tools before any admin page seeds executors.
        ensure_default_executors(session)
        ability = (
            session.execute(
                select(Ability).where(Ability.provider == provider, Ability.capability_key == capability_key)
            )
            .scalars()
            .first()
        )
        if not ability:
            from fastapi import HTTPException, status

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ABILITY_NOT_FOUND")

    # Translate Coze tool input -> our generic invoke request.
    # NOTE: Coze may send image inputs as structured objects; accept broadly.
    executor_id = body.pop("executorId", None)  # legacy; currently not exposed in OpenAPI
    image_url = None
    image_base64 = None
    url_candidates: list[str] = []
    # Coze may send image inputs under a variety of keys depending on the UI widget.
    # Be permissive here; backend still validates required-image semantics per ability.
    for key in (
        "url",
        "urls",
        "imageUrl",
        "image_url",
        "image_urls",
        "input_urls",
        "image",
        "images",
        "imageList",
        "image_list",
        "fileList",
        "file_list",
        "files",
    ):
        url_candidates.extend(_extract_urls_from_value(body.get(key)))
    # Fallback: scan all values for structured image objects (e.g. {url, ossUrl, ...}).
    for v in body.values():
        url_candidates.extend(_extract_urls_from_value(v))
    if url_candidates:
        image_url = url_candidates[0]
    for key in ("imageBase64", "image_base64"):
        if isinstance(body.get(key), str) and body[key].strip():
            image_base64 = body.pop(key).strip()
            break

    payload = ability_schemas.AbilityInvokeRequest(
        executorId=executor_id,
        inputs=body,
        imageUrl=image_url,
        imageBase64=image_base64,
    )

    # For internal system integration, we execute as a trusted service user.
    user = auth_service.build_service_user()

    # Coze validates responses strictly (null vs string, extra fields, etc.).
    # Keep a stable, minimal response shape and omit null fields.
    allowed_out_keys = {
        "text",
        "texts",
        "imageUrl",
        "imageUrls",
        "videoUrl",
        "videoUrls",
        "taskId",
        "taskStatus",
        "expectedImageCount",
        "logId",
        "requestId",
        "debugRequest",
        "debugResponse",
    }

    def _prune(result: dict[str, Any]) -> dict[str, Any]:
        pruned: dict[str, Any] = {}
        for k, v in result.items():
            if k not in allowed_out_keys:
                continue
            if v is None:
                continue
            pruned[k] = v
        return pruned
    # ComfyUI tends to queue and can exceed Coze's single-node timeout. For robustness,
    # submit it as an async task and let Coze poll via `podi_task_get`.
    if provider.lower() == "comfyui":
        def _coerce_positive_int(v: Any) -> int | None:
            try:
                n = int(v)
                return n if n > 0 else None
            except (TypeError, ValueError):
                return None

        # Best-effort: we know batch for the common ComfyUI flows we expose.
        expected_images = 1
        if capability_key in {"jisu_chuli", "zhongsu_tisheng"}:
            expected_images = _coerce_positive_int(body.get("batch") or body.get("amount") or body.get("n")) or 1
        elif capability_key in {"yinhua_tiqu"}:
            expected_images = (
                _coerce_positive_int(body.get("batch") or body.get("batch_count") or body.get("batchCount") or body.get("repeat_count") or body.get("n"))
                or 1
            )

        # Persist the hint with the task so `/tasks/get` can always surface it.
        payload.metadata = (payload.metadata or {}) | {"expectedImageCount": expected_images}

        # Store as a system task (no user FK) to keep internal integrations simple.
        task = get_ability_task_service().enqueue(ability_id=ability.id, payload=payload, user=None)
        external_task_id = encode_task_id(
            task_id=str(task.get("id") or ""),
            provider=provider,
            executor_id=(executor_id if isinstance(executor_id, str) and executor_id.strip() else None),
        )
        return _prune(
            {
                "text": "submitted",
                "texts": ["submitted"],
                "taskId": external_task_id or task.get("id"),
                "taskStatus": task.get("status"),
                "expectedImageCount": expected_images,
                "logId": task.get("log_id"),
                "imageUrls": [],
                "videoUrls": [],
                "debugRequest": None,
                "debugResponse": None,
            }
        )

    resp = ability_invocation_service.invoke(ability_id=ability.id, payload=payload, user=user, request=request)
    resp_dict = resp.model_dump()
    texts = resp_dict.get("texts") or []
    images = resp_dict.get("images") or []
    videos = resp_dict.get("videos") or []
    # Some providers (e.g. KIE) are async on their side and return a provider task id/state.
    # Surface it as taskId/taskStatus so Coze workflows can branch/poll if needed.
    meta = resp_dict.get("metadata") if isinstance(resp_dict.get("metadata"), dict) else {}
    provider_task_id = meta.get("taskId") if isinstance(meta, dict) else None
    provider_task_status = meta.get("state") if isinstance(meta, dict) else None
    raw_payload = resp_dict.get("raw") if isinstance(resp_dict.get("raw"), dict) else {}
    debug_request = ""
    debug_response = ""
    if isinstance(raw_payload, dict):
        try:
            debug_request = str(raw_payload.get("request") or "")[:4000]
        except Exception:
            debug_request = ""
        try:
            debug_response = str(raw_payload.get("response") or raw_payload)[:4000]
        except Exception:
            debug_response = ""

    def _first_url(items: list[dict[str, Any]]) -> str | None:
        for it in items:
            if not isinstance(it, dict):
                continue
            for k in ("ossUrl", "sourceUrl", "url"):
                v = it.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return None

    def _all_urls(items: list[dict[str, Any]]) -> list[str]:
        out: list[str] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            for k in ("ossUrl", "sourceUrl", "url"):
                v = it.get(k)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
        # preserve order, de-dup
        seen: set[str] = set()
        dedup: list[str] = []
        for u in out:
            if u in seen:
                continue
            seen.add(u)
            dedup.append(u)
        return dedup

    return _prune(
        {
            "text": texts[0] if isinstance(texts, list) and texts else None,
            "texts": texts if isinstance(texts, list) else [],
            "imageUrl": _first_url(images) if isinstance(images, list) else None,
            "imageUrls": _all_urls(images) if isinstance(images, list) else [],
            "videoUrl": _first_url(videos) if isinstance(videos, list) else None,
            "videoUrls": _all_urls(videos) if isinstance(videos, list) else [],
            "taskId": str(provider_task_id).strip() if isinstance(provider_task_id, (str, int)) else None,
            "taskStatus": str(provider_task_status).strip() if isinstance(provider_task_status, (str, int)) else None,
            "logId": resp_dict.get("logId"),
            "requestId": resp_dict.get("requestId"),
            "debugRequest": debug_request or None,
            "debugResponse": debug_response or None,
        }
    )


@router.post("/tasks/get")
def get_task(body: dict[str, Any], request: Request) -> dict[str, Any]:
    _require_internal(request)
    raw_task_id = body.get("taskId")
    task_id = decode_task_id(raw_task_id)
    if not isinstance(task_id, str) or not task_id.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="TASK_ID_REQUIRED")

    # Keep backward compatibility:
    # - if caller already uses the new parseable format, echo it back as taskId
    # - otherwise keep returning the raw DB id to avoid surprising older clients
    external_task_id: str | None = None
    if isinstance(raw_task_id, str) and raw_task_id.strip().startswith("t1."):
        external_task_id = raw_task_id.strip()
    with get_session() as session:
        task_row = session.get(AbilityTask, task_id.strip())
        if not task_row:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="TASK_NOT_FOUND")
        task = get_ability_task_service().to_dict(task_row)
    status = task.get("status")
    result_payload = task.get("result_payload") or {}
    req_payload = task.get("request_payload") or {}
    expected_images = None
    if isinstance(req_payload, dict):
        meta = req_payload.get("metadata")
        if isinstance(meta, dict):
            expected_images = meta.get("expectedImageCount")

    # If we know this task should output multiple images (batch), give it a short grace
    # period so Coze polling is less likely to observe a "running" task too early.
    # (We still keep this bounded to avoid long blocking calls.)
    if status in {"queued", "running"} and isinstance(expected_images, int) and expected_images > 1:
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            time.sleep(0.8)
            with get_session() as session:
                task_row = session.get(AbilityTask, task_id.strip())
                if not task_row:
                    break
                task = get_ability_task_service().to_dict(task_row)
            status = task.get("status")
            if status not in {"queued", "running"}:
                break
        result_payload = task.get("result_payload") or {}

    allowed_out_keys = {
        "text",
        "texts",
        "imageUrl",
        "imageUrls",
        "videoUrl",
        "videoUrls",
        "taskId",
        "taskStatus",
        "expectedImageCount",
        "logId",
        "requestId",
        "debugRequest",
        "debugResponse",
    }

    def _prune(result: dict[str, Any]) -> dict[str, Any]:
        pruned: dict[str, Any] = {}
        for k, v in result.items():
            if k not in allowed_out_keys:
                continue
            if v is None:
                continue
            pruned[k] = v
        return pruned

    # Recovery: ComfyUI "submit-only" tasks must stay `running` until the ComfyUI history
    # reaches success and outputs are ingested. If a task was accidentally marked `failed`
    # while the underlying ComfyUI job is still running, revive it so polling can continue.
    if status == "failed" and isinstance(result_payload, dict):
        meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
        prompt_id = meta.get("promptId") or meta.get("taskId")
        base_url = meta.get("baseUrl")
        if (
            isinstance(prompt_id, str)
            and prompt_id.strip()
            and isinstance(base_url, str)
            and base_url.strip()
            and str(result_payload.get("provider") or "").lower() == "comfyui"
            and str(result_payload.get("status") or "").lower() in {"queued", "running"}
        ):
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id.strip())
                if db_task and (db_task.ability_provider or "").lower() == "comfyui":
                    db_task.status = "running"
                    db_task.finished_at = None
                    session.add(db_task)
                    session.commit()
                    task = get_ability_task_service().to_dict(db_task)
                    status = task.get("status")
                    result_payload = task.get("result_payload") or {}
    # If completed, return the same flattened shape as invoke_tool.
    if status == "succeeded" and isinstance(result_payload, dict):
        texts = result_payload.get("texts") or []
        images = result_payload.get("images") or []
        videos = result_payload.get("videos") or []

        def _first_url(items: list[dict[str, Any]]) -> str | None:
            for it in items:
                if not isinstance(it, dict):
                    continue
                for k in ("ossUrl", "sourceUrl", "url"):
                    v = it.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            return None

        def _all_urls(items: list[dict[str, Any]]) -> list[str]:
            out: list[str] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                for k in ("ossUrl", "sourceUrl", "url"):
                    v = it.get(k)
                    if isinstance(v, str) and v.strip():
                        out.append(v.strip())
                        break
            seen: set[str] = set()
            dedup: list[str] = []
            for u in out:
                if u in seen:
                    continue
                seen.add(u)
                dedup.append(u)
            return dedup

        return _prune(
            {
            "text": texts[0] if isinstance(texts, list) and texts else None,
            "texts": texts if isinstance(texts, list) else [],
            "imageUrl": _first_url(images) if isinstance(images, list) else None,
            "imageUrls": _all_urls(images) if isinstance(images, list) else [],
            "videoUrl": _first_url(videos) if isinstance(videos, list) else None,
            "videoUrls": _all_urls(videos) if isinstance(videos, list) else [],
            "taskId": external_task_id or task.get("id"),
            "taskStatus": status,
            "expectedImageCount": expected_images,
            "logId": task.get("log_id"),
            "requestId": (result_payload.get("requestId") if isinstance(result_payload, dict) else None),
            "debugRequest": None,
            "debugResponse": None,
            }
        )

    if status == "failed":
        return _prune(
            {
            "text": "failed",
            "texts": ["failed"],
            "taskId": external_task_id or task.get("id"),
            "taskStatus": status,
            "expectedImageCount": expected_images,
            "logId": task.get("log_id"),
            "requestId": None,
            "imageUrl": None,
            "imageUrls": [],
            "videoUrl": None,
            "videoUrls": [],
            "debugRequest": None,
            "debugResponse": (task.get("error_message") if isinstance(task, dict) else None),
            }
        )

    # queued/running
    # Special-case: ComfyUI submitted-only tasks. If we already have promptId/baseUrl,
    # try to finalize on demand when Coze polls.
    if status in {"queued", "running"} and isinstance(result_payload, dict):
        meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
        prompt_id = meta.get("promptId") or meta.get("taskId")
        base_url = meta.get("baseUrl")
        executor_id = meta.get("executorId")
        # Multi-ComfyUI support: prefer the executor's configured base_url if executorId is available.
        if isinstance(executor_id, str) and executor_id.strip():
            try:
                with get_session() as session:
                    ex = session.get(Executor, executor_id.strip())
                if ex:
                    cfg = ex.config or {}
                    ex_base = (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip()
                    if ex_base:
                        base_url = ex_base
            except Exception:
                # Best-effort: fall back to stored baseUrl in metadata.
                pass

        if isinstance(prompt_id, str) and prompt_id.strip() and isinstance(base_url, str) and base_url.strip():
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id.strip())
                if db_task and (db_task.ability_provider or "").lower() == "comfyui":
                    try:
                        import httpx
                        from types import SimpleNamespace

                        adapter = registry.get("comfyui")
                        if adapter is None:
                            raise RuntimeError("COMFYUI_ADAPTER_MISSING")

                        history_url = f"{base_url.rstrip('/')}/history/{prompt_id}"
                        resp = httpx.get(history_url, timeout=15)
                        if resp.status_code != 200:
                            raise RuntimeError(f"COMFYUI_HISTORY_HTTP_{resp.status_code}")
                        data = resp.json()
                        entry = data.get(prompt_id) if isinstance(data, dict) else None
                        if not isinstance(entry, dict):
                            raise RuntimeError("COMFYUI_HISTORY_INVALID")

                        outputs = adapter._extract_outputs(entry)  # type: ignore[attr-defined]
                        hist = outputs.get("history") if isinstance(outputs, dict) else None
                        status_dict = hist.get("status") if isinstance(hist, dict) else None
                        status_str = str((status_dict or {}).get("status_str") or "").lower()

                        if status_str == "error":
                            db_task.status = "failed"
                            db_task.error_message = "COMFYUI_ERROR"
                            session.add(db_task)
                            session.commit()
                            task = get_ability_task_service().to_dict(db_task)
                            status = task.get("status")
                            result_payload = task.get("result_payload") or {}

                        if status_str != "success":
                            # Still running; keep the DB task as-is.
                            return _prune(
                                {
                                    "text": status or "running",
                                    "texts": [status or "running"],
                                    "taskId": task.get("id"),
                                    "taskStatus": status,
                                    "expectedImageCount": expected_images,
                                    "logId": task.get("log_id"),
                                    "requestId": None,
                                    "imageUrl": None,
                                    "imageUrls": [],
                                    "videoUrl": None,
                                    "videoUrls": [],
                                    "debugRequest": None,
                                    "debugResponse": f"COMFYUI_STATUS_{status_str or 'running'}",
                                }
                            )

                        images = outputs.get("images") if isinstance(outputs, dict) else None
                        if not isinstance(images, list) or not images:
                            # Some ComfyUI builds mark success before batch outputs are fully persisted.
                            return _prune(
                                {
                                    "text": status or "running",
                                    "texts": [status or "running"],
                                    "taskId": task.get("id"),
                                    "taskStatus": status,
                                    "expectedImageCount": expected_images,
                                    "logId": task.get("log_id"),
                                    "requestId": None,
                                    "imageUrl": None,
                                    "imageUrls": [],
                                    "videoUrl": None,
                                    "videoUrls": [],
                                    "debugRequest": None,
                                    "debugResponse": "COMFYUI_IMAGES_EMPTY",
                                }
                            )

                        # Ingest all images into OSS.
                        from app.services.executors.base import ExecutionContext

                        ctx = ExecutionContext(
                            task=SimpleNamespace(id=db_task.id, user_id=str(db_task.user_id or "coze"), assets=[]),
                            workflow=SimpleNamespace(id="coze_task_get", definition={}, extra_metadata={}),
                            executor=SimpleNamespace(id=executor_id or "comfyui", base_url=base_url, config={}),
                            payload={},
                            api_key=None,
                        )
                        assets: list[dict[str, Any]] = []
                        for img in images:
                            if not isinstance(img, dict):
                                continue
                            source_url = img.get("url") or adapter._build_image_url(base_url.rstrip("/"), img)  # type: ignore[attr-defined]
                            base64_data = img.get("base64")
                            if source_url:
                                asset = adapter._store_remote_asset(source_url, ctx, tag="comfyui")  # type: ignore[attr-defined]
                            elif base64_data:
                                asset = adapter._store_base64_asset(base64_data, ctx, tag="comfyui")  # type: ignore[attr-defined]
                            else:
                                asset = None
                            if asset:
                                assets.append(asset)

                        if assets:
                            next_payload = dict(result_payload)
                            next_payload["images"] = assets
                            next_payload["assets"] = assets
                            next_payload["status"] = "succeeded"
                            db_task.status = "succeeded"
                            db_task.result_payload = next_payload
                            session.add(db_task)
                            session.commit()
                            task = get_ability_task_service().to_dict(db_task)
                            status = task.get("status")
                            result_payload = task.get("result_payload") or {}
                    except Exception as exc:
                        # Best-effort; keep running but persist a diagnostic hint so operators
                        # can see why one ComfyUI server behaves differently (network/HTTP/etc).
                        try:
                            hint = str(exc)[:240]
                            # Don't persist transient polling states as task "errors".
                            if hint not in {"COMFYUI_NOT_READY", "COMFYUI_IMAGES_EMPTY"}:
                                db_task.error_message = hint
                            session.add(db_task)
                            session.commit()
                        except Exception:
                            pass

    return _prune(
        {
        "text": status or "running",
        "texts": [status or "running"],
        "taskId": external_task_id or task.get("id"),
        "taskStatus": status,
        "expectedImageCount": expected_images,
        "logId": task.get("log_id"),
        "requestId": None,
        "imageUrl": None,
        "imageUrls": [],
        "videoUrl": None,
        "videoUrls": [],
        "debugRequest": None,
        "debugResponse": (task.get("error_message") if isinstance(task, dict) else None),
        }
    )
