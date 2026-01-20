"""ComfyUI executor adapter."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any
from urllib.parse import parse_qs, quote, urlparse, urlencode
from uuid import uuid4

import httpx
from PIL import Image
from io import BytesIO

from app.services.executors.base import ExecutionContext, ExecutionResult, ExecutorAdapter
from app.services.media_ingest import media_ingest_service


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
        graph_payload = workflow_definition.get("graph") or workflow_definition
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

        prompt_id = uuid4().hex
        submission = {"prompt": graph_payload, "prompt_id": prompt_id}
        try:
            response = httpx.post(f"{base_url}/prompt", json=submission, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            extra_details = ""
            if isinstance(exc, httpx.HTTPStatusError):
                resp = exc.response
                resp_text = resp.text[:1000] if resp is not None else ""
                extra_details = f" | status={resp.status_code if resp else 'unknown'} body={resp_text!r}"
            self._logger.warning("Failed to submit ComfyUI prompt: %s%s", exc, extra_details)
            return ExecutionResult(
                success=False,
                status="failed",
                # Surface status/body to callers (Coze shows this to users), helps diagnose
                # missing custom nodes/models on a specific ComfyUI executor.
                error_message=f"COMFYUI_SUBMIT_ERROR{extra_details}",
            )

        outputs = self._poll_history(base_url, prompt_id, timeout=workflow_definition.get("timeout", 180))
        if outputs is None:
            return ExecutionResult(
                success=False,
                status="failed",
                error_message="COMFYUI_TIMEOUT",
            )

        assets = []
        for image in outputs.get("images", []):
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

        return ExecutionResult(
            success=True,
            status="completed",
            progress=100,
            result_payload={
                "executor": context.executor.id,
                "promptId": prompt_id,
                "assets": assets,
                "raw": outputs,
            },
        )

    def _poll_history(self, base_url: str, prompt_id: str, timeout: float) -> dict[str, Any] | None:
        start = time.monotonic()
        last_data: dict[str, Any] | None = None
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
            if data and data.get(prompt_id):
                break
            time.sleep(1)

        if not last_data or prompt_id not in last_data:
            return None
        entry = last_data[prompt_id]
        outputs = entry.get("outputs") or {}
        images: list[dict[str, Any]] = []
        for _, info in outputs.items():
            for node_image in info.get("images", []):
                filename = node_image.get("filename")
                subfolder = node_image.get("subfolder") or ""
                image_url = node_image.get("url")
                image_type = node_image.get("type") or node_image.get("image_type")
                images.append(
                    {
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": image_type,
                        "url": image_url or "",
                        "base64": node_image.get("base64"),
                        "mime": node_image.get("mime_type"),
                    }
                )
        return {"images": images, "history": entry}

    def _store_remote_asset(self, url: str, context: ExecutionContext, *, tag: str) -> dict[str, Any] | None:
        try:
            filename_hint = self._extract_filename_hint(url)
            return media_ingest_service.ingest_from_remote_url(
                url,
                user_id=str(context.task.user_id or "comfyui"),
                filename_hint=filename_hint,
                tag=tag,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to ingest remote ComfyUI asset: %s", exc)
            return None

    def _store_base64_asset(self, payload: str, context: ExecutionContext, *, tag: str) -> dict[str, Any] | None:
        try:
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
        workflow_key = workflow_meta.get("workflow_key") or workflow_definition.get("workflow_key")
        if workflow_key == "sifang_lianxu":
            return self._build_seamless_inputs(inputs, context)
        if workflow_key == "yinhua_tiqu":
            return self._build_pattern_extract_inputs(inputs, context, workflow_definition)
        if workflow_key == "huawen_kuotu":
            return self._build_pattern_expand_inputs(inputs, context, workflow_definition)
        if workflow_key == "jisu_chuli":
            return self._build_jisu_chuli_inputs(inputs, context, workflow_definition)
        if workflow_key == "zhongsu_tisheng":
            return self._build_jisu_chuli_inputs(inputs, context, workflow_definition)
        return None, None

    def _looks_like_node_overrides(self, payload: dict[str, Any]) -> bool:
        try:
            return all(str(key).isdigit() and isinstance(value, dict) for key, value in payload.items())
        except AttributeError:
            return False

    def _build_seamless_inputs(
        self, params: dict[str, Any], context: ExecutionContext
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, base64_data = self._resolve_image_source(params, context)
        if not image_url and not base64_data:
            return None, "COMFYUI_IMAGE_REQUIRED"
        if image_url:
            overrides["96"] = {"url": image_url}
        if base64_data:
            overrides.setdefault("104", {})["base64_data"] = base64_data

        prompt = self._as_text(params.get("prompt") or params.get("description"))
        if prompt:
            overrides.setdefault("42", {})["string_a"] = prompt

        pattern_type = self._as_text(params.get("patternType") or params.get("pattern_type"))
        if pattern_type:
            overrides.setdefault("97", {})["boolean"] = pattern_type.lower() != "twoway"

        width = self._coerce_positive_int(params.get("width"))
        height = self._coerce_positive_int(params.get("height"))
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["102"] = node_inputs

        return (overrides or None), None

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
        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["400"] = node_inputs

        batch_count = self._coerce_positive_int(
            params.get("batch_count") or params.get("batchCount") or params.get("repeat_count")
        )
        if batch_count:
            overrides.setdefault("424", {})["amount"] = batch_count
            base_timeout = self._coerce_positive_int(workflow_definition.get("timeout")) or 180
            effective_timeout = max(base_timeout, int(base_timeout * batch_count * 1.2))
            workflow_definition["timeout"] = effective_timeout

        lora_name = self._as_text(params.get("lora_name") or params.get("loraName"))
        if lora_name:
            overrides.setdefault("390", {})["lora_name"] = lora_name

        return (overrides or None), None

    def _build_pattern_expand_inputs(
        self, params: dict[str, Any], context: ExecutionContext, workflow_definition: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        overrides: dict[str, dict[str, Any]] = {}
        image_url, _ = self._resolve_image_source(params, context)
        if not image_url:
            return None, "COMFYUI_IMAGE_REQUIRED"
        overrides["205"] = {"url": image_url}

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

        batch = self._coerce_positive_int(params.get("batch") or params.get("amount") or params.get("n"))
        if batch:
            overrides.setdefault("434", {})["amount"] = batch

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

        if width or height:
            node_inputs: dict[str, Any] = {}
            if width:
                node_inputs["width"] = width
            if height:
                node_inputs["height"] = height
            overrides["433"] = node_inputs

        return (overrides or None), None

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

        if image_url and not image_base64:
            fetched = self._download_base64(image_url)
            if fetched:
                image_base64 = fetched

        return image_url, image_base64

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

    def _download_base64(self, url: str) -> str | None:
        try:
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._logger.warning("Failed to fetch image for base64 fallback: %s", exc)
            return None
        return base64.b64encode(response.content).decode("ascii")

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
