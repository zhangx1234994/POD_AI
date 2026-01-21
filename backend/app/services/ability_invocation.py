"""Runtime ability catalogue + invocation service."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from math import gcd
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select

import httpx

from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import Ability, Executor, WorkflowBinding
from app.models.user import User
from app.schemas import abilities as schemas
from app.services.ability_logs import AbilityLogStartParams, ability_log_service
from app.services.ability_seed import ensure_default_abilities
from app.services.executor_seed import ensure_default_executors
from app.services.integration_test import integration_test_service
from app.services.coze_client import coze_client
from app.services.workflow_seed import ensure_default_bindings, ensure_default_workflows


@dataclass
class _ImageBundle:
    image_url: str | None
    image_base64: str | None
    image_list: list[dict[str, Any]]


@dataclass
class _InvocationContext:
    request_id: str
    source: str
    user: User | None
    payload: schemas.AbilityInvokeRequest


class AbilityInvocationService:
    """Expose a uniform invoke/list API over capability catalogue."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    # -------- catalogue helpers -------- #
    def list_public_abilities(self) -> list[schemas.AbilityPublicInfo]:
        with get_session() as session:
            ensure_default_abilities(session)
            stmt = (
                select(Ability)
                .where(Ability.status == "active")
                .order_by(Ability.provider.asc(), Ability.capability_key.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._to_public_info(row) for row in rows]

    def get_public_ability(self, ability_id: str) -> schemas.AbilityPublicInfo:
        ability = self._get_ability(ability_id)
        if ability.status != "active":
            raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
        return self._to_public_info(ability)

    # -------- invocation entrypoint -------- #
    def invoke(
        self,
        *,
        ability_id: str,
        payload: schemas.AbilityInvokeRequest,
        user: User | None,
        source: str = "ability-api",
        request: Request | None = None,
    ) -> schemas.AbilityInvokeResponse:
        ability = self._get_ability(ability_id)
        if ability.status != "active":
            raise HTTPException(status_code=400, detail="ABILITY_INACTIVE")
        merged_inputs = self._merge_inputs(ability, payload)
        image_bundle = self._normalize_image_inputs(payload, merged_inputs)
        provider_key = ability.provider.lower()
        executor_id = payload.executorId or ability.executor_id
        # For internal integrations (Coze/automation), we allow omitting executorId and
        # auto-pick an active executor by provider.
        if not executor_id and provider_key == "comfyui":
            # Different ComfyUI servers may have different custom nodes/models installed.
            # Route by action/workflow_key via workflow bindings when possible.
            executor_id = self._pick_comfyui_executor_id(ability, merged_inputs)
        if not executor_id and provider_key not in {"coze", "podi"}:
            executor_id = self._pick_default_executor_id(provider_key)
        if not executor_id and provider_key not in {"coze", "podi"}:
            raise HTTPException(status_code=400, detail="ABILITY_EXECUTOR_NOT_CONFIGURED")
        request_marker = uuid4().hex
        currency, billing_unit, unit_price = self._extract_pricing_metadata(ability)
        request_payload = {
            "inputs": merged_inputs,
            "imageUrl": image_bundle.image_url,
            "hasImageBase64": bool(image_bundle.image_base64),
            "imageListCount": len(image_bundle.image_list),
            "metadata": payload.metadata,
            "userId": user.id if user else (request.client.host if request else None),
        }
        log_id = ability_log_service.start_log(
            AbilityLogStartParams(
                ability_id=ability.id,
                ability_name=ability.display_name,
                provider=ability.provider,
                capability_key=ability.capability_key,
                executor_id=executor_id,
                source=source or "ability-api",
                task_id=request_marker,
                request_payload=self._omit_large_fields(request_payload),
                trace_id=request_marker,
                billing_unit=billing_unit,
                unit_price=unit_price,
                currency=currency,
                cost_amount=unit_price,
            )
        )
        start = time.perf_counter()
        callback_url = payload.callbackUrl
        callback_headers = payload.callbackHeaders
        context = _InvocationContext(
            request_id=request_marker,
            source=source or "ability-api",
            user=user,
            payload=payload,
        )
        try:
            provider_result = self._dispatch_provider(
                ability=ability,
                executor_id=executor_id,
                merged_inputs=merged_inputs,
                images=image_bundle,
                context=context,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            ability_log_service.finish_failure(
                log_id,
                error_message=self._extract_error_message(exc),
                response_payload=self._extract_error_payload(exc),
                duration_ms=duration_ms,
            )
            if callback_url:
                self._schedule_callback(
                    callback_url=callback_url,
                    callback_headers=callback_headers,
                    ability=ability,
                    request_id=request_marker,
                    log_id=log_id,
                    duration_ms=duration_ms,
                    status="failed",
                    result_payload=None,
                    error_payload=self._extract_error_payload(exc) or {"detail": str(exc)},
                )
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        ability_log_service.finish_success(log_id, response_payload=provider_result, duration_ms=duration_ms)
        response_payload = self._build_response_payload(
            ability,
            request_marker,
            provider_result,
            log_id,
            duration_ms=duration_ms,
        )
        if callback_url:
            self._schedule_callback(
                callback_url=callback_url,
                callback_headers=callback_headers,
                ability=ability,
                request_id=request_marker,
                log_id=log_id,
                duration_ms=duration_ms,
                status="success",
                result_payload=response_payload.model_dump(),
                error_payload=None,
            )
        return response_payload

    def _pick_default_executor_id(self, provider_key: str) -> str | None:
        """Pick a default executor for a provider.

        We keep this simple/deterministic:
        - seed default executors (from `config/executors.yaml`) if missing
        - choose the highest-weight active executor of the provider
        """

        with get_session() as session:
            ensure_default_executors(session)
            row = (
                session.execute(
                    select(Executor)
                    .where(Executor.status == "active", Executor.type == provider_key)
                    .order_by(Executor.weight.desc(), Executor.id.asc())
                )
                .scalars()
                .first()
            )
            return row.id if row else None

    def _pick_comfyui_executor_id(self, ability: Ability, merged_inputs: dict[str, Any]) -> str | None:
        """Pick a ComfyUI executor based on workflow binding/action.

        This avoids sending a workflow graph to a ComfyUI node that doesn't have
        required custom nodes installed (which causes /prompt 400 errors).
        """

        settings = get_settings()
        if settings.comfyui_default_executor_id:
            forced_id = settings.comfyui_default_executor_id.strip()
            if forced_id:
                with get_session() as session:
                    executor = session.get(Executor, forced_id)
                    if executor and executor.status == "active" and (executor.type or "").lower() == "comfyui":
                        return executor.id

        metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
        action = (metadata.get("action") or "").strip() or "generic"
        workflow_key = (
            (merged_inputs.get("workflow_key") if isinstance(merged_inputs, dict) else None)
            or metadata.get("workflow_key")
            or ability.capability_key
        )

        # Some actions share the same executor in our current deployment.
        actions = [action]
        if action == "pattern_expand":
            actions.append("pattern_extract")

        with get_session() as session:
            ensure_default_executors(session)
            ensure_default_workflows(session)
            ensure_default_bindings(session)
            # Prefer bindings for the action.
            binding = (
                session.execute(
                    select(WorkflowBinding)
                    .where(WorkflowBinding.enabled.is_(True), WorkflowBinding.action.in_(actions))
                    .order_by(WorkflowBinding.priority.desc(), WorkflowBinding.id.asc())
                )
                .scalars()
                .first()
            )
            if binding:
                executor = session.get(Executor, binding.executor_id)
                if executor and executor.status == "active":
                    return executor.id

        # Fallback: keep current single-host defaults predictable.
        if workflow_key == "sifang_lianxu":
            return "executor_comfyui_seamless_117"
        if workflow_key in {"yinhua_tiqu", "huawen_kuotu", "jisu_chuli", "zhongsu_tisheng"}:
            return "executor_comfyui_pattern_extract_158"
        return None

    # -------- internal helpers -------- #
    def _dispatch_provider(
        self,
        *,
        ability: Ability,
        executor_id: str | None,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
        context: _InvocationContext,
    ) -> dict[str, Any]:
        provider = ability.provider.lower()
        if provider == "podi":
            return self._invoke_podi(ability, merged_inputs, images, context)
        if provider == "baidu":
            return self._invoke_baidu(ability, executor_id, merged_inputs, images)
        if provider == "volcengine":
            return self._invoke_volcengine(ability, executor_id, merged_inputs, images)
        if provider == "comfyui":
            return self._invoke_comfyui(ability, executor_id, merged_inputs, images)
        if provider == "kie":
            return self._invoke_kie(ability, executor_id, merged_inputs, images)
        if provider == "coze":
            return self._invoke_coze(ability, merged_inputs, images, context)
        raise HTTPException(status_code=400, detail=f"ABILITY_PROVIDER_UNSUPPORTED:{provider}")

    def _invoke_podi(
        self,
        ability: Ability,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
        context: _InvocationContext,
    ) -> dict[str, Any]:
        from app.services import podi_image_tools

        key = ability.capability_key
        if key != "expand_mask_color":
            raise HTTPException(status_code=400, detail="PODI_UTILITY_UNSUPPORTED")

        image_url = (
            images.image_url
            or self._pop_first_string(merged_inputs, ["image_url", "imageUrl"])
            or self._pop_first_string(merged_inputs, ["url"])
        )
        image_base64 = images.image_base64 or self._pop_first_string(merged_inputs, ["image_base64", "imageBase64"])
        if not image_url and not image_base64:
            raise HTTPException(status_code=400, detail="IMAGE_REQUIRED")

        def _as_int(name: str) -> int:
            v = merged_inputs.get(name)
            try:
                n = int(str(v).strip())
                return n if n > 0 else 0
            except Exception:
                return 0

        left = _as_int("expand_left")
        right = _as_int("expand_right")
        top = _as_int("expand_top")
        bottom = _as_int("expand_bottom")

        # Prefer base64 input (no network fetch). Otherwise download by URL.
        if image_base64:
            import base64 as _b64

            raw = image_base64.strip()
            if "," in raw and "base64" in raw:
                raw = raw.split(",", 1)[1]
            src_bytes = _b64.b64decode(raw)
            out_bytes = podi_image_tools.expand_with_color(
                image_bytes=src_bytes,
                expand_left=left,
                expand_right=right,
                expand_top=top,
                expand_bottom=bottom,
            )
            upload = oss_service.upload_bytes(
                user_id=str(context.user.id if context.user else "system"),
                filename="expand_mask.png",
                data=out_bytes,
                content_type="image/png",
            )
            asset = {
                "sourceUrl": None,
                "ossUrl": upload.get("url"),
                "ossKey": upload.get("objectKey"),
                "contentType": "image/png",
                "tag": "podi-expand-mask",
            }
        else:
            asset = podi_image_tools.expand_with_color_from_url(
                image_url=str(image_url),
                expand_left=left,
                expand_right=right,
                expand_top=top,
                expand_bottom=bottom,
                user_id=str(context.user.id if context.user else "system"),
                filename="expand_mask.png",
            )

        stored_url = asset.get("ossUrl") if isinstance(asset, dict) else None
        return {
            "provider": "podi",
            "storedUrl": stored_url,
            "assets": [asset] if asset else [],
            "raw": {
                "request": {
                    "capability_key": key,
                    "expand_left": left,
                    "expand_right": right,
                    "expand_top": top,
                    "expand_bottom": bottom,
                    "imageUrl": image_url,
                    "hasImageBase64": bool(image_base64),
                }
            },
        }

    def _invoke_baidu(
        self,
        ability: Ability,
        executor_id: str,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
    ) -> dict[str, Any]:
        image_base64 = images.image_base64 or merged_inputs.get("image_base64")
        image_url = images.image_url or merged_inputs.get("image_url")
        if not image_base64 and not image_url:
            raise HTTPException(status_code=400, detail="IMAGE_REQUIRED")
        params = self._clean_params(self._exclude_keys(merged_inputs, {"image_base64", "image_url"}))
        return integration_test_service.run_baidu_image_process(
            executor_id=executor_id,
            operation=ability.capability_key,
            image_base64=image_base64,
            image_url=image_url,
            params=params,
        )

    def _invoke_volcengine(
        self,
        ability: Ability,
        executor_id: str,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
    ) -> dict[str, Any]:
        metadata = ability.extra_metadata or {}
        api_type = (metadata.get("api_type") or "").lower()
        prompt = self._pop_first_string(merged_inputs, ["prompt", "text"])
        model = self._pop_first_string(merged_inputs, ["model"]) or metadata.get("model_id")
        if not model:
            raise HTTPException(status_code=400, detail="VOLCENGINE_MODEL_REQUIRED")
        if api_type == "chat_completions":
            if not prompt:
                raise HTTPException(status_code=400, detail="PROMPT_REQUIRED")
            extra_params = self._clean_params(merged_inputs)
            return integration_test_service.run_volcengine_chat_completion(
                executor_id=executor_id,
                model=model,
                prompt=prompt,
                image_url=images.image_url,
                params=extra_params or None,
            )
        if api_type == "image_generation":
            if not prompt:
                raise HTTPException(status_code=400, detail="PROMPT_REQUIRED")
            negative_prompt = self._pop_first_string(merged_inputs, ["negative_prompt", "negativePrompt"])
            size = self._pop_first_string(merged_inputs, ["size"])
            response_format = self._pop_first_string(merged_inputs, ["response_format", "responseFormat"])
            sequential = self._pop_first_string(
                merged_inputs,
                [
                    "sequential_image_generation",
                    "sequentialImageGeneration",
                ],
            )
            max_images_raw = self._pop_first_string(
                merged_inputs,
                [
                    "max_images",
                    "maxImages",
                    "sequential_image_generation_max_images",
                ],
            )
            # Support custom width/height (input schema exposes them as "number" but we pass
            # as real ints to the provider).
            width_raw = self._pop_first_string(merged_inputs, ["width"])
            height_raw = self._pop_first_string(merged_inputs, ["height"])
            n_raw = self._pop_first_string(merged_inputs, ["n"])
            try:
                width = int(width_raw) if width_raw is not None else None
            except (TypeError, ValueError):
                width = None
            try:
                height = int(height_raw) if height_raw is not None else None
            except (TypeError, ValueError):
                height = None
            try:
                n_value = int(n_raw) if n_raw is not None else None
            except (TypeError, ValueError):
                n_value = None
            # NOTE: Seedream 4.x image-to-image uses `image` (string or list) and may not
            # support free-form width/height the way OpenAI-style providers do. We keep
            # width/height as optional metadata for our own post-processing, but do not
            # rely on the model honoring them.
            if width and height:
                merged_inputs["width"] = width
                merged_inputs["height"] = height
            reference_urls = self._pop_url_list(
                merged_inputs, ["image_urls", "image_url", "reference_image_urls"]
            )
            bundle_urls = self._urls_from_image_bundle(images)
            combined_urls = self._deduplicate_urls(reference_urls + bundle_urls)
            if combined_urls:
                # Seedream 4.x image-to-image uses `image` (string or list).
                merged_inputs["image"] = combined_urls[0] if len(combined_urls) == 1 else combined_urls

            # Volcengine supports multiple outputs via `n`. Some accounts/models enforce a
            # combined limit with reference images. We clamp to a conservative max=10.
            if n_value is not None:
                if n_value < 1:
                    n_value = 1
                if n_value > 10:
                    n_value = 10
                merged_inputs["n"] = n_value

            # Seedream 4.x multi-image generation uses sequential generation flags, not `n`.
            # Keep it optional and pass through when provided.
            if sequential:
                seq = sequential.strip().lower()
                if seq in {"disabled", "auto"}:
                    merged_inputs["sequential_image_generation"] = seq
                    if seq != "disabled" and max_images_raw is not None:
                        try:
                            max_images = int(str(max_images_raw).strip())
                        except (TypeError, ValueError):
                            max_images = None
                        if max_images and max_images > 0:
                            merged_inputs["sequential_image_generation_options"] = {"max_images": max_images}

            # Coze expects a single JSON response; streaming will break tool execution.
            merged_inputs["stream"] = False
            return integration_test_service.run_volcengine_image_generation(
                executor_id=executor_id,
                model=model,
                prompt=prompt,
                negative_prompt=negative_prompt,
                size=size,
                response_format=response_format,
                params=self._clean_params(merged_inputs) or None,
            )
        raise HTTPException(status_code=400, detail="VOLCENGINE_API_TYPE_UNSUPPORTED")

    def _invoke_comfyui(
        self,
        ability: Ability,
        executor_id: str,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
    ) -> dict[str, Any]:
        metadata = ability.extra_metadata or {}
        workflow_key = (
            merged_inputs.pop("workflow_key", None)
            or metadata.get("workflow_key")
            or ability.capability_key
        )
        if not workflow_key:
            raise HTTPException(status_code=400, detail="COMFYUI_WORKFLOW_KEY_MISSING")
        workflow_params = dict(merged_inputs)
        if images.image_url and "imageUrl" not in workflow_params:
            workflow_params["imageUrl"] = images.image_url
        if images.image_base64 and "imageBase64" not in workflow_params:
            workflow_params["imageBase64"] = images.image_base64
        if images.image_list:
            workflow_params["imageList"] = images.image_list
        return integration_test_service.run_comfyui_workflow(
            executor_id=executor_id,
            workflow_key=workflow_key,
            workflow_params=workflow_params,
        )

    def _invoke_kie(
        self,
        ability: Ability,
        executor_id: str,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
    ) -> dict[str, Any]:
        metadata = ability.extra_metadata or {}
        model = self._pop_first_string(merged_inputs, ["model"]) or metadata.get("model_id")
        if not model:
            raise HTTPException(status_code=400, detail="KIE_MODEL_REQUIRED")
        input_payload = self._extract_input_payload(merged_inputs) or {}
        if "prompt" not in input_payload:
            prompt = self._pop_first_string(merged_inputs, ["prompt"])
            if not prompt:
                raise HTTPException(status_code=400, detail="PROMPT_REQUIRED")
            input_payload["prompt"] = prompt
        array_target = metadata.get("input_array_target")
        url_candidates: list[str] = []
        # KIE "market" models are inconsistent in naming image fields; accept a broad set.
        url_candidates.extend(
            self._pop_url_list(
                merged_inputs,
                [
                    "image_urls",
                    "image_url",
                    "imageUrl",
                    "input_urls",
                    "input_url",
                    "inputUrl",
                ],
            )
        )
        # Some tools may put image inputs under `input` (input_payload) instead of top-level keys.
        url_candidates.extend(
            self._extract_urls_from_value(
                input_payload.get("image_urls")
                or input_payload.get("image_url")
                or input_payload.get("imageUrl")
                or input_payload.get("input_urls")
                or input_payload.get("input_url")
                or input_payload.get("inputUrl")
            )
        )
        url_candidates.extend(self._urls_from_image_bundle(images))
        if array_target:
            existing_entries_value = input_payload.get(array_target)
            # KIE tools are inconsistent: some expect `["url1","url2"]`, others accept
            # `[{"url":"..."}, ...]`. Detect based on existing payload shape.
            use_object_entries = False
            if isinstance(existing_entries_value, list):
                use_object_entries = any(isinstance(item, dict) for item in existing_entries_value)

            seen_urls: set[str] = set()
            normalized_entries: list[Any] = []
            if isinstance(existing_entries_value, list):
                for entry in existing_entries_value:
                    if isinstance(entry, str) and entry.strip():
                        normalized_entries.append(entry.strip())
                        seen_urls.add(entry.strip())
                    elif isinstance(entry, dict) and use_object_entries:
                        normalized_entries.append(entry)
                        first_url = self._extract_urls_from_value(entry)
                        if first_url:
                            seen_urls.add(first_url[0])

            for url in self._deduplicate_urls(url_candidates):
                if url in seen_urls:
                    continue
                normalized_entries.append({"url": url} if use_object_entries else url)
                seen_urls.add(url)

            if not normalized_entries and metadata.get("requires_image_input"):
                raise HTTPException(status_code=400, detail="IMAGE_REQUIRED")
            if normalized_entries:
                input_payload[array_target] = normalized_entries
        elif metadata.get("requires_image_input") and not url_candidates:
            raise HTTPException(status_code=400, detail="IMAGE_REQUIRED")

        # KIE expects most parameters under `input`. Treat leftover fields as input params
        # (keeps Coze form usage simple; avoids silent drops).
        call_back_url = self._pop_first_string(merged_inputs, ["callBackUrl", "callback_url"])
        extra_payload = merged_inputs.pop("extra", None) if isinstance(merged_inputs.get("extra"), dict) else None
        for key, value in list(merged_inputs.items()):
            if isinstance(value, str):
                value = value.strip()
            if value in (None, "", []):
                continue
            input_payload.setdefault(key, value)

        endpoint = metadata.get("request_endpoint")
        return integration_test_service.run_kie_market_task(
            executor_id=executor_id,
            endpoint=endpoint,
            model=model,
            input_payload=input_payload,
            input_array_target=metadata.get("input_array_target"),
            call_back_url=call_back_url,
            extra_payload=self._clean_params(extra_payload) or None,
        )

    def _invoke_coze(
        self,
        ability: Ability,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
        context: _InvocationContext,
    ) -> dict[str, Any]:
        metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
        workflow_id = ability.coze_workflow_id or metadata.get("coze_workflow_id")
        if not workflow_id:
            raise HTTPException(status_code=400, detail="COZE_WORKFLOW_ID_MISSING")
        coze_inputs = dict(merged_inputs or {})
        if images.image_url and not coze_inputs.get("image_url"):
            coze_inputs["image_url"] = images.image_url
        if images.image_base64 and not coze_inputs.get("image_base64"):
            coze_inputs["image_base64"] = images.image_base64
        if images.image_list and not coze_inputs.get("image_list"):
            coze_inputs["image_list"] = list(images.image_list)
        coze_inputs = self._clean_params(coze_inputs)
        ext_payload = self._build_coze_ext(ability, context)
        response = coze_client.run_workflow(
            workflow_id=workflow_id,
            parameters=coze_inputs,
            ext=ext_payload,
            request_id=context.request_id,
        )
        base_resp = response.get("BaseResp") or {}
        status_code = base_resp.get("StatusCode")
        code = response.get("code")
        if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
            message = response.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"
            detail = {
                "code": code,
                "statusCode": status_code,
                "message": message,
                "debugUrl": response.get("debug_url"),
            }
            raise HTTPException(status_code=502, detail=detail)
        parsed_payload = self._parse_coze_payload(response.get("data"))
        provider_result: dict[str, Any] = {
            "provider": "coze",
            "taskId": response.get("execute_id"),
            "state": base_resp.get("StatusMessage"),
            "raw": {"response": response},
        }
        if isinstance(parsed_payload, (dict, list)):
            provider_result["raw"]["parsedData"] = parsed_payload
        elif isinstance(parsed_payload, str):
            provider_result["text"] = parsed_payload
        text_output = self._extract_coze_text(parsed_payload)
        if text_output and not provider_result.get("text"):
            provider_result["text"] = text_output
        result_urls = self._extract_coze_result_urls(parsed_payload)
        if result_urls:
            provider_result["resultUrls"] = result_urls
        if isinstance(parsed_payload, dict):
            assets = parsed_payload.get("assets")
            if isinstance(assets, list):
                provider_result["assets"] = assets
        return provider_result

    # -------- parsing helpers -------- #
    def _merge_inputs(self, ability: Ability, payload: schemas.AbilityInvokeRequest) -> dict[str, Any]:
        merged = dict(ability.default_params or {})
        if payload.inputs:
            # Do not let empty strings clobber defaults. Coze forms often submit "" for
            # optional fields; treating that as "unset" makes workflows much more robust.
            for key, value in payload.inputs.items():
                if isinstance(value, str):
                    value = value.strip()
                if value in (None, "", []):
                    continue
                merged[key] = value
        return self._coerce_input_types(ability, merged)

    def _coerce_input_types(self, ability: Ability, merged: dict[str, Any]) -> dict[str, Any]:
        """Coerce common field types from string inputs.

        Coze workflows prefer all-string inputs; we convert internally based on
        Ability.input_schema field types.
        """

        schema = ability.input_schema or {}
        fields = schema.get("fields") or []
        if not isinstance(fields, list) or not fields:
            return merged

        def truthy(value: str) -> bool:
            v = value.strip().lower()
            return v in {"1", "true", "yes", "y", "on"}

        for f in fields:
            if not isinstance(f, dict):
                continue
            name = f.get("name")
            if not isinstance(name, str) or not name:
                continue
            ftype = (f.get("type") or "").lower()
            if name not in merged:
                continue
            value = merged.get(name)
            if not isinstance(value, str):
                continue
            if ftype in {"switch", "boolean"}:
                merged[name] = truthy(value)
            elif ftype == "number":
                try:
                    merged[name] = int(value.strip())
                except (TypeError, ValueError):
                    # Leave it as-is; provider handler may accept non-int forms.
                    pass
        return merged

    def _normalize_image_inputs(
        self, payload: schemas.AbilityInvokeRequest, merged_inputs: dict[str, Any]
    ) -> _ImageBundle:
        image_url = payload.imageUrl or merged_inputs.get("image_url") or merged_inputs.get("imageUrl")
        image_base64 = payload.imageBase64 or merged_inputs.get("image_base64") or merged_inputs.get("imageBase64")
        image_list: list[dict[str, Any]] = []
        default_image_list = merged_inputs.get("imageList")
        if isinstance(default_image_list, list):
            image_list.extend([item for item in default_image_list if isinstance(item, dict)])
        if payload.images:
            for item in payload.images:
                entry: dict[str, Any] = {}
                if item.name:
                    entry["filename"] = item.name
                if item.ossUrl:
                    entry["ossUrl"] = item.ossUrl
                if item.url:
                    entry["url"] = item.url
                if item.base64:
                    entry["base64"] = item.base64
                if entry:
                    image_list.append(entry)
                if not image_url and item.url:
                    image_url = item.url
                if not image_url and item.ossUrl:
                    image_url = item.ossUrl
                if not image_base64 and item.base64:
                    image_base64 = item.base64
        return _ImageBundle(image_url=image_url, image_base64=image_base64, image_list=image_list)

    def _extract_input_payload(self, merged_inputs: dict[str, Any]) -> dict[str, Any] | None:
        candidate = merged_inputs.pop("input", None)
        if isinstance(candidate, dict):
            return candidate
        return None

    def _build_coze_ext(self, ability: Ability, context: _InvocationContext) -> dict[str, str]:
        ext: dict[str, str] = {
            "ability_id": ability.id,
            "capability_key": ability.capability_key,
            "provider": ability.provider,
            "request_id": context.request_id,
            "source": context.source,
        }
        if context.user:
            ext["user_id"] = str(context.user.id)
        metadata = context.payload.metadata
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if value is None:
                    continue
                ext[f"meta_{key}"] = self._stringify_value(value)
        return ext

    def _stringify_value(self, value: Any) -> str:
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)

    def _parse_coze_payload(self, payload: Any) -> Any:
        if payload is None:
            return None
        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                return stripped
        return payload

    def _extract_coze_text(self, payload: Any) -> str | None:
        if payload is None:
            return None
        if isinstance(payload, str):
            stripped = payload.strip()
            return stripped or None
        if isinstance(payload, dict):
            for key in ("text", "data", "content", "message", "output"):
                if key in payload:
                    text = self._extract_coze_text(payload[key])
                    if text:
                        return text
            outputs = payload.get("outputs")
            if isinstance(outputs, list):
                for item in outputs:
                    text = self._extract_coze_text(item)
                    if text:
                        return text
        if isinstance(payload, list):
            for item in payload:
                text = self._extract_coze_text(item)
                if text:
                    return text
        return None

    def _extract_coze_result_urls(self, payload: Any) -> list[str]:
        urls: list[str] = []

        def add_url(entry: Any) -> None:
            if isinstance(entry, str):
                urls.append(entry)
            elif isinstance(entry, dict):
                for key in ("url", "ossUrl", "sourceUrl"):
                    candidate = entry.get(key)
                    if isinstance(candidate, str):
                        urls.append(candidate)
                        break

        def traverse(value: Any) -> None:
            if isinstance(value, dict):
                for key in ("resultUrls", "result_urls", "imageUrls", "images", "urls"):
                    target = value.get(key)
                    if isinstance(target, list):
                        for entry in target:
                            add_url(entry)
                    elif isinstance(target, str):
                        urls.append(target)
                outputs = value.get("outputs")
                if isinstance(outputs, list):
                    for item in outputs:
                        traverse(item)
            elif isinstance(value, list):
                for item in value:
                    traverse(item)

        traverse(payload)
        return self._deduplicate_urls(urls)

    # -------- response helpers -------- #
    def _build_response_payload(
        self,
        ability: Ability,
        request_id: str,
        provider_result: dict[str, Any],
        log_id: int | None,
        *,
        duration_ms: int | None = None,
    ) -> schemas.AbilityInvokeResponse:
        provider = provider_result.get("provider", ability.provider)
        images = self._extract_output_assets(provider_result, target="image")
        videos = self._extract_output_assets(provider_result, target="video")
        texts = self._extract_texts(provider_result)
        generic_assets = self._extract_generic_assets(provider_result)
        metadata = {
            "model": provider_result.get("model"),
            "state": provider_result.get("state"),
            "taskId": provider_result.get("taskId"),
        }
        raw_payload = provider_result.get("raw")
        return schemas.AbilityInvokeResponse(
            abilityId=ability.id,
            provider=provider,
            status="succeeded",
            requestId=request_id,
            logId=log_id,
            durationMs=duration_ms,
            images=images or None,
            videos=videos or None,
            texts=texts or None,
            assets=generic_assets or None,
            metadata=self._clean_params(metadata) or None,
            raw=raw_payload if isinstance(raw_payload, dict) else None,
        )

    def _extract_output_assets(self, payload: dict[str, Any], target: str) -> list[schemas.AbilityOutputAsset]:
        assets: list[schemas.AbilityOutputAsset] = []
        if target == "image":
            stored_url = payload.get("storedUrl")
            image_url = payload.get("imageUrl")
            image_base64 = payload.get("imageBase64") or payload.get("resultImage")
            result_urls = payload.get("resultUrls")
            if stored_url or image_url or image_base64:
                assets.append(
                    schemas.AbilityOutputAsset(
                        ossUrl=stored_url,
                        sourceUrl=image_url,
                        base64=image_base64,
                        type="image",
                    )
                )
            if isinstance(result_urls, list):
                for url in result_urls:
                    if isinstance(url, str):
                        assets.append(schemas.AbilityOutputAsset(sourceUrl=url, type="image"))
            # Providers like ComfyUI return a generic `assets` list; surface image assets in `images`
            # so Coze (and our UI) can display them without custom parsing.
            if not assets:
                generic_assets = payload.get("assets") or payload.get("storedAssets")
                if isinstance(generic_assets, list):
                    for item in generic_assets:
                        if not isinstance(item, dict):
                            continue
                        content_type = (item.get("contentType") or item.get("mimeType") or "").lower()
                        if content_type.startswith("image/") or item.get("tag") in {"comfyui", "comfyui-input"}:
                            assets.append(
                                schemas.AbilityOutputAsset(
                                    ossUrl=item.get("ossUrl") or item.get("url"),
                                    sourceUrl=item.get("sourceUrl"),
                                    type="image",
                                    tag=item.get("tag"),
                                )
                            )
        elif target == "video":
            video_urls = payload.get("videoUrls") or payload.get("videos")
            if isinstance(video_urls, list):
                for url in video_urls:
                    if isinstance(url, str):
                        assets.append(schemas.AbilityOutputAsset(sourceUrl=url, type="video"))
            if not assets:
                generic_assets = payload.get("assets") or payload.get("storedAssets")
                if isinstance(generic_assets, list):
                    for item in generic_assets:
                        if not isinstance(item, dict):
                            continue
                        content_type = (item.get("contentType") or item.get("mimeType") or "").lower()
                        if content_type.startswith("video/") or item.get("tag") in {"video", "comfyui-video"}:
                            assets.append(
                                schemas.AbilityOutputAsset(
                                    ossUrl=item.get("ossUrl") or item.get("url"),
                                    sourceUrl=item.get("sourceUrl"),
                                    type="video",
                                    tag=item.get("tag"),
                                )
                            )
        return assets

    def _extract_generic_assets(self, payload: dict[str, Any]) -> list[schemas.AbilityOutputAsset]:
        entries = []
        assets = payload.get("assets") or payload.get("storedAssets")
        if isinstance(assets, list):
            for item in assets:
                if not isinstance(item, dict):
                    continue
                entries.append(
                    schemas.AbilityOutputAsset(
                        ossUrl=item.get("ossUrl") or item.get("url"),
                        sourceUrl=item.get("sourceUrl"),
                        type=item.get("contentType"),
                        tag=item.get("tag"),
                    )
                )
        return entries

    def _extract_texts(self, payload: dict[str, Any]) -> list[str]:
        texts: list[str] = []
        if isinstance(payload.get("text"), str):
            texts.append(payload["text"])
        if isinstance(payload.get("texts"), list):
            texts.extend([str(item) for item in payload["texts"] if isinstance(item, (str, int, float))])
        return texts

    def _urls_from_image_bundle(self, bundle: _ImageBundle) -> list[str]:
        urls = []
        if bundle.image_url:
            urls.append(bundle.image_url)
        urls.extend(self._extract_urls_from_value(bundle.image_list))
        return urls

    # -------- misc utilities -------- #
    def _get_ability(self, ability_id: str) -> Ability:
        with get_session() as session:
            ability = session.get(Ability, ability_id)
            if not ability:
                raise HTTPException(status_code=404, detail="ABILITY_NOT_FOUND")
            return ability

    def _to_public_info(self, ability: Ability) -> schemas.AbilityPublicInfo:
        metadata = ability.extra_metadata or {}
        max_output = metadata.get("max_output_images")
        supports_multi = bool(metadata.get("supports_multiple_outputs")) or (
            isinstance(max_output, int) and max_output > 1
        )
        requires_image = bool(metadata.get("requires_image_input"))
        return schemas.AbilityPublicInfo(
            id=ability.id,
            provider=ability.provider,
            category=ability.category,
            capabilityKey=ability.capability_key,
            displayName=ability.display_name,
            description=ability.description,
            status=ability.status,
            abilityType=ability.ability_type,
            workflowId=ability.workflow_id,
            cozeWorkflowId=ability.coze_workflow_id,
            executorId=ability.executor_id,
            defaultParams=ability.default_params,
            inputSchema=ability.input_schema,
            metadata=metadata or None,
            requiresImage=requires_image,
            supportsMultipleImages=supports_multi,
            maxOutputImages=max_output if isinstance(max_output, int) else None,
            lastHealthCheckAt=ability.last_health_check_at,
            lastHealthStatus=ability.last_health_status,
            successRate=ability.success_rate,
        )

    @staticmethod
    def _clean_params(payload: dict[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}
        return {key: value for key, value in payload.items() if value not in (None, "", [])}

    @staticmethod
    def _exclude_keys(source: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
        keys = set(keys)
        return {key: value for key, value in source.items() if key not in keys}

    @staticmethod
    def _pop_first_string(payload: dict[str, Any], keys: Iterable[str]) -> str | None:
        for key in keys:
            value = payload.pop(key, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
            # Coze inputs are typically strings; internal coercion may have already
            # converted some fields (e.g., number/switch) to scalars.
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
        return None

    @staticmethod
    def _omit_large_fields(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}
        for key, value in payload.items():
            if key.lower() in {"imagebase64", "image_base64"} and isinstance(value, str):
                sanitized[key] = "[omitted]"
            else:
                sanitized[key] = value
        return sanitized

    @staticmethod
    def _deduplicate_urls(urls: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for url in urls:
            normalized = url.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
        return unique

    @staticmethod
    def _extract_urls_from_value(value: Any) -> list[str]:
        if value is None:
            return []
        urls: list[str] = []
        if isinstance(value, str):
            normalized = value.replace(",", "\n")
            urls.extend([line.strip() for line in normalized.splitlines() if line.strip()])
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                urls.extend(AbilityInvocationService._extract_urls_from_value(item))
        elif isinstance(value, dict):
            for key in ("url", "ossUrl", "oss_url"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    urls.append(candidate.strip())
                    break
        return urls

    def _pop_url_list(self, payload: dict[str, Any], keys: Iterable[str]) -> list[str]:
        urls: list[str] = []
        for key in keys:
            value = payload.pop(key, None)
            urls.extend(self._extract_urls_from_value(value))
        return self._deduplicate_urls(urls)

    @staticmethod
    def _extract_pricing_metadata(ability: Ability) -> tuple[str | None, str | None, float | None]:
        metadata = ability.extra_metadata or {}
        pricing = metadata.get("pricing") if isinstance(metadata, dict) else None
        if isinstance(pricing, dict):
            currency = pricing.get("currency")
            unit = pricing.get("unit")
            value = pricing.get("discount_price") or pricing.get("list_price")
            try:
                unit_price = float(value) if value is not None else None
            except (TypeError, ValueError):
                unit_price = None
            return currency, unit, unit_price
        return None, None, None

    @staticmethod
    def _extract_error_message(exc: Exception) -> str:
        if isinstance(exc, HTTPException):
            detail = exc.detail
            if isinstance(detail, str):
                return detail
            return str(detail)
        return str(exc)

    @staticmethod
    def _extract_error_payload(exc: Exception) -> dict[str, Any] | None:
        if isinstance(exc, HTTPException):
            return {"status_code": exc.status_code, "detail": exc.detail}
        return None

    def _schedule_callback(
        self,
        *,
        callback_url: str,
        callback_headers: dict[str, str] | None,
        ability: Ability,
        request_id: str,
        log_id: int | None,
        duration_ms: int | None,
        status: str,
        result_payload: dict[str, Any] | None,
        error_payload: dict[str, Any] | None,
    ) -> None:
        if not callback_url:
            return
        payload = {
            "status": status,
            "abilityId": ability.id,
            "provider": ability.provider,
            "requestId": request_id,
            "logId": log_id,
            "durationMs": duration_ms,
            "result": result_payload,
            "error": error_payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        thread = threading.Thread(
            target=self._post_callback,
            args=(callback_url, callback_headers or {}, payload),
            daemon=True,
        )
        thread.start()

    def _post_callback(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> None:
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - best effort webhook
            self._logger.warning("Callback POST to %s failed: %s", url, exc)


ability_invocation_service = AbilityInvocationService()
