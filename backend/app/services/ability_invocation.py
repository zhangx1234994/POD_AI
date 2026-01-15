"""Runtime ability catalogue + invocation service."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

import httpx

from app.core.db import get_session
from app.models.integration import Ability
from app.models.user import User
from app.schemas import abilities as schemas
from app.services.ability_logs import AbilityLogStartParams, ability_log_service
from app.services.ability_seed import ensure_default_abilities
from app.services.integration_test import integration_test_service


@dataclass
class _ImageBundle:
    image_url: str | None
    image_base64: str | None
    image_list: list[dict[str, Any]]


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
    ) -> schemas.AbilityInvokeResponse:
        ability = self._get_ability(ability_id)
        if ability.status != "active":
            raise HTTPException(status_code=400, detail="ABILITY_INACTIVE")
        executor_id = payload.executorId or ability.executor_id
        if not executor_id:
            raise HTTPException(status_code=400, detail="ABILITY_EXECUTOR_NOT_CONFIGURED")
        merged_inputs = self._merge_inputs(ability, payload)
        image_bundle = self._normalize_image_inputs(payload, merged_inputs)
        request_marker = uuid4().hex
        currency, billing_unit, unit_price = self._extract_pricing_metadata(ability)
        request_payload = {
            "inputs": merged_inputs,
            "imageUrl": image_bundle.image_url,
            "hasImageBase64": bool(image_bundle.image_base64),
            "imageListCount": len(image_bundle.image_list),
            "metadata": payload.metadata,
            "userId": user.id if user else None,
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
        try:
            provider_result = self._dispatch_provider(
                ability=ability,
                executor_id=executor_id,
                merged_inputs=merged_inputs,
                images=image_bundle,
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

    # -------- internal helpers -------- #
    def _dispatch_provider(
        self,
        *,
        ability: Ability,
        executor_id: str,
        merged_inputs: dict[str, Any],
        images: _ImageBundle,
    ) -> dict[str, Any]:
        provider = ability.provider.lower()
        if provider == "baidu":
            return self._invoke_baidu(ability, executor_id, merged_inputs, images)
        if provider == "volcengine":
            return self._invoke_volcengine(ability, executor_id, merged_inputs, images)
        if provider == "comfyui":
            return self._invoke_comfyui(ability, executor_id, merged_inputs, images)
        if provider == "kie":
            return self._invoke_kie(ability, executor_id, merged_inputs, images)
        raise HTTPException(status_code=400, detail=f"ABILITY_PROVIDER_UNSUPPORTED:{provider}")

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
        if array_target and images.image_list:
            input_payload[array_target] = images.image_list
        elif array_target and images.image_url:
            input_payload[array_target] = [{"url": images.image_url}]
        extra_payload = None
        if isinstance(merged_inputs.get("extra"), dict):
            extra_payload = merged_inputs.pop("extra")
        endpoint = metadata.get("request_endpoint")
        return integration_test_service.run_kie_market_task(
            executor_id=executor_id,
            endpoint=endpoint,
            model=model,
            input_payload=input_payload,
            call_back_url=self._pop_first_string(merged_inputs, ["callBackUrl", "callback_url"]),
            extra_payload=self._clean_params(extra_payload or merged_inputs) or None,
        )

    # -------- parsing helpers -------- #
    def _merge_inputs(self, ability: Ability, payload: schemas.AbilityInvokeRequest) -> dict[str, Any]:
        merged = dict(ability.default_params or {})
        if payload.inputs:
            merged.update(payload.inputs)
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
        elif target == "video":
            video_urls = payload.get("videoUrls") or payload.get("videos")
            if isinstance(video_urls, list):
                for url in video_urls:
                    if isinstance(url, str):
                        assets.append(schemas.AbilityOutputAsset(sourceUrl=url, type="video"))
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
