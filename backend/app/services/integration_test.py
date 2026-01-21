"""Admin integration testing utilities."""

from __future__ import annotations

import logging
import json
import time
from types import SimpleNamespace
from uuid import uuid4
from io import BytesIO

import httpx
from fastapi import HTTPException
from PIL import Image

from app.constants.abilities import BAIDU_IMAGE_ABILITIES
from app.core.db import get_session
from app.models.integration import ApiKey, Executor
from app.services.api_key_selector import bump_usage, mark_cooldown, pick_executor_api_key, pick_provider_api_key
from app.services.executors import ExecutionContext, registry
from app.services.media_ingest import media_ingest_service
from app.services.oss import oss_service
from app.workflows import load_comfy_workflow


class IntegrationTestService:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def _get_executor(self, executor_id: str) -> Executor:
        with get_session() as session:
            executor = session.get(Executor, executor_id)
            if not executor:
                raise HTTPException(status_code=404, detail="EXECUTOR_NOT_FOUND")
            # Preload api keys (otherwise lazy-loading after session closes will fail).
            _ = list(executor.api_keys)
            _ = list(executor.api_key_links)
            return executor

    def run_baidu_image_process(
        self,
        *,
        executor_id: str,
        operation: str,
        image_base64: str | None,
        image_url: str | None,
        params: dict | None = None,
    ) -> dict:
        executor = self._get_executor(executor_id)

        if executor.type != "baidu":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_BAIDU")

        adapter = registry.get(executor.type)
        if adapter is None:
            raise HTTPException(status_code=500, detail="EXECUTOR_ADAPTER_MISSING")
        if not image_base64 and not image_url:
            raise HTTPException(status_code=400, detail="IMAGE_REQUIRED")

        operation_conf = BAIDU_IMAGE_ABILITIES.get(operation)
        if not operation_conf:
            raise HTTPException(status_code=400, detail="UNSUPPORTED_OPERATION")
        endpoint = operation_conf["endpoint"]

        workflow_definition = {
            "endpoint": endpoint,
            "defaults": {**operation_conf.get("defaults", {}), **(params or {})},
        }
        payload: dict[str, str] = {}
        if image_base64:
            payload["image"] = image_base64
        elif image_url:
            payload["imageUrl"] = image_url

        context = ExecutionContext(
            task=SimpleNamespace(id=f"test-{uuid4().hex}", assets=[]),
            workflow=SimpleNamespace(
                id=f"baidu_{operation}_test",
                definition=workflow_definition,
            ),
            executor=executor,
            payload=payload,
            api_key=None,
        )
        result = adapter.execute(context)
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error_message or "BAIDU_TEST_FAILED")
        if not result.result_payload:
            raise HTTPException(status_code=502, detail="NO_RESULT_PAYLOAD")
        if not isinstance(result.result_payload, dict):
            return result.result_payload

        payload_dict = result.result_payload

        # Baidu returns base64 image; persist into OSS so Coze/our UI can preview via URL.
        result_image = payload_dict.get("resultImage")
        if isinstance(result_image, str) and result_image.startswith("data:image/") and ";base64," in result_image:
            b64 = result_image.split(";base64,", 1)[1].strip()
            asset = self._store_base64_asset(
                b64,
                user_id="admin-baidu",
                filename=f"baidu-{operation}-{uuid4().hex}.png",
                mime_type="image/png",
                tag="baidu-image",
            )
            if asset and isinstance(asset.get("ossUrl"), str):
                payload_dict["storedUrl"] = asset["ossUrl"]
                payload_dict["resultUrls"] = [asset["ossUrl"]]
                payload_dict["assets"] = [asset]

        # Add request context for debugging without leaking base64 payload.
        payload_dict["raw"] = {
            "response": payload_dict.get("raw"),
            "request": {
                "endpoint": endpoint,
                "operation": operation,
                "params": params or {},
                "imageUrl": image_url,
                "hasImageBase64": bool(image_base64),
            },
        }
        return payload_dict

    def run_baidu_quality_upgrade(
        self,
        *,
        executor_id: str,
        image_base64: str | None,
        image_url: str | None,
        resolution: str,
        upscale_type: str | None,
    ) -> dict:
        params = {
            "resolution": resolution or "2k",
            "type": upscale_type or "auto",
        }
        return self.run_baidu_image_process(
            executor_id=executor_id,
            operation="quality_upgrade",
            image_base64=image_base64,
            image_url=image_url,
            params=params,
        )

    # ----------------------- Volcengine helpers ----------------------- #
    def _pick_volc_api_key(self, executor: Executor, exclude_ids: set[str] | None = None) -> ApiKey | None:
        # Prefer keys bound in DB; fallback to legacy executor.config["apiKey"].
        exclude_ids = exclude_ids or set()
        with get_session() as session:
            api_key = pick_executor_api_key(
                session,
                executor_id=executor.id,
                provider="volcengine",
                exclude_ids=exclude_ids,
            )
            if api_key:
                return api_key
            # Internal fallback: if the executor isn't bound yet, use the global pool.
            api_key = pick_provider_api_key(session, provider="volcengine", exclude_ids=exclude_ids)
            if api_key:
                return api_key
        legacy = (executor.config or {}).get("apiKey")
        if legacy:
            return ApiKey(id="legacy", provider="volcengine", name="legacy", key=str(legacy), status="active")
        return None

    def _prepare_volc_request(
        self, executor: Executor, *, endpoint: str, api_key: ApiKey
    ) -> tuple[str, dict[str, str]]:
        config = executor.config or {}
        base_url = (config.get("baseUrl") or "https://ark.cn-beijing.volces.com").rstrip("/")
        url = f"{base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {api_key.key}",
            "Content-Type": "application/json",
        }
        return url, headers

    def run_volcengine_chat_completion(
        self,
        *,
        executor_id: str,
        model: str,
        prompt: str,
        image_url: str | None,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        executor = self._get_executor(executor_id)
        if executor.type != "volcengine":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_VOLCENGINE")
        exclude: set[str] = set()
        last_err: str | None = None
        for _attempt in range(2):
            api_key = self._pick_volc_api_key(executor, exclude_ids=exclude)
            if not api_key:
                raise HTTPException(status_code=400, detail="VOLCENGINE_API_KEY_MISSING")
            url, headers = self._prepare_volc_request(executor, endpoint="/api/v3/chat/completions", api_key=api_key)

            content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
            if image_url:
                content.insert(0, {"type": "image_url", "image_url": {"url": image_url}})
            payload: dict[str, object] = {
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
            }
            if params:
                payload.update(params)
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=60)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="VOLCENGINE_HTTP_ERROR") from exc
            data = response.json()
            if response.status_code >= 400:
                detail = data.get("error", {}).get("message") if isinstance(data, dict) else None
                last_err = str(detail or data)
                if response.status_code == 429 and api_key.id != "legacy":
                    with get_session() as session:
                        real_key = session.get(ApiKey, api_key.id)
                        if real_key:
                            mark_cooldown(session, api_key=real_key, seconds=120, reason="rate_limited")
                    exclude.add(api_key.id)
                    continue
                raise HTTPException(status_code=502, detail=detail or data)

            if api_key.id != "legacy":
                with get_session() as session:
                    real_key = session.get(ApiKey, api_key.id)
                    if real_key:
                        bump_usage(session, api_key=real_key)

            choices = data.get("choices") or []
            message_content = ""
            if choices:
                message = choices[0].get("message") or {}
                content_value = message.get("content")
                if isinstance(content_value, list):
                    message_content = " ".join(
                        part.get("text", "") for part in content_value if isinstance(part, dict)
                    ).strip()
                elif isinstance(content_value, str):
                    message_content = content_value
            return {
                "provider": "volcengine",
                "model": data.get("model") or model,
                "text": message_content or "(无返回文本)",
                "raw": data,
            }
        raise HTTPException(status_code=502, detail=last_err or "VOLCENGINE_REQUEST_FAILED")

    def run_volcengine_image_generation(
        self,
        *,
        executor_id: str,
        model: str,
        prompt: str,
        negative_prompt: str | None,
        size: str | None,
        response_format: str | None,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        executor = self._get_executor(executor_id)
        if executor.type != "volcengine":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_VOLCENGINE")
        exclude: set[str] = set()
        last_err: str | None = None
        for _attempt in range(2):
            api_key = self._pick_volc_api_key(executor, exclude_ids=exclude)
            if not api_key:
                raise HTTPException(status_code=400, detail="VOLCENGINE_API_KEY_MISSING")
            url, headers = self._prepare_volc_request(executor, endpoint="/api/v3/images/generations", api_key=api_key)

            payload: dict[str, object] = {
                "model": model,
                "prompt": prompt,
                "stream": False,
            }
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt
            if size:
                payload["size"] = size
            if response_format:
                payload["response_format"] = response_format
            if params:
                payload.update(params)

            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=120)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="VOLCENGINE_HTTP_ERROR") from exc
            data = response.json()
            if response.status_code >= 400:
                detail = data.get("error", {}).get("message") if isinstance(data, dict) else None
                last_err = str(detail or data)
                if response.status_code == 429 and api_key.id != "legacy":
                    with get_session() as session:
                        real_key = session.get(ApiKey, api_key.id)
                        if real_key:
                            mark_cooldown(session, api_key=real_key, seconds=120, reason="rate_limited")
                    exclude.add(api_key.id)
                    continue
                raise HTTPException(status_code=502, detail=detail or data)

            if api_key.id != "legacy":
                with get_session() as session:
                    real_key = session.get(ApiKey, api_key.id)
                    if real_key:
                        bump_usage(session, api_key=real_key)
            break
        else:
            raise HTTPException(status_code=502, detail=last_err or "VOLCENGINE_REQUEST_FAILED")
        data_records: list[dict] = []
        if isinstance(data, dict):
            recs = data.get("data") or []
            if isinstance(recs, list):
                data_records = [r for r in recs if isinstance(r, dict)]
        stored_assets: list[dict[str, object]] = []
        stored_urls: list[str] = []
        image_urls: list[str] = []
        image_b64_list: list[str] = []

        for idx, record in enumerate(data_records):
            if not isinstance(record, dict):
                continue
            image_url = record.get("url")
            image_b64 = record.get("b64_json")
            if isinstance(image_url, str) and image_url.strip():
                image_urls.append(image_url.strip())
                asset = self._store_remote_asset(
                    image_url.strip(),
                    user_id="admin-volcengine",
                    filename=f"{model}-{idx + 1}.png",
                    tag="volcengine-image",
                )
                if asset and isinstance(asset.get("ossUrl"), str):
                    stored_assets.append(asset)
                    stored_urls.append(str(asset["ossUrl"]))
            elif isinstance(image_b64, str) and image_b64.strip():
                image_b64_list.append(image_b64.strip())
                asset = self._store_base64_asset(
                    image_b64.strip(),
                    user_id="admin-volcengine",
                    filename=f"{model}-{idx + 1}.png",
                    mime_type="image/png",
                    tag="volcengine-image",
                )
                if asset and isinstance(asset.get("ossUrl"), str):
                    stored_assets.append(asset)
                    stored_urls.append(str(asset["ossUrl"]))

        # Optional: enforce exact output dimensions without distortion.
        # We "contain" scale (letterbox) into target size (keeps aspect ratio).
        width = payload.get("width")
        height = payload.get("height")
        try:
            target_w = int(width) if width is not None else None
        except (TypeError, ValueError):
            target_w = None
        try:
            target_h = int(height) if height is not None else None
        except (TypeError, ValueError):
            target_h = None
        if target_w and target_h and stored_assets:
            resized_assets: list[dict[str, object]] = []
            resized_urls: list[str] = []
            for idx, asset in enumerate(stored_assets):
                if not isinstance(asset, dict):
                    continue
                src = asset.get("ossUrl") or asset.get("url")
                if not isinstance(src, str) or not src:
                    continue
                try:
                    img_resp = httpx.get(src, timeout=60)
                    img_resp.raise_for_status()
                    im = Image.open(BytesIO(img_resp.content))
                    im = im.convert("RGBA")
                    src_w, src_h = im.size
                    scale = min(target_w / src_w, target_h / src_h)
                    new_w = max(1, int(round(src_w * scale)))
                    new_h = max(1, int(round(src_h * scale)))
                    resized = im.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
                    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
                    offset_x = (target_w - new_w) // 2
                    offset_y = (target_h - new_h) // 2
                    canvas.paste(resized, (offset_x, offset_y))
                    buf = BytesIO()
                    canvas.save(buf, format="PNG")
                    uploaded = oss_service.upload_bytes(
                        user_id="admin-volcengine",
                        filename=f"{model}-{idx + 1}-{target_w}x{target_h}.png",
                        data=buf.getvalue(),
                        content_type="image/png",
                    )
                    new_asset = {
                        "sourceUrl": src,
                        "ossUrl": uploaded.get("url"),
                        "ossKey": uploaded.get("objectKey"),
                        "contentType": "image/png",
                        "size": len(buf.getvalue()),
                        "tag": "volcengine-image-resized",
                    }
                    resized_assets.append(new_asset)
                    if isinstance(uploaded.get("url"), str):
                        resized_urls.append(str(uploaded["url"]))
                except Exception:
                    # If resizing fails, keep original asset.
                    resized_assets.append(asset)
                    if isinstance(asset.get("ossUrl"), str):
                        resized_urls.append(str(asset["ossUrl"]))
            if resized_urls:
                stored_assets = resized_assets
                stored_urls = resized_urls

        first_url = image_urls[0] if image_urls else None
        first_b64 = image_b64_list[0] if image_b64_list else None
        stored_url: str | None = stored_urls[0] if stored_urls else None
        return {
            "provider": "volcengine",
            "model": (data.get("model") if isinstance(data, dict) else None) or model,
            "imageUrl": first_url,
            "imageBase64": first_b64,
            "storedUrl": stored_url,
            # Prefer returning our own OSS URLs for multi-image outputs (preserve order).
            "resultUrls": stored_urls,
            "assets": stored_assets,
            # Include the request payload to help diagnose "image not applied / size ignored".
            # This contains no secrets (API key is in headers).
            "raw": {"response": data, "request": payload},
        }

    # ----------------------- KIE helpers ----------------------- #
    def _pick_kie_api_key(self, executor: Executor, exclude_ids: set[str] | None = None) -> ApiKey | None:
        exclude_ids = exclude_ids or set()
        with get_session() as session:
            api_key = pick_executor_api_key(
                session,
                executor_id=executor.id,
                provider="kie",
                exclude_ids=exclude_ids,
            )
            if api_key:
                return api_key
            api_key = pick_provider_api_key(session, provider="kie", exclude_ids=exclude_ids)
            if api_key:
                return api_key
        legacy = (executor.config or {}).get("apiKey") or (executor.config or {}).get("api_key")
        if legacy:
            return ApiKey(id="legacy", provider="kie", name="legacy", key=str(legacy), status="active")
        return None

    def _prepare_kie_client(self, executor: Executor, *, api_key: ApiKey) -> tuple[str, dict[str, str]]:
        config = executor.config or {}
        base_url = (config.get("baseUrl") or executor.base_url or "https://api.kie.ai").rstrip("/")
        headers = {
            "Authorization": f"Bearer {api_key.key}",
            "Content-Type": "application/json",
        }
        return base_url, headers

    def run_kie_market_task(
        self,
        *,
        executor_id: str,
        endpoint: str | None,
        model: str,
        input_payload: dict[str, object],
        input_array_target: str | None = None,
        call_back_url: str | None = None,
        extra_payload: dict[str, object] | None = None,
        poll_timeout: float = 75.0,
        poll_interval: float = 2.5,
    ) -> dict[str, object]:
        executor = self._get_executor(executor_id)
        normalized_type = (executor.type or "").lower()
        if normalized_type not in {"kie", "kie-market", "kie_market"}:
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_KIE")

        exclude: set[str] = set()
        last_msg: str | None = None
        base_url = ""
        headers: dict[str, str] = {}
        task_id: str | None = None

        for _attempt in range(2):
            api_key = self._pick_kie_api_key(executor, exclude_ids=exclude)
            if not api_key:
                raise HTTPException(status_code=400, detail="KIE_API_KEY_MISSING")
            base_url, headers = self._prepare_kie_client(executor, api_key=api_key)

            path = endpoint or "/api/v1/jobs/createTask"
            if not path.startswith("/"):
                path = f"/{path}"
            url = f"{base_url}{path}"

            # KIE pulls images from URL on their side. If Coze sends a URL that is not
            # publicly reachable (or requires cookies), KIE will fail with
            # "file type not supported". To make this robust, we ingest any input URLs
            # into our OSS first and send OSS URLs to KIE.
            if input_array_target:
                entries = input_payload.get(input_array_target)
                oss_urls: list[str] = []

                def _to_url_list(value: object) -> list[str]:
                    if isinstance(value, str) and value.strip():
                        return [value.strip()]
                    if isinstance(value, list):
                        out: list[str] = []
                        for item in value:
                            out.extend(_to_url_list(item))
                        return out
                    if isinstance(value, dict):
                        for key in ("url", "ossUrl", "sourceUrl"):
                            v = value.get(key)
                            if isinstance(v, str) and v.strip():
                                return [v.strip()]
                    return []

                raw_urls = _to_url_list(entries)
                for idx, raw_url in enumerate(raw_urls[:10]):
                    # Skip if it's already our OSS domain.
                    if "podi.oss-" in raw_url:
                        oss_urls.append(raw_url)
                        continue
                    try:
                        asset = self._store_remote_asset(
                            raw_url,
                            user_id="admin-kie-input",
                            # Do not force a suffix: KIE sometimes checks by extension and/or content-type.
                            # Let our ingest logic pick a matching suffix from the downloaded content-type.
                            filename=f"kie-input-{idx + 1}",
                            tag="kie-input",
                        )
                        if asset and isinstance(asset.get("ossUrl"), str):
                            oss_urls.append(str(asset["ossUrl"]))
                    except Exception:
                        # Fallback: keep original URL
                        oss_urls.append(raw_url)

                if oss_urls:
                    input_payload[input_array_target] = oss_urls if len(oss_urls) > 1 else [oss_urls[0]]

            payload: dict[str, object] = {"model": model, "input": input_payload}
            if call_back_url:
                payload["callBackUrl"] = call_back_url
            if extra_payload:
                payload.update(extra_payload)

            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=60)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="KIE_HTTP_ERROR") from exc
            try:
                data = response.json()
            except ValueError as exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=502, detail="KIE_RESPONSE_INVALID") from exc

            code = data.get("code")
            ok = (response.status_code < 400) and (code in (200, "200", None))
            if not ok:
                last_msg = str(data.get("msg") or data)
                # Some KIE models validate `aspect_ratio` against a strict enum and may
                # reject values that look valid to us (or include whitespace).
                # For robustness, retry once without aspect_ratio (provider default).
                if (
                    "aspect_ratio is not within the range of allowed options" in last_msg
                    and isinstance(input_payload, dict)
                    and "aspect_ratio" in input_payload
                    and _attempt == 0
                ):
                    input_payload.pop("aspect_ratio", None)
                    continue
                is_rate_limited = (response.status_code == 429) or (code in (429, "429"))
                if is_rate_limited and api_key.id != "legacy":
                    with get_session() as session:
                        real_key = session.get(ApiKey, api_key.id)
                        if real_key:
                            mark_cooldown(session, api_key=real_key, seconds=120, reason="rate_limited")
                    exclude.add(api_key.id)
                    continue
                raise HTTPException(status_code=502, detail=data.get("msg") or "KIE_TASK_CREATE_FAILED")

            task_id = ((data.get("data") or {}) or {}).get("taskId")
            if not task_id:
                raise HTTPException(status_code=502, detail="KIE_TASK_ID_MISSING")
            if api_key.id != "legacy":
                with get_session() as session:
                    real_key = session.get(ApiKey, api_key.id)
                    if real_key:
                        bump_usage(session, api_key=real_key)
            break

        if not task_id:
            raise HTTPException(status_code=502, detail=last_msg or "KIE_TASK_CREATE_FAILED")

        detail_data = None
        deadline = time.monotonic() + max(poll_timeout, 10)
        while time.monotonic() < deadline:
            detail_data = self._fetch_kie_task(base_url, headers, task_id)
            state = self._extract_kie_state(detail_data)
            if state in {"success", "fail"}:
                break
            time.sleep(poll_interval)
        if detail_data is None:
            detail_data = {}
        state = self._extract_kie_state(detail_data)
        result_urls, result_object = self._parse_kie_result(detail_data)
        stored_assets: list[dict[str, object]] = []
        stored_urls: list[str] = []
        for index, remote_url in enumerate(result_urls or []):
            asset = self._store_remote_asset(
                remote_url,
                user_id="admin-kie",
                # Do not force a suffix; keep content-type/extension consistent.
                filename=f"{model}-{index + 1}",
                tag="kie-market",
            )
            if asset:
                stored_assets.append(asset)
                if isinstance(asset.get("ossUrl"), str):
                    stored_urls.append(str(asset["ossUrl"]))
        record = detail_data.get("data") if isinstance(detail_data, dict) else {}
        return {
            "provider": "kie",
            "model": model,
            "taskId": task_id,
            "state": state or (record.get("state") if isinstance(record, dict) else None),
            # Prefer returning our own OSS URLs so downstream nodes are stable.
            "resultUrls": stored_urls or result_urls,
            "resultObject": result_object,
            "storedAssets": stored_assets,
            # Include request payload to diagnose field mapping issues.
            "raw": {"response": detail_data, "request": payload},
        }

    def _fetch_kie_task(self, base_url: str, headers: dict[str, str], task_id: str) -> dict:
        detail_url = f"{base_url}/api/v1/jobs/recordInfo"
        try:
            response = httpx.get(detail_url, headers=headers, params={"taskId": task_id}, timeout=30)
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=502, detail="KIE_STATUS_HTTP_ERROR") from exc
        try:
            return response.json()
        except ValueError:  # pragma: no cover - defensive
            return {}

    def _extract_kie_state(self, detail_data: dict | None) -> str | None:
        if not detail_data:
            return None
        record = detail_data.get("data")
        if isinstance(record, dict):
            state = record.get("state")
            if isinstance(state, str):
                return state
        return None

    def _parse_kie_result(self, detail_data: dict | None) -> tuple[list[str] | None, dict | None]:
        if not detail_data:
            return None, None
        record = detail_data.get("data")
        if not isinstance(record, dict):
            return None, None
        result_json = record.get("resultJson")
        parsed: dict | None = None
        if isinstance(result_json, str) and result_json.strip():
            try:
                payload = json.loads(result_json)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                parsed = payload
        elif isinstance(result_json, dict):
            parsed = result_json
        result_urls = None
        if parsed:
            urls = parsed.get("resultUrls")
            if isinstance(urls, list):
                result_urls = [str(item) for item in urls if isinstance(item, str)]
            elif isinstance(parsed.get("resultUrl"), str):
                result_urls = [str(parsed["resultUrl"])]
        return result_urls, parsed

    # ----------------------- ComfyUI helpers ----------------------- #
    def run_comfyui_workflow(
        self,
        *,
        executor_id: str,
        workflow_key: str,
        workflow_params: dict[str, Any],
    ) -> dict[str, Any]:
        executor = self._get_executor(executor_id)
        if (executor.type or "").lower() != "comfyui":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_COMFYUI")
        adapter = registry.get(executor.type)
        if adapter is None:
            raise HTTPException(status_code=500, detail="EXECUTOR_ADAPTER_MISSING")
        payload: dict[str, Any] = dict(workflow_params or {})
        timeout_value = payload.pop("timeout", None)
        workflow_definition = {
            "workflow_key": workflow_key,
            "graph": load_comfy_workflow(workflow_key),
        }
        if isinstance(timeout_value, (int, float)) and timeout_value > 0:
            workflow_definition["timeout"] = max(60, min(int(timeout_value), 900))
        workflow = SimpleNamespace(
            id=f"{workflow_key}_test",
            definition=workflow_definition,
            extra_metadata={"workflow_key": workflow_key},
        )
        context = ExecutionContext(
            task=SimpleNamespace(id=f"test-{uuid4().hex}", user_id="admin-comfyui", assets=[]),
            workflow=workflow,
            executor=executor,
            payload=payload,
            api_key=None,
        )
        result = adapter.execute(context)
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error_message or "COMFYUI_TEST_FAILED")
        payload = result.result_payload or {}
        assets = payload.get("assets")
        stored_url = None
        if isinstance(assets, list) and assets:
            first = assets[0] or {}
            stored_url = first.get("ossUrl") or first.get("url")
        return {
            "provider": "comfyui",
            "workflowKey": workflow_key,
            "promptId": payload.get("promptId") or payload.get("prompt_id") or "",
            "storedUrl": stored_url,
            "assets": assets,
            "raw": payload.get("raw"),
        }

    def get_comfyui_model_catalog(self, *, executor_id: str) -> dict[str, Any]:
        executor = self._get_executor(executor_id)
        if (executor.type or "").lower() != "comfyui":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_COMFYUI")
        config = executor.config or {}
        base_url = (
            executor.base_url
            or config.get("baseUrl")
            or config.get("base_url")
            or ""
        ).rstrip("/")
        if not base_url:
            raise HTTPException(status_code=400, detail="COMFYUI_BASE_URL_MISSING")
        try:
            response = httpx.get(f"{base_url}/object_info", timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to fetch ComfyUI object info: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_OBJECT_INFO_ERROR") from exc
        data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="COMFYUI_OBJECT_INFO_INVALID")

        catalog = {
            "unet": self._extract_comfy_choices(data, "UNETLoader", "unet_name"),
            "clip": self._extract_comfy_choices(data, "CLIPLoader", "clip_name"),
            "vae": self._extract_comfy_choices(data, "VAELoader", "vae_name"),
            "lora": self._extract_comfy_choices(data, "LoraLoaderModelOnly", "lora_name"),
        }
        return {
            "executorId": executor.id,
            "baseUrl": base_url,
            "models": catalog,
        }

    def get_comfyui_queue_status(self, *, executor_id: str) -> dict[str, Any]:
        executor = self._get_executor(executor_id)
        if (executor.type or "").lower() != "comfyui":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_COMFYUI")
        config = executor.config or {}
        base_url = (
            executor.base_url
            or config.get("baseUrl")
            or config.get("base_url")
            or ""
        ).rstrip("/")
        if not base_url:
            raise HTTPException(status_code=400, detail="COMFYUI_BASE_URL_MISSING")
        url = f"{base_url}/queue/status"
        try:
            response = httpx.get(url, timeout=15)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {404, 405}:
                self._logger.warning("ComfyUI queue endpoint unsupported at %s (status=%s)", url, status_code)
                return {
                    "executorId": executor.id,
                    "baseUrl": base_url,
                    "runningCount": 0,
                    "pendingCount": 0,
                    "queueMaxSize": None,
                    "supported": False,
                    "message": "当前 ComfyUI 版本未暴露 /queue/status，无法读取队列状态。",
                    "raw": {"status_code": status_code},
                }
            self._logger.warning("Failed to fetch ComfyUI queue status: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR") from exc
        except httpx.HTTPError as exc:
            self._logger.warning("Failed to fetch ComfyUI queue status: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR") from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_INVALID")
        running_entries = payload.get("queue_running")
        pending_entries = payload.get("queue_pending")
        running_count = len(running_entries) if isinstance(running_entries, list) else 0
        pending_count = len(pending_entries) if isinstance(pending_entries, list) else 0
        queue_max_size = payload.get("queue_size_max") or payload.get("queue_max_size")
        try:
            max_size_value = int(queue_max_size) if queue_max_size is not None else None
        except (TypeError, ValueError):
            max_size_value = None
        return {
            "executorId": executor.id,
            "baseUrl": base_url,
            "runningCount": running_count,
            "pendingCount": pending_count,
            "queueMaxSize": max_size_value,
            "supported": True,
            "raw": payload,
        }

    @staticmethod
    def _extract_comfy_choices(
        payload: dict[str, Any],
        node_key: str,
        field_name: str,
    ) -> list[str]:
        node = payload.get(node_key)
        if not isinstance(node, dict):
            return []
        inputs = node.get("input") or {}
        required = inputs.get("required") or {}
        value = required.get(field_name)
        if isinstance(value, list):
            first = value[0] if value else None
            if isinstance(first, list):
                return [str(item) for item in first if isinstance(item, str)]
            if all(isinstance(item, str) for item in value):
                return [str(item) for item in value]
        return []

    def _store_remote_asset(
        self,
        url: str,
        *,
        user_id: str,
        filename: str,
        tag: str,
    ) -> dict[str, object] | None:
        try:
            return media_ingest_service.ingest_from_remote_url(
                url,
                user_id=user_id,
                filename_hint=filename,
                tag=tag,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Store remote asset failed: %s", exc)
            return None

    def _store_base64_asset(
        self,
        payload: str,
        *,
        user_id: str,
        filename: str,
        mime_type: str,
        tag: str,
    ) -> dict[str, object] | None:
        try:
            return media_ingest_service.ingest_from_base64(
                payload,
                user_id=user_id,
                filename_hint=filename,
                mime_type=mime_type,
                tag=tag,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.warning("Store base64 asset failed: %s", exc)
            return None


integration_test_service = IntegrationTestService()
