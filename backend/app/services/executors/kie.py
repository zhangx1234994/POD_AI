"""KIE market executor adapter for the generic task dispatcher."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .base import ExecutionContext, ExecutionResult, ExecutorAdapter


class KieMarketExecutorAdapter(ExecutorAdapter):
    """Submit KIE market tasks through the same helper used by admin tests.

    The old dispatcher path works with Task/Workflow/Executor records instead of
    Ability records. This adapter keeps that path functional without duplicating
    KIE submit/poll/key-rotation logic.
    """

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        definition = context.workflow.definition if isinstance(context.workflow.definition, dict) else {}
        payload = context.payload if isinstance(context.payload, dict) else {}
        model = self._pick_string(payload, definition, "model", "providerModel", "provider_model")
        if not model:
            return ExecutionResult(success=False, status="failed", error_message="KIE_MODEL_REQUIRED")

        endpoint = self._pick_string(payload, definition, "endpoint", "requestEndpoint", "request_endpoint")
        input_array_target = self._pick_string(
            payload,
            definition,
            "input_array_target",
            "inputArrayTarget",
            "imageArrayTarget",
            "image_array_target",
        )
        call_back_url = self._pick_string(payload, definition, "callBackUrl", "callbackUrl", "callback_url")
        extra_payload = self._pick_dict(payload, definition, "extra_payload", "extraPayload")
        desired_output_size = self._pick_desired_output_size(payload, definition)
        poll_timeout = self._pick_float(payload, definition, "poll_timeout", "pollTimeout", default=120.0)
        poll_interval = self._pick_float(payload, definition, "poll_interval", "pollInterval", default=2.5)

        input_payload = self._build_input_payload(payload, definition)
        try:
            from app.services.integration_test import integration_test_service

            result = integration_test_service.run_kie_market_task(
                executor_id=context.executor.id,
                endpoint=endpoint,
                model=model,
                input_payload=input_payload,
                input_array_target=input_array_target,
                desired_output_size=desired_output_size,
                call_back_url=call_back_url,
                extra_payload=extra_payload,
                poll_timeout=poll_timeout,
                poll_interval=poll_interval,
            )
        except HTTPException as exc:
            return ExecutionResult(success=False, status="failed", error_message=str(exc.detail or "KIE_EXECUTION_FAILED"))

        status = str(result.get("status") or "").lower()
        if status == "failed":
            return ExecutionResult(
                success=False,
                status="failed",
                progress=100,
                result_payload=dict(result),
                error_message=self._extract_error_message(result),
            )
        if status in {"queued", "running"}:
            return ExecutionResult(success=True, status=status, progress=0, result_payload=dict(result))
        return ExecutionResult(success=True, status="completed", progress=100, result_payload=dict(result))

    def _build_input_payload(self, payload: dict[str, Any], definition: dict[str, Any]) -> dict[str, object]:
        defaults = self._pick_dict({}, definition, "defaults", "inputDefaults", "input_defaults") or {}
        explicit_input = self._pick_dict(payload, definition, "input", "input_payload", "inputPayload") or {}
        merged: dict[str, object] = {}
        merged.update(defaults)
        merged.update(explicit_input)
        reserved = {
            "model",
            "providerModel",
            "provider_model",
            "endpoint",
            "requestEndpoint",
            "request_endpoint",
            "input",
            "input_payload",
            "inputPayload",
            "input_array_target",
            "inputArrayTarget",
            "image_array_target",
            "imageArrayTarget",
            "callBackUrl",
            "callbackUrl",
            "callback_url",
            "extra_payload",
            "extraPayload",
            "poll_timeout",
            "pollTimeout",
            "poll_interval",
            "pollInterval",
            "desired_output_size",
            "desiredOutputSize",
            "desired_width",
            "desiredWidth",
            "desired_height",
            "desiredHeight",
        }
        for key, value in payload.items():
            if key in reserved:
                continue
            merged[key] = value
        return merged

    @staticmethod
    def _pick_string(payload: dict[str, Any], definition: dict[str, Any], *keys: str) -> str | None:
        for source in (payload, definition):
            for key in keys:
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _pick_dict(payload: dict[str, Any], definition: dict[str, Any], *keys: str) -> dict[str, object] | None:
        for source in (payload, definition):
            for key in keys:
                value = source.get(key)
                if isinstance(value, dict):
                    return dict(value)
        return None

    @staticmethod
    def _pick_float(payload: dict[str, Any], definition: dict[str, Any], *keys: str, default: float) -> float:
        for source in (payload, definition):
            for key in keys:
                value = source.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return default

    @staticmethod
    def _pick_desired_output_size(
        payload: dict[str, Any],
        definition: dict[str, Any],
    ) -> tuple[int, int] | None:
        for source in (payload, definition):
            value = source.get("desired_output_size") or source.get("desiredOutputSize")
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                try:
                    width = int(value[0])
                    height = int(value[1])
                    if width > 0 and height > 0:
                        return width, height
                except (TypeError, ValueError):
                    pass
            width = source.get("desired_width") or source.get("desiredWidth")
            height = source.get("desired_height") or source.get("desiredHeight")
            try:
                width_int = int(width)
                height_int = int(height)
                if width_int > 0 and height_int > 0:
                    return width_int, height_int
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _extract_error_message(result: dict[str, Any]) -> str:
        raw = result.get("raw")
        if isinstance(raw, dict):
            response = raw.get("response")
            if isinstance(response, dict):
                msg = response.get("msg") or response.get("message") or response.get("detail")
                if msg:
                    return str(msg)
        return "KIE_TASK_FAILED"
