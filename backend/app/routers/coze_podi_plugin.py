"""Coze Studio plugin endpoints for PODI abilities.

We expose a custom OpenAPI document that Coze can import as a plugin, with one
tool per ability. Requests are trusted internal calls (single-host deployment),
so we keep auth lightweight and rely on network isolation + optional service token.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.constants.kie_model_catalog import build_coze_param_suggestion
from app.constants.kie_model_catalog import get_kie_model
from app.constants.kie_model_catalog import list_kie_models
from app.core.db import get_session
from app.models.integration import Ability, AbilityTask, ComfyuiLora, Executor
from app.schemas import abilities as ability_schemas
from app.services.ability_invocation import ability_invocation_service
from app.services.ability_logs import ability_log_service
from app.services.ability_seed import ensure_default_abilities
from app.services.ability_task_service import get_ability_task_service
from app.services.task_id_codec import decode_task_id, encode_task_id
from app.services.executor_seed import ensure_default_executors
from app.services.auth_service import auth_service
from app.services.comfyui_lora_catalog_service import collect_functional_lora_names
from app.services.executors.registry import registry
from app.services.integration_test import integration_test_service


router = APIRouter(prefix="/api/coze/podi", tags=["coze-plugin"])

MAX_QUEUE_PER_EXECUTOR = 10
ERR_CODE_COMFYUI_QUEUE_FULL = "Q1001"
ERR_CODE_COMMERCIAL_QUEUE_FULL = "Q2001"


def _format_task_error(code: str, message: str) -> str:
    safe_message = " ".join(str(message).strip().split())
    safe_message = safe_message.replace("|", "/")
    return f"ERR|{code}|{safe_message}"


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


def _drop_none_deep(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_none_deep(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none_deep(v) for v in value]
    return value


def _resolve_executor_info(executor_id: str | None) -> dict[str, Any]:
    if not isinstance(executor_id, str) or not executor_id.strip():
        return {}
    executor_id = executor_id.strip()
    info: dict[str, Any] = {"executorId": executor_id}
    try:
        with get_session() as session:
            ex = session.get(Executor, executor_id)
        if not ex:
            return info
        cfg = ex.config or {}
        base_url = (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip() or None
        info["executorName"] = ex.name or None
        info["executorBaseUrl"] = base_url
    except Exception:
        return info
    return info


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


def _normalize_coze_task_status(raw_status: Any) -> str:
    text = str(raw_status or "").strip().lower()
    if text in {"success", "succeeded", "completed", "done", "ok"}:
        return "succeeded"
    if text in {"failed", "error", "timeout", "rejected"}:
        return "failed"
    if text in {"running", "processing", "in_progress"}:
        return "running"
    if text in {"queued", "pending", "created"}:
        return "queued"
    if text in {"cancelled", "canceled", "stopped", "aborted"}:
        return "failed"
    return "running"


def _limit_comfyui_images(capability_key: Any, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    key = str(capability_key or "").strip().lower()
    # 四方连续当前只保留最终成品图，忽略 workflow 偶发输出的额外图片。
    if key == "sifang_lianxu":
        return images[:1]
    return images


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
        # Keep commas inside URL query string (e.g. "...u=1,2&..."),
        # only split commas that begin another URL.
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for part in re.split(r"[，,](?=https?://)", line):
                candidate = part.strip().strip("，,")
                if candidate:
                    urls.append(candidate)
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


def _normalize_base_model_tag(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def _match_lora_base_model(row: ComfyuiLora, base_model_query: str | None) -> bool:
    if not base_model_query:
        return True
    target = _normalize_base_model_tag(base_model_query)
    if not target:
        return True
    values: list[str] = []
    if isinstance(row.base_model, str) and row.base_model.strip():
        values.append(row.base_model.strip())
    if isinstance(row.base_models, list):
        values.extend([str(item).strip() for item in row.base_models if str(item).strip()])
    if not values:
        return False
    for item in values:
        normalized = _normalize_base_model_tag(item)
        if normalized == target or target in normalized or normalized in target:
            return True
    return False


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
            "executorId": _nullable_str("Assigned executor id (if resolved)."),
            "executorName": _nullable_str("Assigned executor name (if resolved)."),
            "executorBaseUrl": _nullable_str("Assigned executor base URL (if resolved)."),
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

    queue_summary_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "totalRunning": {"type": "integer"},
            "totalPending": {"type": "integer"},
            "totalCount": {"type": "integer"},
            "timestamp": {"type": "string", "description": "Server time (ISO 8601)."},
            "servers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "executorId": {"type": "string"},
                        "baseUrl": {"type": "string"},
                        "runningCount": {"type": "integer"},
                        "pendingCount": {"type": "integer"},
                        "queueMaxSize": {"type": "integer", "nullable": True},
                        "supported": {"type": "boolean"},
                        "message": {"type": "string", "nullable": True},
                    },
                },
            },
        },
    }
    lora_catalog_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "executorId": {"type": "string", "nullable": True},
            "baseUrl": {"type": "string", "nullable": True},
            "count": {"type": "integer"},
            "installedCount": {"type": "integer"},
            "loraNames": {"type": "array", "items": {"type": "string"}},
            "untrackedNames": {"type": "array", "items": {"type": "string"}},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fileName": {"type": "string"},
                        "displayName": {"type": "string"},
                        "status": {"type": "string"},
                        "installed": {"type": "boolean"},
                        "baseModels": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }
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

    # ComfyUI queue summary (used for centralized scheduling).
    paths["/api/coze/podi/comfyui/queue-summary"] = {
        "post": {
            "operationId": "podi_comfyui_queue_summary",
            "summary": "PODI · ComfyUI 队列汇总",
            "description": "返回全部 ComfyUI 执行节点的队列数量，可选传 executorIds 过滤。",
            "requestBody": {
                "required": False,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "executorIds": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                }
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Queue summary",
                    "content": {"application/json": {"schema": queue_summary_schema}},
                }
            },
        }
    }
    paths["/api/coze/podi/comfyui/lora-catalog"] = {
        "post": {
            "operationId": "podi_comfyui_lora_catalog",
            "summary": "PODI · ComfyUI LoRA 查询",
            "description": "查询 LoRA 目录，可按基座模型筛选；支持指定 executorId 返回当前服务器安装状态。",
            "requestBody": {
                "required": False,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "executorId": {"type": "string", "nullable": True},
                                "q": {"type": "string", "nullable": True},
                                "status": {"type": "string", "nullable": True},
                                "baseModel": {"type": "string", "nullable": True},
                                "installedOnly": {"type": "boolean", "nullable": True},
                                "includeUntracked": {"type": "boolean", "nullable": True},
                                "limit": {"type": "integer", "nullable": True},
                                "functionalOnly": {
                                    "type": "boolean",
                                    "nullable": True,
                                    "description": "仅返回功能可用 LoRA。默认 false。",
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "LoRA catalog result",
                    "content": {"application/json": {"schema": lora_catalog_schema}},
                }
            },
        }
    }
    paths["/api/coze/podi/comfyui/lora-catalog/default"] = {
        "post": {
            "operationId": "podi_comfyui_lora_catalog_default",
            "summary": "PODI · ComfyUI LoRA 查询（零参数）",
            "description": "直接返回已启用 LoRA 清单。可空参调用，也支持传入可选默认参数。",
            "requestBody": {
                "required": False,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "default": "active",
                                    "description": "LoRA 状态 Status。默认 active。",
                                },
                                "baseModel": {
                                    "type": "string",
                                    "nullable": True,
                                    "description": "基座模型 Base Model（可选）。如 qwen_image_edit/flux/sdxl。",
                                },
                                "limit": {
                                    "type": "integer",
                                    "default": 500,
                                    "description": "返回上限 Limit，默认 500，最大 5000。",
                                },
                                "functionalOnly": {
                                    "type": "boolean",
                                    "default": True,
                                    "description": "仅返回功能可用 LoRA。默认 true。",
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "LoRA catalog result",
                    "content": {"application/json": {"schema": lora_catalog_schema}},
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
    allowed.add("/api/coze/podi/comfyui/queue-summary")
    if "comfyui" in providers:
        allowed.add("/api/coze/podi/comfyui/lora-catalog")
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
        required = schema.get("required")
        if isinstance(required, list):
            replaced = False
            new_required: list[str] = []
            for item in required:
                if item in image_keys:
                    replaced = True
                    if "url" not in new_required:
                        new_required.append("url")
                elif isinstance(item, str):
                    if item not in new_required:
                        new_required.append(item)
            if replaced:
                schema["required"] = new_required
        # Drop the legacy single-image keys from the schema to avoid confusing Coze users.
        # (Backend still accepts them for backward compatibility.)
        for k in image_keys:
            props.pop(k, None)

    return doc


def _build_kie_catalog_openapi(request: Request) -> dict[str, Any]:
    server = _server_from_request(request)
    list_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "modelKey": {"type": "string"},
                        "displayName": {"type": "string"},
                        "providerModel": {"type": "string"},
                        "mediaType": {"type": "string", "enum": ["image", "video"]},
                        "status": {"type": "string"},
                        "summary": {"type": "string"},
                        "abilityKey": {"type": "string", "nullable": True},
                        "docsUrl": {"type": "string"},
                        "pricingHint": {"type": "string", "nullable": True},
                        "supports": {"type": "object"},
                    },
                },
            },
        },
    }
    schema_response: dict[str, Any] = {
        "type": "object",
        "properties": {
            "model": {"type": "object"},
            "cozeSuggestion": {"type": "object"},
        },
    }
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "PODI KIE 模型查询",
            "version": "0.1.0",
            "description": "查询 KIE 模型与参数定义，不执行任务。",
        },
        "servers": [{"url": server}],
        "paths": {
            "/api/coze/podi/kie/models/list/default": {
                "post": {
                    "operationId": "podi_kie_models_list_default",
                    "summary": "PODI · KIE 模型列表（零参数）",
                    "description": "返回启用中的 KIE 模型结构化列表（默认 all + active，可空参）。",
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "mediaType": {
                                            "type": "string",
                                            "enum": ["all", "image", "video"],
                                            "default": "all",
                                            "description": "模型类型 Media Type。all/image/video，默认 all。",
                                        },
                                        "status": {
                                            "type": "string",
                                            "enum": ["all", "active", "preview"],
                                            "default": "active",
                                            "description": "模型状态 Status。默认 active。",
                                        },
                                        "q": {
                                            "type": "string",
                                            "nullable": True,
                                            "description": "关键字搜索 Keyword（可选）。",
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Model list",
                            "content": {"application/json": {"schema": list_schema}},
                        }
                    },
                }
            },
            "/api/coze/podi/kie/models/schema": {
                "post": {
                    "operationId": "podi_kie_models_schema",
                    "summary": "PODI · KIE 模型参数",
                    "description": "按 modelKey 查询标准参数 schema 与 Coze 封装建议。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["modelKey"],
                                    "properties": {
                                        "modelKey": {
                                            "type": "string",
                                            "description": "模型标识 Model Key。例：nano_banana_2_image_to_image。",
                                        }
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Model schema",
                            "content": {"application/json": {"schema": schema_response}},
                        }
                    },
                }
            },
        },
    }


def _normalize_kie_model_key(model_key: str | None) -> str:
    raw = str(model_key or "").strip()
    if not raw:
        return ""
    return raw.replace("-", "_")


def _build_kie_single_model_openapi(request: Request, model_key: str) -> dict[str, Any]:
    server = _server_from_request(request)
    model = get_kie_model(model_key)
    if not model:
        raise HTTPException(status_code=404, detail="KIE_MODEL_NOT_FOUND")
    display_name = str(model.get("displayName") or model_key)
    path = f"/api/coze/podi/kie/models/{model_key}/schema"
    schema_response: dict[str, Any] = {
        "type": "object",
        "properties": {
            "model": {"type": "object"},
            "cozeSuggestion": {"type": "object"},
        },
    }
    return {
        "openapi": "3.0.0",
        "info": {
            "title": f"PODI KIE · {display_name}",
            "version": "0.1.0",
            "description": f"{display_name} 专用参数查询工具箱。",
        },
        "servers": [{"url": server}],
        "paths": {
            path: {
                "post": {
                    "operationId": f"podi_kie_{model_key}_schema",
                    "summary": f"PODI · {display_name} 参数查询",
                    "description": "无需入参，直接返回该模型参数 schema 与 Coze 封装建议。",
                    "responses": {
                        "200": {
                            "description": "Model schema",
                            "content": {"application/json": {"schema": schema_response}},
                        }
                    },
                }
            }
        },
    }


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


@router.get("/comfyui/lora/openapi.json")
def get_comfyui_lora_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI ComfyUI LoRA query-only plugin."""
    # Keep this OpenAPI public so Coze can import the toolbox URL directly.
    # The real tool endpoint still performs internal/token auth checks.
    server = _server_from_request(request)
    doc = _build_openapi(podi_server=server)
    paths = doc.get("paths") or {}
    allowed = {"/api/coze/podi/comfyui/lora-catalog/default"}
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    doc["info"]["title"] = "PODI ComfyUI LoRA 查询"
    doc["info"]["description"] = "仅用于 LoRA 查询（零参数），不包含任何生图或执行类工具。"
    return doc


@router.get("/comfyui/execute/duotu-ronghe/openapi.json")
def get_comfyui_duotu_ronghe_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for standalone ComfyUI 多图融合 toolbox."""
    doc = _build_openapi_filtered(
        request=request,
        providers={"comfyui"},
        title="PODI ComfyUI 执行 · 多图融合",
        description="ComfyUI 多图融合独立工具箱（含提交工具与任务轮询）。",
        prefer_url_field=True,
    )
    paths = doc.get("paths") or {}
    allowed = {
        "/api/coze/podi/tools/comfyui/duotu_ronghe",
        "/api/coze/podi/tasks/get",
    }
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    return doc


@router.get("/comfyui/execute/yinhua-tiqu-lora-8step/openapi.json")
def get_comfyui_yinhua_tiqu_lora_8step_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for standalone ComfyUI 8步加速可换LoRA toolbox."""
    # Keep this OpenAPI public so Coze can import the toolbox URL directly.
    # The real execution and task polling endpoints still enforce internal/token auth.
    doc = _build_openapi_filtered(
        request=request,
        providers={"comfyui"},
        title="PODI ComfyUI 执行 · 8步加速可换LoRA",
        description="ComfyUI 8步加速可换LoRA独立工具箱（含提交工具与任务轮询）。",
        prefer_url_field=True,
    )
    paths = doc.get("paths") or {}
    allowed = {
        "/api/coze/podi/tools/comfyui/yinhua_tiqu_lora_8step",
        "/api/coze/podi/tasks/get",
    }
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    return doc


@router.get("/kie/catalog/openapi.json")
def get_kie_catalog_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for PODI KIE model query-only plugin."""
    # Keep this OpenAPI public so Coze can import directly.
    return _build_kie_catalog_openapi(request)


@router.get("/kie/catalog/{model_key}/openapi.json")
def get_kie_single_model_openapi(request: Request, model_key: str) -> dict[str, Any]:
    """OpenAPI for one KIE model only (query schema)."""
    normalized_key = _normalize_kie_model_key(model_key)
    return _build_kie_single_model_openapi(request, normalized_key)


@router.get("/kie/execute/{model_key}/openapi.json")
def get_kie_single_model_execute_openapi(request: Request, model_key: str) -> dict[str, Any]:
    """OpenAPI for one KIE model execution toolbox."""
    normalized_key = _normalize_kie_model_key(model_key)
    model = get_kie_model(normalized_key)
    if not model:
        raise HTTPException(status_code=404, detail="KIE_MODEL_NOT_FOUND")
    ability_key = str(model.get("abilityKey") or "").strip()
    if not ability_key:
        raise HTTPException(status_code=404, detail="KIE_ABILITY_NOT_CONFIGURED")
    doc = _build_openapi_filtered(
        request=request,
        providers={"kie"},
        title=f"PODI KIE 执行 · {model.get('displayName') or ability_key}",
        description="单模型执行工具箱（含提交工具与任务轮询）。",
        prefer_url_field=True,
    )
    paths = doc.get("paths") or {}
    allowed = {
        f"/api/coze/podi/tools/kie/{ability_key}",
        "/api/coze/podi/tasks/get",
    }
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    return doc


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
        "executorId",
        "executorName",
        "executorBaseUrl",
        "expectedImageCount",
        "logId",
        "requestId",
        "debugRequest",
        "debugResponse",
    }

    def _coerce_positive_int(v: Any) -> int | None:
        try:
            n = int(v)
            return n if n > 0 else None
        except (TypeError, ValueError):
            return None

    def _prune(result: dict[str, Any]) -> dict[str, Any]:
        pruned: dict[str, Any] = {}
        for k, v in result.items():
            if k not in allowed_out_keys:
                continue
            if k == "taskStatus":
                v = _normalize_coze_task_status(v)
            if v is None:
                continue
            pruned[k] = v
        return pruned

    def _queue_limit_response(code: str, message: str, executor_hint: str | None) -> dict[str, Any]:
        executor_info = _resolve_executor_info(executor_hint if isinstance(executor_hint, str) else None)
        task_error = _format_task_error(code, message)
        return _prune(
            {
                "text": "queue_full",
                "texts": [message],
                "taskId": task_error,
                "taskStatus": "failed",
                **executor_info,
                "debugRequest": None,
                "debugResponse": message,
            }
        )
    provider_lower = provider.lower()
    ability_meta = ability.extra_metadata or {}
    api_type = str(ability_meta.get("api_type") or "").lower()
    async_api_types = {"image_generation", "video_generation", "market_image_to_image", "market_text_to_video"}
    async_providers = {"volcengine", "kie"}
    force_async = bool(
        ability_meta.get("async_mode")
        or ability_meta.get("async")
        or ability_meta.get("callback_mode")
    )

    # ComfyUI tends to queue and can exceed Coze's single-node timeout. For robustness,
    # submit it as an async task and let Coze poll via `podi_task_get`.
    if provider_lower == "comfyui":
        if not executor_id:
            executor_id = ability_invocation_service._pick_comfyui_executor_id(ability, body)  # type: ignore[attr-defined]
        if executor_id:
            payload.executorId = executor_id
        executor_info = _resolve_executor_info(executor_id)
        if executor_id:
            pending_count = get_ability_task_service().count_pending_by_executor(
                executor_id=executor_id,
                providers=["comfyui"],
                limit=MAX_QUEUE_PER_EXECUTOR,
            )
            if pending_count >= MAX_QUEUE_PER_EXECUTOR:
                message = f"COMFYUI_QUEUE_FULL(limit={MAX_QUEUE_PER_EXECUTOR}, current={pending_count})"
                return _queue_limit_response(ERR_CODE_COMFYUI_QUEUE_FULL, message, executor_id)
            try:
                queue_status = integration_test_service.get_comfyui_queue_status(executor_id=executor_id)
                if queue_status.get("supported", True):
                    running = int(queue_status.get("runningCount") or 0)
                    pending = int(queue_status.get("pendingCount") or 0)
                    total = running + pending
                    if total >= MAX_QUEUE_PER_EXECUTOR:
                        message = f"COMFYUI_QUEUE_FULL(limit={MAX_QUEUE_PER_EXECUTOR}, current={total})"
                        return _queue_limit_response(ERR_CODE_COMFYUI_QUEUE_FULL, message, executor_id)
            except Exception:
                # If queue status fails, continue to submit instead of blocking.
                pass

        # Best-effort: we know batch for the common ComfyUI flows we expose.
        expected_images = 1
        if capability_key in {"jisu_chuli", "zhongsu_tisheng"}:
            expected_images = _coerce_positive_int(body.get("batch") or body.get("amount") or body.get("n")) or 1
        elif capability_key in {"yinhua_tiqu", "yinhua_tiqu_lora_8step"}:
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
                **executor_info,
                "expectedImageCount": expected_images,
                "logId": task.get("log_id"),
                "imageUrls": [],
                "videoUrls": [],
                "debugRequest": None,
                "debugResponse": None,
            }
        )

    # Commercial models that now return an async id + unified callback should also
    # be queued as AbilityTask so Coze can poll via /tasks/get.
    if force_async or (provider_lower in async_providers and api_type in async_api_types):
        if not executor_id:
            executor_id = ability.executor_id
        if not executor_id:
            executor_id = ability_invocation_service._pick_default_executor_id(provider_lower)  # type: ignore[attr-defined]
        if executor_id:
            payload.executorId = executor_id
            pending_count = get_ability_task_service().count_pending_by_executor(
                executor_id=executor_id,
                providers=[provider_lower],
                limit=MAX_QUEUE_PER_EXECUTOR,
            )
            if pending_count >= MAX_QUEUE_PER_EXECUTOR:
                message = f"COMMERCIAL_QUEUE_FULL(limit={MAX_QUEUE_PER_EXECUTOR}, current={pending_count})"
                return _queue_limit_response(ERR_CODE_COMMERCIAL_QUEUE_FULL, message, executor_id)
        executor_info = _resolve_executor_info(executor_id)
        expected_images = (
            _coerce_positive_int(
                body.get("n")
                or body.get("batch")
                or body.get("amount")
                or body.get("batch_count")
                or body.get("batchCount")
                or body.get("repeat_count")
            )
            or (
                ability_meta.get("max_output_images")
                if isinstance(ability_meta.get("max_output_images"), int)
                else None
            )
        )
        if expected_images:
            payload.metadata = (payload.metadata or {}) | {"expectedImageCount": expected_images}

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
                **executor_info,
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
    executor_hint = (
        (meta.get("executorId") if isinstance(meta, dict) else None)
        or executor_id
    )
    executor_info = _resolve_executor_info(executor_hint if isinstance(executor_hint, str) else None)
    external_task_id = encode_task_id(
        task_id=str(resp_dict.get("requestId") or "").strip(),
        provider=provider,
        executor_id=(executor_hint if isinstance(executor_hint, str) and executor_hint.strip() else None),
    )
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
            "taskId": external_task_id or (str(provider_task_id).strip() if isinstance(provider_task_id, (str, int)) else None),
            "taskStatus": str(provider_task_status or resp_dict.get("status") or "").strip() or None,
            **executor_info,
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
    capability_key = task.get("capability_key")
    status = task.get("status")
    result_payload = task.get("result_payload") or {}
    req_payload = task.get("request_payload") or {}
    expected_images = None
    if isinstance(req_payload, dict):
        meta = req_payload.get("metadata")
        if isinstance(meta, dict):
            expected_images = meta.get("expectedImageCount")
    executor_id = None
    if isinstance(result_payload, dict):
        meta = result_payload.get("metadata")
        if isinstance(meta, dict):
            executor_id = meta.get("executorId")
    if not executor_id and isinstance(req_payload, dict):
        executor_id = req_payload.get("executorId")
    if not executor_id and isinstance(raw_task_id, str) and raw_task_id.strip().startswith("t1."):
        parts = raw_task_id.strip().split(".")
        if len(parts) >= 3:
            candidate = parts[-2].strip()
            if candidate:
                executor_id = candidate
    executor_info = _resolve_executor_info(executor_id if isinstance(executor_id, str) else None)

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
            capability_key = task.get("capability_key")
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
        "executorId",
        "executorName",
        "executorBaseUrl",
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
            if k == "taskStatus":
                v = _normalize_coze_task_status(v)
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
        if isinstance(images, list):
            images = _limit_comfyui_images(capability_key, images)

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
            **executor_info,
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
            **executor_info,
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
        provider = str(result_payload.get("provider") or task.get("ability_provider") or "").lower()
        # KIE: try a lightweight status pull to finalize long-running tasks.
        if provider == "kie":
            meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
            kie_task_id = meta.get("taskId")
            kie_executor_id = meta.get("executorId")
            if isinstance(kie_task_id, str) and kie_task_id.strip() and isinstance(kie_executor_id, str) and kie_executor_id.strip():
                try:
                    with get_session() as session:
                        db_task = session.get(AbilityTask, task_id.strip())
                        if db_task and (db_task.ability_provider or "").lower() == "kie":
                            settings = get_settings()
                            timeout_seconds = int(getattr(settings, "kie_task_timeout_seconds", 0) or 0)
                            started_at = db_task.started_at or db_task.created_at
                            if timeout_seconds > 0 and started_at:
                                elapsed = (datetime.utcnow() - started_at).total_seconds()
                                if elapsed > timeout_seconds:
                                    db_task.status = "failed"
                                    db_task.error_message = "KIE_TIMEOUT"
                                    db_task.finished_at = datetime.utcnow()
                                    try:
                                        db_task.duration_ms = int(elapsed * 1000)
                                    except Exception:
                                        pass
                                    next_payload = dict(result_payload)
                                    next_payload["status"] = "failed"
                                    db_task.result_payload = next_payload
                                    session.add(db_task)
                                    session.commit()
                                    task = get_ability_task_service().to_dict(db_task)
                                    status = task.get("status")
                                    result_payload = task.get("result_payload") or {}
                                    # Return failed immediately on hard timeout.
                                    return _prune(
                                        {
                                            "text": "failed",
                                            "texts": ["failed"],
                                            "taskId": external_task_id or task.get("id"),
                                            "taskStatus": status,
                                            **executor_info,
                                            "expectedImageCount": expected_images,
                                            "logId": task.get("log_id"),
                                            "requestId": None,
                                            "imageUrl": None,
                                            "imageUrls": [],
                                            "videoUrl": None,
                                            "videoUrls": [],
                                            "debugRequest": None,
                                            "debugResponse": "KIE_TIMEOUT",
                                        }
                                    )
                            fetched = integration_test_service.fetch_kie_market_result(
                                executor_id=kie_executor_id.strip(),
                                task_id=kie_task_id.strip(),
                                timeout=18.0,
                                max_retries=1,
                            )
                            state = str(fetched.get("state") or "").lower()
                            urls = fetched.get("resultUrls") if isinstance(fetched.get("resultUrls"), list) else []
                            assets = fetched.get("storedAssets") if isinstance(fetched.get("storedAssets"), list) else []
                            if state == "success" and (urls or assets):
                                if not assets and urls:
                                    assets = [{"url": u} for u in urls if isinstance(u, str) and u.strip()]
                                next_payload = dict(result_payload)
                                next_payload["images"] = assets
                                next_payload["assets"] = assets
                                next_payload["status"] = "succeeded"
                                db_task.status = "succeeded"
                                db_task.result_payload = next_payload
                                db_task.finished_at = datetime.utcnow()
                                if not db_task.duration_ms and db_task.started_at:
                                    try:
                                        db_task.duration_ms = int(
                                            (datetime.now(timezone.utc) - db_task.started_at).total_seconds() * 1000
                                        )
                                    except Exception:
                                        pass
                                session.add(db_task)
                                session.commit()
                                try:
                                    ability_log_service.finish_success(
                                        db_task.log_id,
                                        response_payload=next_payload,
                                        duration_ms=db_task.duration_ms,
                                    )
                                except Exception:
                                    pass
                                task = get_ability_task_service().to_dict(db_task)
                                status = task.get("status")
                                result_payload = task.get("result_payload") or {}
                            elif state == "fail":
                                db_task.status = "failed"
                                db_task.error_message = "KIE_TASK_FAILED"
                                db_task.finished_at = datetime.utcnow()
                                session.add(db_task)
                                session.commit()
                                task = get_ability_task_service().to_dict(db_task)
                                status = task.get("status")
                                result_payload = task.get("result_payload") or {}
                except Exception as exc:
                    try:
                        with get_session() as session:
                            db_task = session.get(AbilityTask, task_id.strip())
                            if db_task:
                                db_task.error_message = str(exc)[:240]
                                session.add(db_task)
                                session.commit()
                    except Exception:
                        pass

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
                        **executor_info,
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
                        **executor_info,
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
                        entry = None
                        if isinstance(data, dict):
                            prompt_entry = data.get(prompt_id)
                            if isinstance(prompt_entry, dict):
                                entry = prompt_entry
                            elif isinstance(data.get("outputs"), dict):
                                # Some ComfyUI deployments return the history entry directly.
                                entry = data
                        if not isinstance(entry, dict):
                            return _prune(
                                {
                                    "text": status or "running",
                                    "texts": [status or "running"],
                                    "taskId": task.get("id"),
                                    "taskStatus": status,
                                    **executor_info,
                                    "expectedImageCount": expected_images,
                                    "logId": task.get("log_id"),
                                    "requestId": None,
                                    "imageUrl": None,
                                    "imageUrls": [],
                                    "videoUrl": None,
                                    "videoUrls": [],
                                    "debugRequest": None,
                                    "debugResponse": "COMFYUI_NOT_READY",
                                }
                            )

                        output_node_ids = None
                        if isinstance(meta, dict):
                            raw_ids = meta.get("outputNodeIds")
                            if isinstance(raw_ids, list):
                                output_node_ids = {str(x) for x in raw_ids if str(x).strip()}
                        outputs = adapter._extract_outputs(entry, output_node_ids=output_node_ids)  # type: ignore[attr-defined]
                        hist = outputs.get("history") if isinstance(outputs, dict) else None
                        status_dict = hist.get("status") if isinstance(hist, dict) else None
                        status_str = str((status_dict or {}).get("status_str") or "").lower()

                        if status_str == "error":
                            db_task.status = "failed"
                            db_task.error_message = "COMFYUI_ERROR"
                            db_task.finished_at = datetime.utcnow()
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
                                    **executor_info,
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
                                    **executor_info,
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
                        images = _limit_comfyui_images(capability_key, images)
                        if not images:
                            return _prune(
                                {
                                    "text": status or "running",
                                    "texts": [status or "running"],
                                    "taskId": task.get("id"),
                                    "taskStatus": status,
                                    **executor_info,
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
                            db_task.error_message = None
                            db_task.finished_at = datetime.utcnow()
                            if not db_task.duration_ms and db_task.started_at:
                                try:
                                    db_task.duration_ms = int(
                                        (datetime.now(timezone.utc) - db_task.started_at).total_seconds() * 1000
                                    )
                                except Exception:
                                    pass
                            session.add(db_task)
                            session.commit()
                            try:
                                ability_log_service.finish_success(
                                    db_task.log_id,
                                    response_payload=next_payload,
                                    duration_ms=db_task.duration_ms,
                                )
                            except Exception:
                                pass
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
        **executor_info,
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


@router.post("/comfyui/queue-summary")
def get_comfyui_queue_summary(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    _require_internal(request)
    executor_ids: list[str] | None = None
    if isinstance(body, dict):
        raw = body.get("executorIds")
        if isinstance(raw, list):
            executor_ids = [str(x).strip() for x in raw if isinstance(x, (str, int)) and str(x).strip()]
    result = integration_test_service.get_comfyui_queue_summary(executor_ids=executor_ids)
    # Coze's schema validator is strict; drop nulls to avoid type mismatches.
    servers = []
    for item in result.get("servers") or []:
        if not isinstance(item, dict):
            continue
        if item.get("queueMaxSize") is None:
            try:
                item["queueMaxSize"] = int((item.get("runningCount") or 0) + (item.get("pendingCount") or 0))
            except (TypeError, ValueError):
                item["queueMaxSize"] = 0
        cleaned = {k: v for k, v in item.items() if v is not None}
        servers.append(cleaned)
    result["servers"] = servers
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    return result


@router.post("/comfyui/lora-catalog")
def get_comfyui_lora_catalog(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    # Query-only toolbox endpoint: keep it publicly callable for Coze debugging/import flows.
    # No write side effects.
    body = body if isinstance(body, dict) else {}
    executor_id = str(body.get("executorId") or "").strip() or None
    query = str(body.get("q") or "").strip() or None
    status = str(body.get("status") or "active").strip() or None
    base_model = str(body.get("baseModel") or "").strip() or None
    installed_only = _truthy(body.get("installedOnly"))
    include_untracked = _truthy(body.get("includeUntracked"))
    functional_only = _truthy(body.get("functionalOnly"))
    raw_limit = body.get("limit")
    try:
        limit = int(raw_limit) if raw_limit is not None else 500
    except (TypeError, ValueError):
        limit = 500
    limit = max(1, min(limit, 5000))

    functional_names: set[str] = set()
    with get_session() as session:
        rows: list[ComfyuiLora] = []
        try:
            stmt = select(ComfyuiLora)
            if status and status.lower() != "all":
                stmt = stmt.where(ComfyuiLora.status == status)
            if query:
                keyword = f"%{query}%"
                stmt = stmt.where(or_(ComfyuiLora.file_name.like(keyword), ComfyuiLora.display_name.like(keyword)))
            rows = session.execute(stmt.order_by(ComfyuiLora.updated_at.desc()).limit(limit)).scalars().all()
            if functional_only:
                functional_names = collect_functional_lora_names(session)
        except SQLAlchemyError:
            rows = []
            functional_names = set()

    installed_set: set[str] = set()
    base_url: str | None = None
    if executor_id:
        try:
            catalog = integration_test_service.get_comfyui_model_catalog(executor_id=executor_id)
            raw_files = catalog.get("models", {}).get("lora") or []
            installed_set = {str(item).strip() for item in raw_files if str(item).strip()}
            base_url = str(catalog.get("baseUrl") or "").strip() or None
        except Exception:
            installed_set = set()
            base_url = None

    items: list[dict[str, Any]] = []
    tracked_files: set[str] = set()
    for row in rows:
        if functional_only and functional_names and row.file_name not in functional_names:
            continue
        if not _match_lora_base_model(row, base_model):
            continue
        installed = row.file_name in installed_set if executor_id else False
        if installed_only and executor_id and not installed:
            continue
        base_models: list[str] = []
        if isinstance(row.base_models, list):
            base_models = [str(item).strip() for item in row.base_models if str(item).strip()]
        elif isinstance(row.base_model, str) and row.base_model.strip():
            base_models = [row.base_model.strip()]
        tags = [str(item).strip() for item in (row.tags or []) if str(item).strip()]
        items.append(
            {
                "fileName": row.file_name,
                "displayName": row.display_name or row.file_name,
                "status": row.status,
                "installed": installed,
                "baseModels": base_models,
                "tags": tags,
            }
        )
        tracked_files.add(row.file_name)

    untracked_names: list[str] = []
    if include_untracked and executor_id and installed_set:
        candidates = installed_set - tracked_files
        if query:
            lowered = query.lower()
            candidates = {name for name in candidates if lowered in name.lower()}
        untracked_names = sorted(candidates)[:limit]

    return _drop_none_deep(
        {
        "executorId": executor_id,
        "baseUrl": base_url,
        "count": len(items),
        "installedCount": sum(1 for item in items if item.get("installed")),
        "loraNames": [item["fileName"] for item in items],
        "lora_names": [item["fileName"] for item in items],
        "untrackedNames": untracked_names,
        "untracked_names": untracked_names,
        "items": items,
        }
    )


@router.post("/comfyui/lora-catalog/default")
def get_comfyui_lora_catalog_default(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Zero-parameter LoRA catalog for Coze toolbox."""
    body = body if isinstance(body, dict) else {}
    defaults = {
        "status": body.get("status") or "active",
        "baseModel": body.get("baseModel"),
        "limit": body.get("limit"),
        "functionalOnly": body.get("functionalOnly", True),
    }
    return get_comfyui_lora_catalog(request, defaults)


@router.post("/kie/models/list")
def get_kie_models_list(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    # Query-only toolbox endpoint: keep it publicly callable for Coze debugging/import flows.
    # No write side effects.
    body = body if isinstance(body, dict) else {}
    media_type = str(body.get("mediaType") or "all").strip().lower()
    keyword = str(body.get("q") or "").strip() or None
    status = str(body.get("status") or "active").strip().lower()
    if media_type not in {"all", "image", "video"}:
        media_type = "all"
    if status not in {"all", "active", "preview"}:
        status = "active"
    items = list_kie_models(media_type=media_type, keyword=keyword, status=status)
    model_keys = [str(item.get("modelKey") or "").strip() for item in items if str(item.get("modelKey") or "").strip()]
    return _drop_none_deep(
        {
            "count": len(items),
            "items": items,
            "modelKeys": model_keys,
            "model_keys": model_keys,
            "mediaTypes": sorted({str(item.get("mediaType") or "").strip() for item in items if str(item.get("mediaType") or "").strip()}),
            "media_types": sorted({str(item.get("mediaType") or "").strip() for item in items if str(item.get("mediaType") or "").strip()}),
        }
    )


@router.post("/kie/models/list/default")
def get_kie_models_list_default(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    # Zero-parameter model list for Coze toolbox.
    body = body if isinstance(body, dict) else {}
    media_type = str(body.get("mediaType") or "all").strip().lower()
    keyword = str(body.get("q") or "").strip() or None
    status = str(body.get("status") or "active").strip().lower()
    if media_type not in {"all", "image", "video"}:
        media_type = "all"
    if status not in {"all", "active", "preview"}:
        status = "active"
    items = list_kie_models(media_type=media_type, keyword=keyword, status=status)
    model_keys = [str(item.get("modelKey") or "").strip() for item in items if str(item.get("modelKey") or "").strip()]
    return _drop_none_deep(
        {
            "count": len(items),
            "items": items,
            "modelKeys": model_keys,
            "model_keys": model_keys,
            "mediaTypes": sorted({str(item.get("mediaType") or "").strip() for item in items if str(item.get("mediaType") or "").strip()}),
            "media_types": sorted({str(item.get("mediaType") or "").strip() for item in items if str(item.get("mediaType") or "").strip()}),
        }
    )


@router.post("/kie/models/schema")
def get_kie_model_schema(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    # Query-only toolbox endpoint: keep it publicly callable for Coze debugging/import flows.
    # No write side effects.
    body = body if isinstance(body, dict) else {}
    model_key = str(body.get("modelKey") or "").strip()
    if not model_key:
        raise HTTPException(status_code=400, detail="KIE_MODEL_KEY_REQUIRED")
    model = get_kie_model(model_key)
    if not model:
        raise HTTPException(status_code=404, detail="KIE_MODEL_NOT_FOUND")
    return {"model": model, "cozeSuggestion": build_coze_param_suggestion(model)}


@router.post("/kie/models/{model_key}/schema")
def get_kie_model_schema_by_path(request: Request, model_key: str) -> dict[str, Any]:
    # Query-only toolbox endpoint: keep it publicly callable for Coze debugging/import flows.
    # No write side effects.
    normalized_key = _normalize_kie_model_key(model_key)
    if not normalized_key:
        raise HTTPException(status_code=400, detail="KIE_MODEL_KEY_REQUIRED")
    model = get_kie_model(normalized_key)
    if not model:
        raise HTTPException(status_code=404, detail="KIE_MODEL_NOT_FOUND")
    return {"model": model, "cozeSuggestion": build_coze_param_suggestion(model)}
