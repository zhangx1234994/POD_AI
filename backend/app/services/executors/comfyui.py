"""ComfyUI executor adapter."""

from __future__ import annotations

import re
import base64
import json
import logging
import math
import mimetypes
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse, urlencode
from uuid import uuid4

import httpx
from PIL import Image
from io import BytesIO

from app.services.executors.base import ExecutionContext, ExecutionResult, ExecutorAdapter
from app.services.comfyui_graph import normalize_comfyui_prompt_graph
from app.services.media_ingest import media_ingest_service


# Fallback LoRA name when ComfyUI rejects a lora_name (value_not_in_list).
# IMPORTANT: This must exist on every ComfyUI executor you route to, otherwise the
# fallback will still fail. Keep it consistent with your ops sync policy.
FALLBACK_LORA_NAME = "杯子1124.safetensors"
TEXT2IMG_TEXT_ALLOWED_NEGATIVE_DEFAULT = (
    "blurry, low quality, broken composition, watermark, mockup, photo of a shirt, "
    "dirty grunge, muddy colors, extra instruction words, unrelated objects"
)

FISSION_V4_ROUTE_MAP: dict[str, dict[str, Any]] = {
    "small_scatter_high_density": {"low": 0.50, "mid": 0.52, "high": 0.52, "experimental": 0.52},
    "medium_floral_textile": {"low": 0.50, "mid": 0.58, "high": 0.58, "experimental": 0.58},
    "clean_vector_cartoon_repeat": {"low": 0.50, "mid": 0.58, "high": 0.65, "experimental": 0.65},
    "separable_cartoon_icon_repeat": {"low": 0.50, "mid": 0.60, "high": 0.68, "experimental": 0.72},
    "large_single_motif": {"low": 0.50, "mid": 0.58, "high": 0.65, "experimental": 0.65},
    "unknown_or_uncertain": {"low": 0.50, "mid": 0.52, "high": 0.52, "experimental": 0.52},
}

FISSION_V4_DEFAULT_PROFILE = "pattern_risk_routed_v4"
FISSION_V4_DEFAULT_REFERENCE_LOCK = 0.42
FISSION_V4_DEFAULT_COLOR_LOCK = 0.90


def _detect_lora_name_validation_nodes(payload: Any) -> set[str] | None:
    """Return node ids that failed lora_name validation, or None if not applicable."""
    if payload is None:
        return None

    data: dict[str, Any] | None = None
    if isinstance(payload, httpx.Response):
        try:
            parsed = payload.json()
        except Exception:
            return None
        if isinstance(parsed, dict):
            data = parsed
    elif isinstance(payload, dict):
        data = payload
    if not isinstance(data, dict):
        return None

    err = data.get("error")
    if isinstance(err, dict):
        # ComfyUI uses this when outputs can't be validated (e.g. missing model/LoRA).
        if str(err.get("type") or "") != "prompt_outputs_failed_validation":
            return None

    node_errors = data.get("node_errors")
    if not isinstance(node_errors, dict) or not node_errors:
        return None

    nodes: set[str] = set()
    for node_id, info in node_errors.items():
        if not isinstance(info, dict):
            continue
        errors = info.get("errors")
        if not isinstance(errors, list):
            continue
        for e in errors:
            if not isinstance(e, dict):
                continue
            if str(e.get("type") or "") != "value_not_in_list":
                continue
            extra = e.get("extra_info")
            if not isinstance(extra, dict):
                continue
            if str(extra.get("input_name") or "") == "lora_name":
                nodes.add(str(node_id))
                break

    return nodes or None


def _apply_fallback_lora_name(graph: dict[str, Any], *, node_ids: set[str] | None, fallback: str) -> int:
    """Update lora_name in the graph and return number of nodes updated."""
    updated = 0
    for node_id, node in graph.items():
        if node_ids is not None and str(node_id) not in node_ids:
            continue
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        if "lora_name" not in inputs:
            continue
        if inputs.get("lora_name") == fallback:
            continue
        inputs["lora_name"] = fallback
        updated += 1
    return updated


class ComfyUIExecutorAdapter(ExecutorAdapter):
    """Submit prompt JSON to ComfyUI /prompt endpoint, poll history, download outputs."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        config = context.executor.config or {}
        base_url = (context.executor.base_url or config.get("baseUrl") or config.get("base_url") or "").rstrip("/")
        if not base_url:
            return ExecutionResult(
                success=False,
                status="failed",
                error_message="COMFYUI_BASE_URL_MISSING",
            )

        workflow_definition = context.workflow.definition or {}
        graph_payload = normalize_comfyui_prompt_graph(workflow_definition) or workflow_definition.get("graph") or workflow_definition
        if not graph_payload:
            return ExecutionResult(
                success=False,
                status="failed",
                error_message="COMFYUI_WORKFLOW_EMPTY",
            )
        overrides, override_error = self._prepare_graph_inputs(context, workflow_definition)
        if override_error:
            return ExecutionResult(
                success=False,
                status="failed",
                error_message=override_error,
            )
        if overrides:
            _apply_inputs(graph_payload, overrides)
        self._normalize_string_nodes(graph_payload)
        workflow_meta = getattr(context.workflow, "extra_metadata", None) or {}

        # Avoid "same inputs => same outputs" surprises when users run the same workflow
        # repeatedly (e.g. "抽卡"). Many shared ComfyUI graphs ship with a fixed seed.
        # Unless the caller explicitly provides a seed, randomize all KSampler seeds.
        self._ensure_sampler_seed(graph_payload, context.payload or {})

        def _submit(prompt_id: str) -> tuple[dict[str, Any] | None, str | None]:
            """Return (json, error_message)."""
            submission = {"prompt": graph_payload, "prompt_id": prompt_id}
            try:
                resp = httpx.post(f"{base_url}/prompt", json=submission, timeout=30)
                resp.raise_for_status()
                payload = resp.json() if resp.content else None
            except httpx.HTTPError as exc:  # pragma: no cover - defensive
                extra_details = ""
                node_ids = None
                if isinstance(exc, httpx.HTTPStatusError):
                    resp = exc.response
                    resp_text = resp.text[:1000] if resp is not None else ""
                    extra_details = f" | status={resp.status_code if resp else 'unknown'} body={resp_text!r}"
                    # If ComfyUI rejects a LoRA name (not in list), try a safe fallback once.
                    node_ids = _detect_lora_name_validation_nodes(resp) if resp is not None else None
                if node_ids:
                    updated = _apply_fallback_lora_name(graph_payload, node_ids=node_ids, fallback=FALLBACK_LORA_NAME)
                    if updated:
                        self._logger.warning(
                            "ComfyUI rejected lora_name; falling back to %r on %d node(s). prompt_id=%s",
                            FALLBACK_LORA_NAME,
                            updated,
                            prompt_id,
                        )
                        return None, "RETRY_FALLBACK_LORA"
                self._logger.warning("Failed to submit ComfyUI prompt: %s%s", exc, extra_details)
                return None, f"COMFYUI_SUBMIT_ERROR{extra_details}"

            # ComfyUI can still return node_errors in a 200 response; treat as failure.
            node_errors = payload.get("node_errors") if isinstance(payload, dict) else None
            if isinstance(node_errors, dict) and node_errors:
                node_ids = _detect_lora_name_validation_nodes(payload)  # type: ignore[arg-type]
                if node_ids:
                    updated = _apply_fallback_lora_name(graph_payload, node_ids=node_ids, fallback=FALLBACK_LORA_NAME)
                    if updated:
                        self._logger.warning(
                            "ComfyUI returned node_errors for lora_name; falling back to %r on %d node(s). prompt_id=%s",
                            FALLBACK_LORA_NAME,
                            updated,
                            prompt_id,
                        )
                        return None, "RETRY_FALLBACK_LORA"
                return None, f"COMFYUI_SUBMIT_NODE_ERROR:{list(node_errors.keys())[:5]}"

            return payload, None

        prompt_id = uuid4().hex
        resp_json, err = _submit(prompt_id)
        if err == "RETRY_FALLBACK_LORA":
            prompt_id = uuid4().hex
            resp_json, err = _submit(prompt_id)
            if err:
                return ExecutionResult(success=False, status="failed", error_message=str(err))
        elif err:
            return ExecutionResult(success=False, status="failed", error_message=str(err))

        expected_images = None
        try:
            expected_images = int(workflow_definition.get("_expected_image_count") or 0) or None
        except (TypeError, ValueError):
            expected_images = None

        output_node_ids = None
        raw_ids = workflow_definition.get("output_node_ids")
        if not isinstance(raw_ids, list):
            workflow_meta = getattr(context.workflow, "extra_metadata", None) or {}
            raw_ids = workflow_meta.get("output_node_ids") or workflow_meta.get("outputNodeIds")
        if isinstance(raw_ids, list):
            output_node_ids = {str(x) for x in raw_ids if str(x).strip()}

        outputs = self._poll_history(
            base_url,
            prompt_id,
            timeout=workflow_definition.get("timeout", 180),
            expected_images=expected_images,
            output_node_ids=output_node_ids,
        )
        pending_payload_base: dict[str, Any] = {
            "executor": context.executor.id,
            "promptId": prompt_id,
            "assets": [],
            "submit": resp_json,
            "baseUrl": base_url,
        }
        if output_node_ids:
            pending_payload_base["outputNodeIds"] = sorted(output_node_ids)
        if outputs is None:
            # Prompt was already accepted by ComfyUI, but history is still unavailable.
            # Keep task running so the background finalizer can continue polling.
            pending_payload = dict(pending_payload_base)
            pending_payload["status"] = "running"
            pending_payload["state"] = "running"
            return ExecutionResult(
                success=True,
                status="running",
                progress=0,
                result_payload=pending_payload,
            )
        if outputs.get("timed_out"):
            state = str(outputs.get("state") or "").lower()
            if state == "error":
                return ExecutionResult(
                    success=False,
                    status="failed",
                    error_message="COMFYUI_ERROR",
                )
            if state in {"queued", "running", ""}:
                status = state if state in {"queued", "running"} else "running"
                pending_payload = dict(pending_payload_base)
                pending_payload["status"] = status
                pending_payload["state"] = state or status
                pending_payload["raw"] = outputs
                return ExecutionResult(
                    success=True,
                    status=status,
                    progress=0,
                    result_payload=pending_payload,
                )
            pending_payload = dict(pending_payload_base)
            pending_payload["status"] = "running"
            pending_payload["state"] = state or "running"
            pending_payload["raw"] = outputs
            return ExecutionResult(
                success=True,
                status="running",
                progress=0,
                result_payload=pending_payload,
            )

        state_now = str(outputs.get("state") or "").lower()
        if state_now in {"error", "failed"}:
            return ExecutionResult(
                success=False,
                status="failed",
                error_message="COMFYUI_ERROR",
            )

        history_images = outputs.get("images") if isinstance(outputs.get("images"), list) else []
        max_output_images = self._coerce_positive_int(workflow_definition.get("_max_output_images"))
        if max_output_images:
            history_images = history_images[:max_output_images]
        if not history_images:
            pending_payload = dict(pending_payload_base)
            pending_payload["status"] = "running"
            pending_payload["state"] = state_now or "running"
            pending_payload["raw"] = outputs
            return ExecutionResult(
                success=True,
                status="running",
                progress=0,
                result_payload=pending_payload,
            )

        assets = []
        for image in history_images:
            source_url = image.get("url") or self._build_image_url(base_url, image)
            base64_data = image.get("base64")
            if source_url:
                asset = self._store_remote_asset(source_url, context, tag="comfyui")
            elif base64_data:
                asset = self._store_base64_asset(base64_data, context, tag="comfyui")
            else:
                continue
            if asset:
                assets.append(asset)
        if not assets:
            pending_payload = dict(pending_payload_base)
            pending_payload["status"] = "running"
            pending_payload["state"] = state_now or "running"
            pending_payload["raw"] = outputs
            return ExecutionResult(
                success=True,
                status="running",
                progress=0,
                result_payload=pending_payload,
            )

        return ExecutionResult(
            success=True,
            status="completed",
            progress=100,
            result_payload={
                "executor": context.executor.id,
                "promptId": prompt_id,
                "assets": assets,
                "raw": outputs,
                "submit": resp_json,
            },
        )

    def _ensure_sampler_seed(self, graph: dict[str, Any], params: dict[str, Any]) -> None:
        def _coerce_int(v: Any) -> int | None:
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        provided = (
            params.get("seed")
            or params.get("random_seed")
            or params.get("randomSeed")
            or params.get("sampler_seed")
            or params.get("samplerSeed")
        )
        seed = _coerce_int(provided)
        if seed is None:
            # Use a large positive int; ComfyUI typically supports 64-bit seeds.
            seed = secrets.randbits(48)

        for node in graph.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            class_type = str(node.get("class_type") or "")
            if class_type == "KSampler" and "seed" in inputs:
                inputs["seed"] = seed
            elif class_type == "RandomNoise" and "noise_seed" in inputs:
                inputs["noise_seed"] = seed

    @staticmethod
    def _normalize_comfy_dim(value: int | None, *, multiple: int = 8) -> int | None:
        """ComfyUI/latent pipelines typically require dimensions to be multiples of 8.

        If callers pass arbitrary px sizes, ComfyUI will silently round; we normalize
        on our side so the output size matches what we ask for.
        """
        if not value or value <= 0:
            return None
        multiple = max(1, int(multiple))
        return max(multiple, int(value) - (int(value) % multiple))

    def _poll_history(
        self,
        base_url: str,
        prompt_id: str,
        timeout: float,
        *,
        expected_images: int | None,
        output_node_ids: set[str] | None = None,
    ) -> dict[str, Any] | None:
        start = time.monotonic()
        last_data: dict[str, Any] | None = None
        last_status_str: str | None = None
        timed_out = False
        # Some ComfyUI builds create the history entry before all batch images are persisted.
        # We wait for a terminal status (preferred) or for outputs to "stabilize" for a few polls.
        stable_polls = 0
        last_image_count: int | None = None
        fallback_to_all = False
        while time.monotonic() - start < timeout:
            try:
                resp = httpx.get(f"{base_url}/history/{prompt_id}", timeout=15)
                if resp.status_code == 404:
                    time.sleep(1)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                time.sleep(1)
                continue
            last_data = data
            entry = data.get(prompt_id) if isinstance(data, dict) else None
            if not isinstance(entry, dict):
                time.sleep(1)
                continue

            status = entry.get("status")
            outputs = entry.get("outputs") or {}
            image_count = 0
            total_image_count = 0
            if isinstance(outputs, dict):
                for node_id, info in outputs.items():
                    if not isinstance(info, dict):
                        continue
                    imgs = info.get("images")
                    if isinstance(imgs, list):
                        total_image_count += len(imgs)
                    if output_node_ids and str(node_id) not in output_node_ids:
                        continue
                    if isinstance(imgs, list):
                        image_count += len(imgs)
            if output_node_ids and image_count == 0 and total_image_count > 0:
                image_count = total_image_count
                fallback_to_all = True

            if last_image_count is not None and image_count == last_image_count and image_count > 0:
                stable_polls += 1
            else:
                stable_polls = 0
            last_image_count = image_count

            # If we know how many images we expect (batch), wait until we have them.
            # Still keep a fallback to avoid hanging forever if the workflow produces fewer images.
            if expected_images and image_count >= expected_images:
                break

            if isinstance(status, dict):
                status_str = str(status.get("status_str") or "").lower()
                if status_str:
                    last_status_str = status_str
                # "error" is terminal.
                if status_str == "error":
                    break
                # "success" can arrive before all batch images are present in `outputs`.
                # If we know how many images we expect, keep polling until we have them
                # or until we're close to timing out (to avoid hanging forever).
                if status_str == "success":
                    if not expected_images:
                        break
                    elapsed = time.monotonic() - start
                    remaining = timeout - elapsed
                    if remaining <= 5 and image_count > 0:
                        break

            # Fallback: if no status info, consider done once output image count stabilizes.
            if not expected_images and stable_polls >= 2:
                break
            time.sleep(1)
        if time.monotonic() - start >= timeout:
            timed_out = True

        if not last_data:
            return None

        # Most ComfyUI versions return: { "<prompt_id>": { ...entry... } }
        # But be defensive in case a reverse proxy / fork returns the entry directly.
        if prompt_id in last_data and isinstance(last_data.get(prompt_id), dict):
            entry = last_data[prompt_id]
        elif isinstance(last_data.get("outputs"), dict):
            entry = last_data
        else:
            return None
        outputs = entry.get("outputs") or {}
        images: list[dict[str, Any]] = []
        for node_id, info in outputs.items():
            if not isinstance(info, dict):
                continue
            if output_node_ids and str(node_id) not in output_node_ids:
                continue
            for node_image in info.get("images", []):
                filename = node_image.get("filename")
                subfolder = node_image.get("subfolder") or ""
                image_url = node_image.get("url")
                image_type = node_image.get("type") or node_image.get("image_type")
                images.append(
                    {
                        "nodeId": str(node_id),
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": image_type,
                        "url": image_url or "",
                        "base64": node_image.get("base64"),
                        "mime": node_image.get("mime_type"),
                    }
                )
        if output_node_ids and not images and fallback_to_all and isinstance(outputs, dict):
            for node_id, info in outputs.items():
                if not isinstance(info, dict):
                    continue
                for node_image in info.get("images", []):
                    filename = node_image.get("filename")
                    subfolder = node_image.get("subfolder") or ""
                    image_url = node_image.get("url")
                    image_type = node_image.get("type") or node_image.get("image_type")
                    images.append(
                        {
                            "nodeId": str(node_id),
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": image_type,
                            "url": image_url or "",
                            "base64": node_image.get("base64"),
                            "mime": node_image.get("mime_type"),
                        }
                    )
        return {"images": images, "history": entry, "timed_out": timed_out, "state": last_status_str}

    def _extract_outputs(self, entry: dict[str, Any], *, output_node_ids: set[str] | None = None) -> dict[str, Any]:
        """Extract images from a ComfyUI history entry.

        NOTE: Some call-sites (eval + coze tasks/get) fetch `/history/{promptId}` themselves
        and only need a consistent extractor. Keep this in sync with `_poll_history`.
        """
        outputs = entry.get("outputs") or {}
        images: list[dict[str, Any]] = []
        total_image_count = 0
        if isinstance(outputs, dict):
            for node_id, info in outputs.items():
                if not isinstance(info, dict):
                    continue
                imgs = info.get("images")
                if isinstance(imgs, list):
                    total_image_count += len(imgs)
                if output_node_ids and str(node_id) not in output_node_ids:
                    continue
                if not isinstance(imgs, list):
                    continue
                for node_image in imgs:
                    if not isinstance(node_image, dict):
                        continue
                    filename = node_image.get("filename")
                    subfolder = node_image.get("subfolder") or ""
                    image_url = node_image.get("url")
                    image_type = node_image.get("type") or node_image.get("image_type")
                    images.append(
                        {
                            "nodeId": str(node_id),
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": image_type,
                            "url": image_url or "",
                            "base64": node_image.get("base64"),
                            "mime": node_image.get("mime_type"),
                        }
                    )
        if output_node_ids and not images and total_image_count > 0 and isinstance(outputs, dict):
            for node_id, info in outputs.items():
                if not isinstance(info, dict):
                    continue
                imgs = info.get("images")
                if not isinstance(imgs, list):
                    continue
                for node_image in imgs:
                    if not isinstance(node_image, dict):
                        continue
                    filename = node_image.get("filename")
                    subfolder = node_image.get("subfolder") or ""
                    image_url = node_image.get("url")
                    image_type = node_image.get("type") or node_image.get("image_type")
                    images.append(
                        {
                            "nodeId": str(node_id),
                            "filename": filename,
                            "subfolder": subfolder,
                            "type": image_type,
                            "url": image_url or "",
                            "base64": node_image.get("base64"),
                            "mime": node_image.get("mime_type"),
                        }
                    )
        return {"images": images, "history": entry}

    def _store_remote_asset(
        self,
        url: str,
        context: ExecutionContext,
        *,
        tag: str,
        expected_size: tuple[int, int] | None = None,
    ) -> dict[str, Any] | None:
        filename_hint = self._extract_filename_hint(url)
        # ComfyUI's /view endpoint can be flaky under load (occasionally 502 even though
        # the file becomes available moments later). Retry a few times before giving up.
        for attempt in range(4):
            try:
                if expected_size:
                    response = httpx.get(url, timeout=60)
                    response.raise_for_status()
                    normalized = self._resize_delivery_image(response.content, expected_size)
                    return media_ingest_service.upload_generated_image_bytes(
                        data=normalized,
                        user_id=str(context.task.user_id or "comfyui"),
                        filename=filename_hint or "comfyui.png",
                        content_type="image/png",
                        tag=tag,
                    )
                return media_ingest_service.ingest_from_remote_url(
                    url,
                    user_id=str(context.task.user_id or "comfyui"),
                    filename_hint=filename_hint,
                    tag=tag,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status and status >= 500 and attempt < 3:
                    time.sleep(0.6 * (1.8**attempt))
                    continue
                self._logger.warning("Failed to ingest remote ComfyUI asset (status=%s): %s", status, exc)
                return None
            except httpx.HTTPError as exc:
                if attempt < 3:
                    time.sleep(0.6 * (1.8**attempt))
                    continue
                self._logger.warning("Failed to ingest remote ComfyUI asset: %s", exc)
                return None
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.warning("Failed to ingest remote ComfyUI asset: %s", exc)
                return None
        return None

    def _store_base64_asset(
        self,
        payload: str,
        context: ExecutionContext,
        *,
        tag: str,
        expected_size: tuple[int, int] | None = None,
    ) -> dict[str, Any] | None:
        try:
            if expected_size:
                data_part = payload.split(",", 1)[1] if payload.startswith("data:") else payload
                normalized = self._resize_delivery_image(base64.b64decode(data_part), expected_size)
                return media_ingest_service.upload_generated_image_bytes(
                    data=normalized,
                    user_id=str(context.task.user_id or "comfyui"),
                    filename="comfyui.png",
                    content_type="image/png",
                    tag=tag,
                )
            return media_ingest_service.ingest_from_base64(
                payload,
                user_id=str(context.task.user_id or "comfyui"),
                filename_hint="comfyui.png",
                mime_type="image/png",
                tag=tag,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to ingest base64 ComfyUI asset: %s", exc)
            return None

    @staticmethod
    def _resize_delivery_image(data: bytes, expected_size: tuple[int, int]) -> bytes:
        target_width, target_height = expected_size
        if target_width <= 0 or target_height <= 0:
            raise ValueError("COMFYUI_EXPECTED_SIZE_INVALID")
        with Image.open(BytesIO(data)) as source:
            image = source.convert("RGBA")
            if image.size != expected_size:
                image = image.resize(expected_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()

    def _build_image_url(self, base_url: str, image: dict[str, Any]) -> str | None:
        filename = image.get("filename")
        if not filename:
            return None
        params = {
            "filename": filename,
            "subfolder": image.get("subfolder") or "",
            "type": image.get("type") or "output",
        }
        return f"{base_url}/view?{urlencode(params)}"

    def _prepare_graph_inputs(
        self, context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        inputs = context.payload or {}
        if not inputs:
            return None, None
        if self._looks_like_node_overrides(inputs):
            return inputs, None
        workflow_meta = getattr(context.workflow, "extra_metadata", None) or {}
        mapping = workflow_meta.get("input_node_map") or workflow_meta.get("inputNodeMap")
        mapped_overrides, mapped_error = self._build_metadata_inputs(mapping, inputs, context)

        workflow_key = workflow_meta.get("workflow_key") or workflow_definition.get("workflow_key")
        base_overrides: dict[str, dict[str, Any]] | None = None
        base_error: str | None = None
        if workflow_key == "sifang_lianxu":
            base_overrides, base_error = self._build_seamless_inputs(inputs, context)
        elif workflow_key == "yinhua_tiqu":
            base_overrides, base_error = self._build_pattern_extract_inputs(inputs, context, workflow_definition)
        elif workflow_key == "yinhua_tiqu_lora_8step":
            base_overrides, base_error = self._build_pattern_extract_lora_8step_inputs(inputs, context, workflow_definition)
        elif workflow_key == "huawen_kuotu":
            base_overrides, base_error = self._build_pattern_expand_inputs(inputs, context, workflow_definition)
        elif workflow_key == "flux2_klein_9b_outpaint":
            base_overrides, base_error = self._build_flux2_klein_9b_outpaint_inputs(inputs, context, workflow_definition)
        elif workflow_key == "beijing_koutu":
            base_overrides, base_error = self._build_background_remove_inputs(inputs, context, workflow_definition)
        elif workflow_key == "toubu_kouxiang":
            base_overrides, base_error = self._build_head_extract_inputs(inputs, context, workflow_definition)
        elif workflow_key == "flux2_9b_liebian_sifang":
            base_overrides, base_error = self._build_flux2_9b_liebian_sifang_inputs(inputs, context, workflow_definition)
        elif workflow_key == "qwen2512_print_shape_text_enhance":
            base_overrides, base_error = self._build_qwen2512_print_shape_text_enhance_inputs(
                inputs, context, workflow_definition
            )
        elif workflow_key == "qwen2512_text2img_text_allowed":
            base_overrides, base_error = self._build_qwen2512_text2img_text_allowed_inputs(
                inputs, context, workflow_definition
            )
        elif workflow_key in {"jisu_chuli", "zhongsu_tisheng"}:
            base_overrides, base_error = self._build_jisu_chuli_inputs(inputs, context, workflow_definition)
        elif workflow_key == "duotu_ronghe":
            base_overrides, base_error = self._build_duotu_ronghe_inputs(inputs, context, workflow_definition)
        elif workflow_key == "e7_flux2_liebian":
            base_overrides, base_error = self._build_e7_flux2_liebian_inputs(inputs, context, workflow_definition)
        elif workflow_key == "flux_strong_hq_softstyle_fission":
            base_overrides, base_error = self._build_flux_strong_hq_softstyle_fission_inputs(
                inputs, context, workflow_definition
            )

        if base_error:
            return None, base_error
        if mapped_error and not base_overrides:
            return None, mapped_error

        overrides = self._merge_overrides(base_overrides, mapped_overrides)
        return overrides, None

    @staticmethod
    def _merge_overrides(
        base: dict[str, dict[str, Any]] | None, extra: dict[str, dict[str, Any]] | None
    ) -> dict[str, dict[str, Any]] | None:
        if not base:
            return extra
        if not extra:
            return base
        for node_id, node_inputs in extra.items():
            if node_id not in base:
                base[node_id] = node_inputs
                continue
            base[node_id].update(node_inputs)
        return base

    def _build_metadata_inputs(
        self, mapping: Any, params: dict[str, Any], context: ExecutionContext
    ) -> tuple[dict[str, dict[str, Any]] | None, str | None]:
        if not mapping or not isinstance(mapping, list):
            return None, None
        overrides: dict[str, dict[str, Any]] = {}
        image_url: str | None = None
        requires_image = False
        image_fields = {"image", "imageurl", "image_url", "imagebase64", "image_base64", "imagelist", "image_list"}

        for item in mapping:
            if not isinstance(item, dict):
                continue
            field = item.get("field") or item.get("name") or item.get("param")
            node_id = item.get("node_id") or item.get("nodeId")
            input_key = item.get("input_key") or item.get("inputKey") or item.get("input")
            value_type = item.get("value_type") or item.get("valueType") or item.get("type")
            if not field or not node_id or not input_key:
                continue

            field_name = str(field).strip()
            if not field_name:
                continue

            value = params.get(field_name)
            field_key = field_name.lower()
            if value is None and field_key in image_fields:
                requires_image = True
                if image_url is None:
                    image_url, _ = self._resolve_image_source(params, context)
                if field_key in {"imagebase64", "image_base64"}:
                    value = self._normalize_base64(params.get(field_name))
                else:
                    value = image_url

            if value is None:
                continue

            coerced = self._coerce_metadata_value(value, value_type)
            if coerced is None and value is not None:
                continue
            overrides.setdefault(str(node_id), {})[str(input_key)] = coerced

        if requires_image and not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        return (overrides or None), None

    @staticmethod
    def _coerce_metadata_value(value: Any, value_type: Any) -> Any:
        if value_type is None:
            return value
        value_type = str(value_type).strip().lower()
        if not value_type:
            return value
        if value_type in {"int", "integer"}:
            raw = value
            if isinstance(raw, str):
                raw = raw.strip().lower().replace("px", "")
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
        if value_type in {"float", "number"}:
            raw = value
            if isinstance(raw, str):
                raw = raw.strip().lower().replace("px", "")
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None
        if value_type in {"bool", "boolean"}:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "y", "on"}:
                    return True
                if normalized in {"false", "0", "no", "n", "off"}:
                    return False
            return None
        if value_type in {"json", "object"}:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return None
            return value
        return value

    def _looks_like_node_overrides(self, payload: dict[str, Any]) -> bool:
        try:
            return all(str(key).isdigit() and isinstance(value, dict) for key, value in payload.items())
        except AttributeError:
            return False

    def _build_seamless_inputs(
        self, params: dict[str, Any], context: ExecutionContext
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        workflow_definition = context.workflow.definition or {}
        workflow_definition["_max_output_images"] = 1
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        # Seamless workflow uses URL as source image (114 -> 96/113).
        # Keep node 104 untouched: it is a fixed mask input in this workflow.
        overrides.setdefault("114", {})["value"] = image_url
        # Add a fragment-only cache buster for LoadImagesFromURL.
        # This avoids reusing a stale/empty cached output while keeping the real
        # remote URL unchanged on server side (fragment is not sent in HTTP request).
        overrides["96"] = {"url": self._append_cache_bust_fragment(image_url)}
        overrides.setdefault("102", {})["image"] = ["96", 0]

        prompt = self._as_text(params.get("prompt") or params.get("description"))
        if prompt:
            overrides.setdefault("42", {})["string_a"] = prompt

        pattern_type = self._as_text(params.get("patternType") or params.get("pattern_type"))
        if pattern_type:
            normalized = pattern_type.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
            twoway_aliases = {"twoway", "2way", "two", "二方连续", "两方连续"}
            seamless_aliases = {"seamless", "4way", "fourway", "四方连续"}
            if normalized in twoway_aliases:
                overrides.setdefault("97", {})["boolean"] = False
            elif normalized in seamless_aliases:
                overrides.setdefault("97", {})["boolean"] = True

        size = self._coerce_positive_int(params.get("size") or params.get("output_size") or params.get("outputSize"))
        width = self._coerce_positive_int(params.get("width"))
        height = self._coerce_positive_int(params.get("height"))
        if size and not (width or height):
            width = size
            height = size
        width = self._normalize_comfy_dim(width)
        height = self._normalize_comfy_dim(height)
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides.setdefault("102", {}).update(node_inputs)

        return (overrides or None), None

    @staticmethod
    def _append_cache_bust_fragment(url: str) -> str:
        try:
            parsed = urlparse(url)
            marker = f"podi_cb={time.time_ns()}"
            if parsed.fragment:
                fragment = f"{parsed.fragment}&{marker}"
            else:
                fragment = marker
            return parsed._replace(fragment=fragment).geturl()
        except Exception:
            return url

    def _build_pattern_extract_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["393"] = {"url": image_url}

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("111", {})["prompt"] = prompt

        negative = self._as_text(params.get("negative_prompt") or params.get("negativePrompt"))
        if negative:
            overrides.setdefault("110", {})["prompt"] = negative

        width = self._coerce_positive_int(params.get("output_width") or params.get("width"))
        height = self._coerce_positive_int(params.get("output_height") or params.get("height"))
        width = self._normalize_comfy_dim(width)
        height = self._normalize_comfy_dim(height)
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["400"] = node_inputs

        batch_count = self._coerce_positive_int(
            params.get("batch_count") or params.get("batchCount") or params.get("repeat_count") or params.get("batch") or params.get("n")
        )
        if batch_count:
            overrides.setdefault("424", {})["amount"] = batch_count
            workflow_definition["_expected_image_count"] = batch_count
            base_timeout = self._coerce_positive_int(workflow_definition.get("timeout")) or 180
            effective_timeout = max(base_timeout, int(base_timeout * batch_count * 1.2))
            workflow_definition["timeout"] = effective_timeout

        lora_name = self._as_text(params.get("lora") or params.get("lora_name") or params.get("loraName"))
        if lora_name:
            overrides.setdefault("390", {})["lora_name"] = lora_name

        return (overrides or None), None

    def _build_pattern_extract_lora_8step_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """8步加速可换 LoRA 版印花提取。

        Node mapping (see `backend/app/workflows/comfyui/yinhua_tiqu_lora_8step.json`):
        - 393: LoadImagesFromURL.url
        - 111: positive prompt
        - 110: negative prompt
        - 390: effect/style LoRA
        - 400: LatentUpscale.width/height
        - 424: RepeatLatentBatch.amount
        """

        overrides: dict[str, dict[str, Any]] = {}

        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["393"] = {"url": image_url}

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("111", {})["prompt"] = prompt

        negative = self._as_text(params.get("negative_prompt") or params.get("negativePrompt"))
        if negative:
            overrides.setdefault("110", {})["prompt"] = negative

        lora_name = self._as_text(params.get("lora") or params.get("lora_name") or params.get("loraName"))
        if lora_name:
            overrides.setdefault("390", {})["lora_name"] = lora_name

        batch = self._coerce_positive_int(params.get("batch") or params.get("amount") or params.get("n"))
        if batch:
            overrides.setdefault("424", {})["amount"] = batch
            workflow_definition["_expected_image_count"] = batch

        width = self._coerce_positive_int(params.get("output_width") or params.get("width"))
        height = self._coerce_positive_int(params.get("output_height") or params.get("height"))

        if not width or not height:
            try:
                resp = httpx.get(image_url, timeout=30)
                resp.raise_for_status()
                im = Image.open(BytesIO(resp.content))
                src_w, src_h = im.size
                width = width or int(src_w)
                height = height or int(src_h)
            except Exception:
                pass

        width = self._normalize_comfy_dim(width)
        height = self._normalize_comfy_dim(height)
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["400"] = node_inputs

        return (overrides or None), None

    def _build_pattern_expand_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["205"] = {"url": image_url}

        prompt = self._as_text(params.get("prompt"))
        if prompt:
            overrides.setdefault("74", {})["text"] = prompt

        negative = self._as_text(params.get("negative_prompt") or params.get("negativePrompt"))
        if negative:
            # Node 72 is the default negative CLIPTextEncode text.
            overrides.setdefault("72", {})["text"] = negative

        # NOTE: Node 61 controls a pre-scale (longest side) that affects quality/speed.
        # For business users, we keep it fixed in the workflow JSON (default 720) and
        # do not expose/override it via API params to avoid confusion.

        lora_name = self._as_text(params.get("lora") or params.get("lora_name") or params.get("loraName"))
        if lora_name:
            # Node 45 is the workflow's LoraLoaderModelOnly.
            overrides.setdefault("45", {})["lora_name"] = lora_name

        mapping = {
            "expand_left": ("188", "value"),
            "expand_right": ("189", "value"),
            "expand_top": ("186", "value"),
            "expand_bottom": ("187", "value"),
        }
        for field, (node_id, key) in mapping.items():
            value = self._coerce_positive_int(params.get(field))
            if value is not None:
                overrides.setdefault(node_id, {})[key] = value

        return (overrides or None), None

    def _build_flux2_klein_9b_outpaint_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"

        base_url = str(context.executor.base_url or "").rstrip("/")
        staged_name = self._upload_image_for_comfyui_loadimage(
            image_url=image_url,
            base_url=base_url,
            prefix="flux2-outpaint",
        )
        if not staged_name:
            return None, "COMFYUI_IMAGE_UPLOAD_FAILED"
        overrides["76"] = {"image": staged_name}

        mapping = {
            "expand_left": "left",
            "expand_right": "right",
            "expand_top": "top",
            "expand_bottom": "bottom",
        }
        for field, node_key in mapping.items():
            value = self._coerce_positive_int(params.get(field))
            if value is not None:
                overrides.setdefault("102", {})[node_key] = value

        seed = secrets.randbelow(2**63 - 1) + 1
        overrides.setdefault("99", {})["seed"] = seed

        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["9"]
        return (overrides or None), None

    def _build_background_remove_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["5"] = {"url": image_url}
        # SaveImage can be fully cached by ComfyUI and then /history may contain no images.
        overrides["4"] = {"filename_prefix": f"bg_remove_{uuid4().hex[:8]}"}
        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["4"]
        return overrides, None

    def _build_head_extract_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["141"] = {"url": image_url}
        # Randomize Florence2 seed to avoid full-graph caching on ComfyUI,
        # which causes /history to return empty outputs and leaves the task
        # stuck in running forever.
        overrides["134"] = {"seed": secrets.randbelow(2**63 - 1) + 1}
        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["140"]
        return overrides, None

    def _build_flux2_9b_liebian_sifang_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["141"] = {"url": image_url}
        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("132", {})["inStr"] = prompt
        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["111"]
        return overrides, None

    def _build_qwen2512_print_shape_text_enhance_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """裂变文字强化：图像输入 + 文本强化 + 重绘幅度映射 denoise。

        Node mapping (see `backend/app/workflows/comfyui/qwen2512_print_shape_text_enhance.json`):
        - 10: LoadImagesFromURL.url
        - 13: CR Text Concatenate.text1
        - 27: KSampler.seed / steps / cfg / denoise
        - 29: SaveImage
        """

        overrides: dict[str, dict[str, Any]] = {}

        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["10"] = {"url": image_url}

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("13", {})["text1"] = prompt

        seed = self._coerce_positive_int(params.get("seed"))
        if seed is None:
            seed = secrets.randbelow(2**63 - 1) + 1
        overrides.setdefault("27", {})["seed"] = seed

        steps = self._coerce_positive_int(params.get("steps"))
        if steps is None:
            steps = self._coerce_positive_int(workflow_definition.get("steps")) or 8
        overrides.setdefault("27", {})["steps"] = steps

        cfg_raw = params.get("cfg")
        if cfg_raw is None:
            cfg_raw = workflow_definition.get("cfg", 1.0)
        try:
            overrides.setdefault("27", {})["cfg"] = float(cfg_raw)
        except (TypeError, ValueError):
            overrides.setdefault("27", {})["cfg"] = 1.0

        repaint_value = params.get("bili")
        if repaint_value in (None, ""):
            repaint_value = params.get("similarity")
        if repaint_value in (None, ""):
            repaint_value = 25
        denoise = self._map_repaint_strength_to_denoise(repaint_value)
        if denoise is not None:
            overrides.setdefault("27", {})["denoise"] = denoise

        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["29"]
        return overrides, None

    def _build_qwen2512_text2img_text_allowed_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """文字强化文生图：用户确认提示词后直接文生图，不再二次改写。

        Node mapping:
        - 10: CLIPTextEncode.text -> editable_prompt
        - 11: CLIPTextEncode.text -> editable_negative_prompt
        - 12: EmptySD3LatentImage.width / height / batch_size
        - 19: KSampler.seed / steps / cfg
        - 21: SaveImage
        """

        prompt = self._as_text(
            params.get("editable_prompt")
            or params.get("editablePrompt")
            or params.get("prompt")
            or params.get("positive_prompt")
            or params.get("positivePrompt")
        )
        if not prompt:
            return None, "COMFYUI_PROMPT_REQUIRED"

        raw_negative = self._as_text(
            params.get("editable_negative_prompt")
            or params.get("editableNegativePrompt")
            or params.get("negative_prompt")
            or params.get("negativePrompt")
        )
        negative_prompt = self._merge_negative_prompt(raw_negative, TEXT2IMG_TEXT_ALLOWED_NEGATIVE_DEFAULT)

        width = self._normalize_comfy_dim(
            self._coerce_positive_int(params.get("width") or params.get("output_width") or params.get("outputWidth"))
        )
        height = self._normalize_comfy_dim(
            self._coerce_positive_int(params.get("height") or params.get("output_height") or params.get("outputHeight"))
        )
        width = width or 1024
        height = height or 1024
        batch_size = self._coerce_positive_int(params.get("batch_size") or params.get("batch") or params.get("n"))
        batch_size = 1 if batch_size is None else max(1, min(batch_size, 1))

        seed = self._coerce_positive_int(params.get("seed"))
        if seed is None:
            seed = secrets.randbelow(2**63 - 1) + 1

        steps = self._coerce_positive_int(params.get("steps"))
        if steps is None:
            steps = self._coerce_positive_int(workflow_definition.get("steps")) or 8

        cfg_raw = params.get("cfg")
        if cfg_raw is None:
            cfg_raw = workflow_definition.get("cfg", 2.0)
        try:
            cfg = float(cfg_raw)
        except (TypeError, ValueError):
            cfg = 2.0

        overrides: dict[str, dict[str, Any]] = {
            "10": {"text": prompt},
            "11": {"text": negative_prompt},
            "12": {"width": width, "height": height, "batch_size": batch_size},
            "19": {"seed": seed, "steps": steps, "cfg": cfg},
        }
        workflow_definition["_max_output_images"] = 1
        workflow_definition["_expected_image_count"] = 1
        workflow_definition["output_node_ids"] = ["21"]
        return overrides, None

    def _build_jisu_chuli_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """极速处理版：图生图编辑（正/反提示词 + 图片 + 批次 + 输出尺寸）。

        Node mapping (see `backend/app/workflows/comfyui/jisu_chuli.json`):
        - 393: LoadImagesFromURL.url
        - 111: positive prompt
        - 110: negative prompt
        - 434: RepeatLatentBatch.amount (batch)
        - 433: LatentUpscale.width/height (output size)
        """

        overrides: dict[str, dict[str, Any]] = {}

        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["393"] = {"url": image_url}

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("111", {})["prompt"] = prompt

        negative = self._as_text(params.get("negative_prompt") or params.get("negativePrompt"))
        if negative:
            overrides.setdefault("110", {})["prompt"] = negative

        lora_name = self._as_text(params.get("lora") or params.get("lora_name") or params.get("loraName"))
        if lora_name:
            overrides.setdefault("89", {})["lora_name"] = lora_name

        batch = self._coerce_positive_int(params.get("batch") or params.get("amount") or params.get("n"))
        if batch:
            overrides.setdefault("434", {})["amount"] = batch
            workflow_definition["_expected_image_count"] = batch

        width = self._coerce_positive_int(params.get("output_width") or params.get("width"))
        height = self._coerce_positive_int(params.get("output_height") or params.get("height"))

        # Default to original image size when not provided.
        if not width or not height:
            try:
                resp = httpx.get(image_url, timeout=30)
                resp.raise_for_status()
                im = Image.open(BytesIO(resp.content))
                src_w, src_h = im.size
                width = width or int(src_w)
                height = height or int(src_h)
            except Exception:
                # Leave as-is; workflow has defaults (512x512).
                pass

        width = self._normalize_comfy_dim(width)
        height = self._normalize_comfy_dim(height)
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["433"] = node_inputs

        return (overrides or None), None

    def _build_duotu_ronghe_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        graph = normalize_comfyui_prompt_graph(workflow_definition) or workflow_definition.get("graph") or workflow_definition
        graph_nodes = graph if isinstance(graph, dict) else {}

        primary_url = self._normalize_remote_url(self._as_text(params.get("imageUrl") or params.get("image_url")))
        aux_values: list[str] = []
        for key in ("image_url_2", "imageUrl2", "aux_image_1", "image_url_3", "imageUrl3", "aux_image_2"):
            normalized = self._normalize_remote_url(self._as_text(params.get(key)))
            if normalized:
                aux_values.append(normalized)

        extra_raw = params.get("image_urls") or params.get("imageUrls") or params.get("input_urls")
        for url in self._split_url_list(extra_raw):
            normalized = self._normalize_remote_url(url)
            if normalized:
                aux_values.append(normalized)

        if not primary_url:
            image_list = params.get("imageList") or params.get("image_list")
            if isinstance(image_list, list):
                normalized_urls: list[str] = []
                for entry in image_list:
                    if not isinstance(entry, dict):
                        continue
                    url = self._normalize_remote_url(self._as_text(entry.get("ossUrl") or entry.get("url")))
                    if url:
                        normalized_urls.append(url)
                if normalized_urls:
                    primary_url = normalized_urls[0]
                    aux_values.extend(normalized_urls[1:])

        if not primary_url:
            return None, "COMFYUI_IMAGE_REQUIRED"

        seen: set[str] = set()
        deduped_aux: list[str] = []
        for url in aux_values:
            if not url or url == primary_url or url in seen:
                continue
            seen.add(url)
            deduped_aux.append(url)
        aux_values = deduped_aux[:2]

        staged_primary = self._upload_image_for_comfyui_loadimage(
            image_url=primary_url,
            base_url=str(context.executor.base_url or "").rstrip("/"),
            prefix="duotu-primary",
        )
        if not staged_primary:
            return None, "COMFYUI_IMAGE_UPLOAD_FAILED"
        overrides["78"] = {"image": staged_primary}

        staged_aux_1 = None
        staged_aux_2 = None
        if aux_values:
            staged_aux_1 = self._upload_image_for_comfyui_loadimage(
                image_url=aux_values[0],
                base_url=str(context.executor.base_url or "").rstrip("/"),
                prefix="duotu-aux1",
            )
            if not staged_aux_1:
                return None, "COMFYUI_IMAGE_UPLOAD_FAILED"
            overrides["106"] = {"image": staged_aux_1}
        if len(aux_values) > 1:
            staged_aux_2 = self._upload_image_for_comfyui_loadimage(
                image_url=aux_values[1],
                base_url=str(context.executor.base_url or "").rstrip("/"),
                prefix="duotu-aux2",
            )
            if not staged_aux_2:
                return None, "COMFYUI_IMAGE_UPLOAD_FAILED"
            overrides["108"] = {"image": staged_aux_2}

        for node_id in ("110", "111"):
            node = graph_nodes.get(node_id)
            if not isinstance(node, dict):
                continue
            node_inputs = node.get("inputs")
            if not isinstance(node_inputs, dict):
                continue
            if staged_aux_1:
                node_inputs["image2"] = ["106", 0]
            else:
                node_inputs.pop("image2", None)
            if staged_aux_2:
                node_inputs["image3"] = ["108", 0]
            else:
                node_inputs.pop("image3", None)

        width = self._normalize_comfy_dim(self._coerce_positive_int(params.get("width") or params.get("output_width")))
        height = self._normalize_comfy_dim(self._coerce_positive_int(params.get("height") or params.get("output_height")))
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["112"] = node_inputs

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("111", {})["prompt"] = prompt

        negative = self._as_text(params.get("negative_prompt") or params.get("negativePrompt"))
        if negative:
            overrides.setdefault("110", {})["prompt"] = negative

        seed = self._coerce_positive_int(params.get("seed"))
        if not seed:
            seed = secrets.randbelow(2**63 - 1) + 1
        overrides.setdefault("151", {})["seed"] = seed

        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["60"]
        return (overrides or None), None

    @staticmethod
    def _map_similarity_to_denoise(value: Any) -> float | None:
        if isinstance(value, str):
            value = value.strip().replace("%", "")
        try:
            similarity = float(value)
        except (TypeError, ValueError):
            return None
        similarity = int(math.floor(similarity + 0.5))
        similarity = max(0, min(100, similarity))
        denoise = 0.95 - similarity * 0.004
        return round(max(0.55, denoise), 2)

    @staticmethod
    def _map_variation_percent_to_denoise(value: Any) -> float | None:
        if isinstance(value, str):
            value = value.strip().replace("%", "")
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return None
        percent = max(0.0, min(100.0, percent))
        return round(0.45 + percent * 0.0035, 3)

    @staticmethod
    def _map_colorlock_variation_percent_to_denoise(value: Any) -> float | None:
        if isinstance(value, str):
            value = value.strip().replace("%", "")
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return None
        percent = max(0.0, min(100.0, percent))
        return round(0.45 + percent * 0.0035, 3)

    @staticmethod
    def _map_repaint_strength_to_denoise(value: Any) -> float | None:
        return ComfyUIExecutorAdapter._map_variation_percent_to_denoise(value)

    @staticmethod
    def _merge_negative_prompt(user_value: str | None, default_value: str) -> str:
        items: list[str] = []
        seen: set[str] = set()
        for source in (user_value, default_value):
            for raw in str(source or "").split(","):
                item = raw.strip()
                key = item.lower()
                if not item or key in seen:
                    continue
                seen.add(key)
                items.append(item)
        return ", ".join(items)

    @staticmethod
    def _parse_fission_percent(value: Any) -> float | None:
        if isinstance(value, str):
            value = value.strip().replace("%", "")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fission_v4_band(value: Any) -> str:
        percent = ComfyUIExecutorAdapter._parse_fission_percent(value)
        if percent is None:
            return "high"
        if percent <= 30:
            return "low"
        if percent <= 65:
            return "mid"
        if percent <= 100:
            return "high"
        return "experimental"

    @staticmethod
    def _parse_jsonish_payload(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return None
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _extract_fission_card(params: dict[str, Any]) -> dict[str, Any]:
        raw = (
            params.get("vl_result")
            or params.get("vlResult")
            or params.get("fissionControlCard")
            or params.get("vl_card")
            or params.get("vlCard")
        )
        parsed = ComfyUIExecutorAdapter._parse_jsonish_payload(raw)
        if not isinstance(parsed, dict):
            return {}
        for key in ("fissionControlCard", "vl_result", "vlResult", "vl_card", "vlCard"):
            nested = parsed.get(key)
            if isinstance(nested, dict):
                return nested
        return parsed

    @staticmethod
    def _first_float(*values: Any) -> float | None:
        for value in values:
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _normalize_pattern_risk_type(value: Any) -> str:
        risk_type = str(value or "").strip()
        return risk_type if risk_type in FISSION_V4_ROUTE_MAP else "unknown_or_uncertain"

    @staticmethod
    def _map_fission_v4_denoise(value: Any, pattern_risk_type: Any) -> float:
        risk_type = ComfyUIExecutorAdapter._normalize_pattern_risk_type(pattern_risk_type)
        band = ComfyUIExecutorAdapter._fission_v4_band(value)
        route = FISSION_V4_ROUTE_MAP.get(risk_type) or FISSION_V4_ROUTE_MAP["unknown_or_uncertain"]
        return round(float(route.get(band) or route.get("high") or 0.52), 3)

    def _build_e7_flux2_liebian_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """E7 + FLUX2 裂变重绘。

        Node mapping (see `backend/app/workflows/comfyui/e7_flux2_liebian.json`):
        - 10: LoadImagesFromURL.url
        - 13: CR Text Concatenate.text1/text2
        - 18: CFGGuider.cfg
        - 19: RandomNoise.noise_seed
        - 21: BasicScheduler.steps/denoise
        - 24: CR Latent Batch Size.batch_size
        - 12: ImageResize+.width/height
        """

        overrides: dict[str, dict[str, Any]] = {}

        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"

        overrides["10"] = {"url": image_url}

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt"))
        if prompt:
            overrides.setdefault("13", {})["text1"] = prompt

        image_desc = self._as_text(params.get("image_desc") or params.get("imageDesc"))
        if image_desc:
            overrides.setdefault("13", {})["text2"] = image_desc

        cfg = params.get("cfg")
        if cfg is not None:
            try:
                overrides.setdefault("18", {})["cfg"] = float(cfg)
            except (TypeError, ValueError):
                pass

        seed = self._coerce_positive_int(params.get("seed"))
        if seed is not None:
            overrides.setdefault("19", {})["noise_seed"] = seed

        steps = self._coerce_positive_int(params.get("steps"))
        if steps is not None:
            overrides.setdefault("21", {})["steps"] = steps

        repaint_value = params.get("bili")
        if repaint_value not in (None, ""):
            denoise = self._map_repaint_strength_to_denoise(repaint_value)
        else:
            similarity_value = params.get("similarity")
            if similarity_value not in (None, ""):
                denoise = self._map_similarity_to_denoise(similarity_value)
            else:
                denoise = self._map_repaint_strength_to_denoise(25)
        if denoise is not None:
            overrides.setdefault("21", {})["denoise"] = denoise

        batch_size = self._coerce_positive_int(params.get("batch_size") or params.get("batch") or params.get("n"))
        if batch_size:
            overrides.setdefault("24", {})["batch_size"] = batch_size
            workflow_definition["_expected_image_count"] = batch_size

        explicit_width = self._coerce_positive_int(params.get("output_width") or params.get("width"))
        explicit_height = self._coerce_positive_int(params.get("output_height") or params.get("height"))
        width = explicit_width
        height = explicit_height
        if (width and not height) or (height and not width):
            try:
                resp = httpx.get(image_url, timeout=30)
                resp.raise_for_status()
                im = Image.open(BytesIO(resp.content))
                src_w, src_h = im.size
                width = width or int(src_w)
                height = height or int(src_h)
            except Exception:
                pass

        target_multiple = 16 if (explicit_width or explicit_height) else 8
        width = self._normalize_comfy_dim(width, multiple=target_multiple)
        height = self._normalize_comfy_dim(height, multiple=target_multiple)
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            if explicit_width and explicit_height:
                node_inputs["method"] = "fill / crop"
            overrides["12"] = node_inputs

        workflow_definition["output_node_ids"] = ["27"]
        return (overrides or None), None

    def _build_flux_strong_hq_softstyle_fission_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """05 Strong HQ SoftStyle 图裂变。

        Node mapping (see `backend/app/workflows/comfyui/flux_strong_hq_softstyle_fission.json`):
        - 10: LoadImage.image (staged file under ComfyUI input)
        - 12: ImageResize+.width/height
        - 13: CR Text Concatenate.text1/text2
        - 20: IPAdapterAdvanced.weight
        - 21: CFGGuider.cfg
        - 22: RandomNoise.noise_seed
        - 24: BasicScheduler.steps/denoise
        - 27: CR Latent Batch Size.batch_size
        - 30: ColorMatch.method/strength
        """

        overrides: dict[str, dict[str, Any]] = {}

        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"

        base_url = str(context.executor.base_url or "").rstrip("/")
        staged_name = self._upload_image_for_comfyui_loadimage(
            image_url=image_url,
            base_url=base_url,
            prefix="flux05-pattern",
        )
        if not staged_name:
            return None, "COMFYUI_IMAGE_UPLOAD_FAILED"
        overrides["10"] = {"image": staged_name}

        prompt = self._as_text(params.get("prompt") or params.get("positive_prompt")) or ""
        image_desc = self._as_text(params.get("image_desc") or params.get("imageDesc")) or ""
        overrides["13"] = {"text1": prompt, "text2": image_desc}

        fission_card = self._extract_fission_card(params)
        profile = self._as_text(params.get("profile") or params.get("profile_id")) or ""
        is_aspect_recompose = self._as_text(params.get("aspect_recompose_route")) == "pattern_recompose"
        is_colorlock_v2 = (
            params.get("bili_mapping") == "variation_percent_045_080_colorlock_v2"
            or profile in {FISSION_V4_DEFAULT_PROFILE, "pattern_color_lock_v2", "pattern_color_lock_strict_v2"}
        )
        is_v4_routed = (
            is_aspect_recompose
            or profile == FISSION_V4_DEFAULT_PROFILE
            or self._as_text(params.get("bili_mapping")) == "pattern_risk_routed_v4"
            or bool(fission_card.get("pattern_risk_type") or params.get("pattern_risk_type") or params.get("patternRiskType"))
        )

        repaint_value = params.get("bili")
        if repaint_value in (None, ""):
            repaint_value = "80%" if is_v4_routed else ("6%" if profile == "pattern_color_lock_strict_v2" else ("15%" if is_colorlock_v2 else 90))
        if is_aspect_recompose:
            denoise = self._first_float(params.get("aspect_recompose_denoise"), params.get("denoise"), 0.68) or 0.68
            denoise = max(0.62, min(0.74, denoise))
        elif is_v4_routed:
            pattern_risk_type = (
                params.get("pattern_risk_type")
                or params.get("patternRiskType")
                or fission_card.get("pattern_risk_type")
                or fission_card.get("patternRiskType")
                or fission_card.get("pattern_type")
                or fission_card.get("patternType")
            )
            denoise = self._map_fission_v4_denoise(repaint_value, pattern_risk_type)
        elif is_colorlock_v2:
            denoise = self._map_colorlock_variation_percent_to_denoise(repaint_value)
        elif params.get("bili_mapping") == "variation_percent_045_080":
            denoise = self._map_variation_percent_to_denoise(repaint_value)
        elif params.get("bili") not in (None, ""):
            denoise = self._map_repaint_strength_to_denoise(repaint_value)
        else:
            similarity_value = params.get("similarity")
            if similarity_value not in (None, ""):
                denoise = self._map_similarity_to_denoise(similarity_value)
            else:
                denoise = self._map_repaint_strength_to_denoise(repaint_value)
        if denoise is None:
            denoise = 0.60

        steps = 8
        batch_size = 1
        cfg_value = 1.0
        ipadapter_weight_value = 0.25
        colormatch_strength_value = 0.20
        colormatch_method = "mkl"
        if is_v4_routed:
            ipadapter_weight_value = self._first_float(
                params.get("reference_lock"),
                params.get("referenceLock"),
                params.get("ipadapter_weight"),
                params.get("ipadapterWeight"),
                fission_card.get("recommended_reference_lock"),
                fission_card.get("recommendedReferenceLock"),
                FISSION_V4_DEFAULT_REFERENCE_LOCK,
            ) or FISSION_V4_DEFAULT_REFERENCE_LOCK
            colormatch_strength_value = self._first_float(
                params.get("color_lock"),
                params.get("colorLock"),
                params.get("colormatch_strength"),
                params.get("colormatchStrength"),
                fission_card.get("recommended_color_lock"),
                fission_card.get("recommendedColorLock"),
                FISSION_V4_DEFAULT_COLOR_LOCK,
            ) or FISSION_V4_DEFAULT_COLOR_LOCK
        elif is_colorlock_v2:
            ipadapter_weight_value = 0.45 if profile == "pattern_color_lock_strict_v2" else 0.35
            colormatch_strength_value = 0.70 if profile == "pattern_color_lock_strict_v2" else 0.55

        seed = self._coerce_positive_int(params.get("seed"))
        if seed is None:
            seed = secrets.randbelow(2**63 - 1) + 1

        overrides["20"] = {"weight": ipadapter_weight_value}
        overrides["21"] = {"cfg": cfg_value}
        overrides["22"] = {"noise_seed": seed}
        overrides["24"] = {"steps": steps, "denoise": denoise}
        overrides["27"] = {"batch_size": batch_size}
        overrides["30"] = {"method": colormatch_method, "strength": colormatch_strength_value}

        explicit_width = self._coerce_positive_int(params.get("output_width") or params.get("width"))
        explicit_height = self._coerce_positive_int(params.get("output_height") or params.get("height"))
        width = explicit_width
        height = explicit_height
        if (width and not height) or (height and not width):
            try:
                resp = httpx.get(image_url, timeout=30)
                resp.raise_for_status()
                im = Image.open(BytesIO(resp.content))
                src_w, src_h = im.size
                width = width or int(src_w)
                height = height or int(src_h)
            except Exception:
                pass

        target_multiple = 16 if (explicit_width or explicit_height) else 8
        width = self._normalize_comfy_dim(width, multiple=target_multiple)
        height = self._normalize_comfy_dim(height, multiple=target_multiple)
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            if explicit_width and explicit_height:
                node_inputs["method"] = "fill / crop"
            overrides["12"] = node_inputs

        workflow_definition["_max_output_images"] = 1
        workflow_definition["output_node_ids"] = ["31"]
        return (overrides or None), None

    def _upload_image_for_comfyui_loadimage(self, *, image_url: str, base_url: str, prefix: str) -> str | None:
        if not image_url or not base_url:
            return None
        try:
            resp = httpx.get(image_url, timeout=60)
            resp.raise_for_status()
            filename_hint = self._extract_filename_hint(image_url)
            suffix = Path(filename_hint).suffix or mimetypes.guess_extension(resp.headers.get("content-type", "").split(";")[0].strip()) or ".png"
            staged_name = f"{prefix}-{uuid4().hex[:10]}{suffix}"
            files = {
                "image": (staged_name, resp.content, resp.headers.get("content-type", "application/octet-stream")),
            }
            data = {"type": "input", "overwrite": "true"}
            upload_resp = httpx.post(f"{base_url}/upload/image", data=data, files=files, timeout=120)
            upload_resp.raise_for_status()
            payload = upload_resp.json() if upload_resp.content else {}
            if isinstance(payload, dict):
                for key in ("name", "filename"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            return staged_name
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to upload image to ComfyUI input folder: %s", exc)
            return None

    @staticmethod
    def _split_url_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            urls: list[str] = []
            for item in value:
                urls.extend(ComfyUIExecutorAdapter._split_url_list(item))
            return urls
        if isinstance(value, dict):
            urls: list[str] = []
            for key in ("url", "ossUrl"):
                if key in value:
                    urls.extend(ComfyUIExecutorAdapter._split_url_list(value.get(key)))
            return urls
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[\n,]", value) if item.strip()]
        text_value = str(value).strip()
        return [text_value] if text_value else []

    def _resolve_image_source(
        self, params: dict[str, Any], context: ExecutionContext
    ) -> tuple[str | None, str | None]:
        image_url = self._normalize_remote_url(self._as_text(params.get("imageUrl") or params.get("image_url")))
        image_base64 = self._normalize_base64(params.get("imageBase64") or params.get("image_base64"))

        image_list = params.get("imageList") or params.get("image_list")
        if isinstance(image_list, list):
            for entry in image_list:
                if not isinstance(entry, dict):
                    continue
                url = self._as_text(entry.get("ossUrl") or entry.get("url"))
                if url:
                    url = self._normalize_remote_url(url)
                    image_url = url
                    break
                if not image_base64:
                    image_base64 = self._normalize_base64(entry.get("base64"))

        if not image_url and image_base64:
            uploaded = self._ingest_input_base64(image_base64, context, filename_hint="comfyui_input.png")
            if uploaded:
                image_url = uploaded
        # IMPORTANT: Do not download remote images into base64 by default.
        # We standardize on URL-based image loading to save backend bandwidth.
        return image_url, None

    def _ingest_input_base64(
        self, payload: str, context: ExecutionContext, *, filename_hint: str
    ) -> str | None:
        try:
            asset = media_ingest_service.ingest_from_base64(
                payload,
                user_id=str(getattr(context.task, "user_id", None) or "comfyui"),
                filename_hint=filename_hint,
                mime_type="image/png",
                tag="comfyui-input",
            )
            return asset.get("ossUrl") if isinstance(asset, dict) else None
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to ingest ComfyUI input image: %s", exc)
            return None

    @staticmethod
    def _normalize_base64(value: Any) -> str | None:
        if not value or not isinstance(value, str):
            return None
        data = value.strip()
        if not data:
            return None
        if "," in data and "base64" in data:
            data = data.split(",", 1)[1]
        return data

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        try:
            number = int(value)
            return number if number > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return str(value).strip() or None

    @staticmethod
    def _normalize_string_nodes(graph: dict[str, Any]) -> None:
        """Align custom String node inputs across ComfyUI node packs."""
        for node in graph.values():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") != "String":
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            if "String" not in inputs and "inStr" in inputs:
                inputs["String"] = inputs.get("inStr")

    @staticmethod
    def _normalize_remote_url(url: str | None) -> str | None:
        if not url:
            return url
        try:
            return quote(url, safe=":/?#[]@!$&'()*+,;=%")
        except Exception:
            return url

    @staticmethod
    def _extract_filename_hint(url: str) -> str:
        try:
            parsed = urlparse(url)
        except Exception:  # pragma: no cover - defensive
            parsed = None
        if parsed:
            query = parse_qs(parsed.query or "")
            filename = query.get("filename")
            if filename and filename[0]:
                return filename[0]
            path = (parsed.path or "").rstrip("/")
            if path:
                tail = path.split("/")[-1]
                if tail:
                    return tail
        return "comfyui.png"


def _apply_inputs(graph: dict[str, Any], inputs: dict[str, Any]) -> None:
    for node_id, node_inputs in inputs.items():
        node = graph.get(str(node_id))
        if not node:
            continue
        values = node.get("inputs")
        if not isinstance(values, dict):
            continue
        for key, value in node_inputs.items():
            values[key] = value
