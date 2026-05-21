"""Admin integration testing utilities."""

from __future__ import annotations

import logging
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any
from types import SimpleNamespace
from uuid import uuid4
from io import BytesIO

import httpx
from fastapi import HTTPException
from PIL import Image
from sqlalchemy import select

from app.constants.abilities import BAIDU_IMAGE_ABILITIES
from app.core.config import get_settings
from app.core.db import get_session
from app.models.integration import Ability, AbilityTask, ApiKey, Executor, Workflow, WorkflowBinding
from app.services.api_key_selector import bump_usage, mark_cooldown, pick_executor_api_key, pick_provider_api_key
from app.services.comfyui_graph import normalize_comfyui_prompt_graph
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

    def _find_comfyui_workflow(self, workflow_key: str) -> Workflow | None:
        key = str(workflow_key or "").strip()
        if not key:
            return None
        try:
            with get_session() as session:
                rows = session.execute(select(Workflow)).scalars().all()
        except Exception:
            return None
        for wf in rows:
            meta = wf.extra_metadata or {}
            meta_key = str(meta.get("workflow_key") or "").strip()
            if meta_key == key:
                return wf
            if wf.id == key:
                return wf
            if wf.action == key:
                return wf
        return None

    def _get_comfyui_workflow_metadata(self, workflow_key: str) -> dict[str, Any]:
        record = self._find_comfyui_workflow(workflow_key)
        if record and isinstance(record.extra_metadata, dict):
            return record.extra_metadata
        return {}

    @staticmethod
    def _normalize_comfyui_graph(definition: dict[str, Any] | None) -> dict[str, Any]:
        return normalize_comfyui_prompt_graph(definition)

    def _get_comfyui_workflow_graph(self, workflow_key: str) -> dict[str, Any]:
        record = self._find_comfyui_workflow(workflow_key)
        if record and isinstance(record.definition, dict) and record.definition:
            graph = self._normalize_comfyui_graph(record.definition)
            if graph:
                return graph
        return load_comfy_workflow(workflow_key)

    @staticmethod
    def _base_url_for_executor(executor: Executor) -> str:
        config = executor.config or {}
        base_url = (
            executor.base_url
            or config.get("baseUrl")
            or config.get("base_url")
            or ""
        ).rstrip("/")
        return base_url

    def _fetch_comfyui_object_info(self, executor: Executor, *, timeout_seconds: float = 8.0) -> tuple[str, dict[str, Any]]:
        base_url = self._base_url_for_executor(executor)
        if not base_url:
            raise HTTPException(status_code=400, detail="COMFYUI_BASE_URL_MISSING")
        try:
            timeout = httpx.Timeout(timeout_seconds, connect=min(2.0, timeout_seconds))
            response = httpx.get(f"{base_url}/object_info", timeout=timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to fetch ComfyUI object info: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_OBJECT_INFO_ERROR") from exc
        data = response.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="COMFYUI_OBJECT_INFO_INVALID")
        return base_url, data

    @staticmethod
    def _is_comfyui_resource_choice_input(class_type: str, input_name: str) -> bool:
        """Only model-like finite choices should block release compatibility.

        ComfyUI also exposes runtime choices such as input image filenames or
        method selectors. Those values are patched per request and must not be
        reported as missing model files.
        """

        name = str(input_name or "").strip().lower()
        if not name:
            return False
        ignored_exact = {
            "image",
            "images",
            "mask",
            "file",
            "filename",
            "input_image",
            "image_name",
            "image_path",
            "upload",
            "method",
            "mode",
            "select",
            "option",
            "preset",
        }
        if name in ignored_exact:
            return False
        resource_hints = (
            "ckpt",
            "checkpoint",
            "model",
            "lora",
            "loras",
            "unet",
            "clip",
            "vae",
            "controlnet",
            "control_net",
            "ipadapter",
            "ip_adapter",
            "sam",
            "grounding",
            "upscale",
            "embedding",
            "insightface",
            "instantid",
        )
        if any(hint in name for hint in resource_hints):
            return True
        class_key = str(class_type or "").strip().lower()
        return "loader" in class_key and any(hint in class_key for hint in resource_hints)

    @classmethod
    def _extract_comfyui_choice_inputs(cls, class_type: str, class_info: dict[str, Any] | None) -> dict[str, list[str]]:
        """Return object_info inputs that expose a finite filename/model choice list."""

        if not isinstance(class_info, dict):
            return {}
        raw_input = class_info.get("input")
        if not isinstance(raw_input, dict):
            return {}
        choices: dict[str, list[str]] = {}
        for section_name in ("required", "optional"):
            section = raw_input.get(section_name)
            if not isinstance(section, dict):
                continue
            for input_name, descriptor in section.items():
                if not isinstance(input_name, str):
                    continue
                if not cls._is_comfyui_resource_choice_input(class_type, input_name):
                    continue
                options: Any | None = None
                if isinstance(descriptor, (list, tuple)) and descriptor:
                    options = descriptor[0]
                if not isinstance(options, (list, tuple)):
                    continue
                values = [str(item) for item in options if isinstance(item, str) and item.strip()]
                if values:
                    choices[input_name] = values
        return choices

    @classmethod
    def _build_comfyui_object_info_index(cls, object_info: dict[str, Any]) -> dict[str, Any]:
        """Precompute the expensive parts of a ComfyUI object_info payload.

        Production object_info responses can be large. Building finite model
        choice lists for every workflow node repeatedly makes release checks
        slow and can exceed the smoke-test timeout.
        """

        node_keys: set[str] = {str(key) for key in object_info.keys() if isinstance(key, str)}
        choice_inputs: dict[str, dict[str, set[str]]] = {}
        for class_type in node_keys:
            raw_choices = cls._extract_comfyui_choice_inputs(class_type, object_info.get(class_type))
            if not raw_choices:
                continue
            choice_inputs[class_type] = {
                input_name: set(values)
                for input_name, values in raw_choices.items()
                if values
            }
        return {"nodeKeys": node_keys, "choiceInputs": choice_inputs}

    @staticmethod
    def _extract_comfyui_workflow_requirements(graph: dict[str, Any]) -> dict[str, Any]:
        nodes: list[dict[str, str]] = []
        for node_id, node in sorted(graph.items(), key=lambda item: str(item[0])):
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type") or "").strip()
            if not class_type:
                continue
            nodes.append({"nodeId": str(node_id), "classType": class_type})
        return {"nodes": nodes, "nodeKeys": sorted({node["classType"] for node in nodes})}

    @classmethod
    def _check_comfyui_graph_compatibility(
        cls,
        graph: dict[str, Any],
        object_info: dict[str, Any],
    ) -> dict[str, Any]:
        return cls._check_comfyui_graph_compatibility_with_index(
            graph,
            cls._build_comfyui_object_info_index(object_info),
        )

    @classmethod
    def _check_comfyui_graph_compatibility_with_index(
        cls,
        graph: dict[str, Any],
        object_info_index: dict[str, Any],
    ) -> dict[str, Any]:
        missing_nodes: list[dict[str, str]] = []
        missing_models: list[dict[str, str]] = []
        object_node_keys = object_info_index.get("nodeKeys")
        if not isinstance(object_node_keys, set):
            object_node_keys = set(object_node_keys or [])
        choice_inputs_by_class = object_info_index.get("choiceInputs")
        if not isinstance(choice_inputs_by_class, dict):
            choice_inputs_by_class = {}

        for node_id, node in sorted(graph.items(), key=lambda item: str(item[0])):
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("class_type") or "").strip()
            if not class_type:
                continue
            if class_type not in object_node_keys:
                missing_nodes.append({"nodeId": str(node_id), "classType": class_type})
                continue

            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            choice_inputs = choice_inputs_by_class.get(class_type)
            if not choice_inputs:
                continue
            for input_name, value in inputs.items():
                if input_name not in choice_inputs or not isinstance(value, str) or not value.strip():
                    continue
                allowed_values = choice_inputs[input_name]
                if value in allowed_values:
                    continue
                missing_models.append(
                    {
                        "nodeId": str(node_id),
                        "classType": class_type,
                        "inputName": str(input_name),
                        "value": value,
                    }
                )

        return {
            "compatible": not missing_nodes and not missing_models,
            "missingNodes": missing_nodes,
            "missingModels": missing_models,
        }

    @staticmethod
    def _normalize_executor_id_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw_items = value.replace(";", ",").split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raw_items = [value]
        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def get_comfyui_workflow_compatibility(
        self,
        *,
        executor_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Check whether active ComfyUI abilities can run on their routed executors."""

        with get_session() as session:
            ability_rows = (
                session.execute(
                    select(Ability).where(Ability.status == "active", Ability.provider == "comfyui")
                    .order_by(Ability.id.asc())
                )
                .scalars()
                .all()
            )
            workflow_rows = session.execute(select(Workflow).where(Workflow.type == "comfyui")).scalars().all()
            binding_rows = (
                session.execute(select(WorkflowBinding).where(WorkflowBinding.enabled.is_(True))).scalars().all()
            )
            executor_query = select(Executor).where(Executor.status == "active", Executor.type == "comfyui")
            if executor_ids:
                executor_query = executor_query.where(Executor.id.in_(executor_ids))
            executor_rows = session.execute(executor_query.order_by(Executor.id.asc())).scalars().all()

        workflow_by_id = {workflow.id: workflow for workflow in workflow_rows}
        workflow_by_key: dict[str, Workflow] = {}
        for workflow in workflow_rows:
            meta = workflow.extra_metadata if isinstance(workflow.extra_metadata, dict) else {}
            definition = workflow.definition if isinstance(workflow.definition, dict) else {}
            for key in (
                workflow.id,
                workflow.action,
                meta.get("workflow_key"),
                definition.get("workflow_key"),
            ):
                normalized = str(key or "").strip()
                if normalized:
                    workflow_by_key[normalized] = workflow

        binding_ids_by_workflow: dict[str, list[str]] = {}
        for binding in binding_rows:
            if not binding.workflow_id or not binding.executor_id:
                continue
            ids = binding_ids_by_workflow.setdefault(binding.workflow_id, [])
            if binding.executor_id not in ids:
                ids.append(binding.executor_id)

        object_info_index_by_executor: dict[str, dict[str, Any] | None] = {}
        server_payloads: list[dict[str, Any]] = []
        active_executor_ids = [executor.id for executor in executor_rows]

        def fetch_executor_object_info(executor: Executor) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
            base_url = self._base_url_for_executor(executor)
            try:
                # Some production nodes return a large object_info payload. Four seconds is
                # too aggressive and causes false "node unavailable" warnings during release checks.
                fetched_base_url, object_info = self._fetch_comfyui_object_info(executor, timeout_seconds=20.0)
                return (
                    executor.id,
                    object_info,
                    {
                        "executorId": executor.id,
                        "executorName": executor.name,
                        "baseUrl": fetched_base_url,
                        "status": executor.status,
                        "reachable": True,
                        "nodeCount": len(object_info),
                        "message": None,
                    },
                )
            except HTTPException as exc:
                return (
                    executor.id,
                    None,
                    {
                        "executorId": executor.id,
                        "executorName": executor.name,
                        "baseUrl": base_url,
                        "status": executor.status,
                        "reachable": False,
                        "nodeCount": None,
                        "message": str(exc.detail),
                    },
                )

        if executor_rows:
            with ThreadPoolExecutor(max_workers=min(8, len(executor_rows))) as pool:
                for executor_id, object_info, payload in pool.map(fetch_executor_object_info, executor_rows):
                    object_info_index_by_executor[executor_id] = (
                        self._build_comfyui_object_info_index(object_info)
                        if object_info is not None
                        else None
                    )
                    server_payloads.append(payload)
            executor_order = {executor_id: index for index, executor_id in enumerate(active_executor_ids)}
            server_payloads.sort(key=lambda item: executor_order.get(str(item.get("executorId") or ""), 9999))

        workflow_payloads: list[dict[str, Any]] = []
        ok_count = warning_count = failed_count = 0
        for ability in ability_rows:
            metadata = ability.extra_metadata if isinstance(ability.extra_metadata, dict) else {}
            defaults = ability.default_params if isinstance(ability.default_params, dict) else {}
            workflow_key = (
                str(metadata.get("workflow_key") or defaults.get("workflow_key") or ability.capability_key or "").strip()
            )
            workflow = workflow_by_key.get(workflow_key)
            if workflow and isinstance(workflow.definition, dict):
                graph = self._normalize_comfyui_graph(workflow.definition)
            else:
                graph = {}
            if not graph and workflow_key:
                try:
                    graph = load_comfy_workflow(workflow_key)
                except Exception:
                    graph = {}

            diagnostics: list[dict[str, str]] = []
            if not graph:
                diagnostics.append(
                    {
                        "level": "critical",
                        "code": "COMFYUI_WORKFLOW_GRAPH_MISSING",
                        "message": "该能力没有可检查的 ComfyUI 工作流图，无法确认节点和模型依赖。",
                    }
                )

            allowed_ids = self._normalize_executor_id_list(metadata.get("allowed_executor_ids"))
            workflow_id = workflow.id if workflow else None
            binding_ids = binding_ids_by_workflow.get(workflow_id or "", [])
            expected_ids = allowed_ids or binding_ids or active_executor_ids
            if executor_ids:
                selected = set(executor_ids)
                expected_ids = [executor_id for executor_id in expected_ids if executor_id in selected]

            requirements = self._extract_comfyui_workflow_requirements(graph)
            server_checks: list[dict[str, Any]] = []
            compatible_ids: list[str] = []
            incompatible_ids: list[str] = []
            for executor_id in expected_ids:
                executor_info_index = object_info_index_by_executor.get(executor_id)
                if executor_info_index is None:
                    server_checks.append(
                        {
                            "executorId": executor_id,
                            "compatible": False,
                            "reachable": False,
                            "missingNodes": [],
                            "missingModels": [],
                            "message": "执行节点不可访问或 object_info 读取失败",
                        }
                    )
                    incompatible_ids.append(executor_id)
                    continue
                check = self._check_comfyui_graph_compatibility_with_index(graph, executor_info_index)
                server_checks.append(
                    {
                        "executorId": executor_id,
                        "compatible": check["compatible"],
                        "reachable": True,
                        "missingNodes": check["missingNodes"],
                        "missingModels": check["missingModels"],
                        "message": None if check["compatible"] else "缺少工作流依赖",
                    }
                )
                if check["compatible"]:
                    compatible_ids.append(executor_id)
                else:
                    incompatible_ids.append(executor_id)

            if allowed_ids and binding_ids:
                allowed_set = set(allowed_ids)
                binding_set = set(binding_ids)
                if allowed_set != binding_set:
                    diagnostics.append(
                        {
                            "level": "warning",
                            "code": "COMFYUI_ROUTING_BINDING_MISMATCH",
                            "message": "能力允许节点与工作流绑定节点不一致，后续应统一口径。",
                        }
                    )
            if not expected_ids:
                diagnostics.append(
                    {
                        "level": "critical",
                        "code": "COMFYUI_NO_ROUTED_EXECUTOR",
                        "message": "该能力没有可检查的执行节点。",
                    }
                )
            has_critical_diagnostic = any(item.get("level") == "critical" for item in diagnostics)
            if has_critical_diagnostic or (expected_ids and not compatible_ids):
                status = "failed"
                failed_count += 1
            elif incompatible_ids or diagnostics:
                status = "warning"
                warning_count += 1
            else:
                status = "ok"
                ok_count += 1

            workflow_payloads.append(
                {
                    "abilityId": ability.id,
                    "displayName": ability.display_name,
                    "capabilityKey": ability.capability_key,
                    "workflowKey": workflow_key,
                    "workflowId": workflow_id,
                    "action": metadata.get("action") or getattr(workflow, "action", None),
                    "allowedExecutorIds": allowed_ids,
                    "bindingExecutorIds": binding_ids,
                    "expectedExecutorIds": expected_ids,
                    "compatibleExecutorIds": compatible_ids,
                    "incompatibleExecutorIds": incompatible_ids,
                    "requiredNodeKeys": requirements["nodeKeys"],
                    "requiredNodeCount": len(requirements["nodes"]),
                    "status": status,
                    "diagnostics": diagnostics,
                    "servers": server_checks,
                }
            )

        return {
            "checkedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "totalWorkflows": len(workflow_payloads),
            "okCount": ok_count,
            "warningCount": warning_count,
            "failedCount": failed_count,
            "servers": server_payloads,
            "workflows": workflow_payloads,
        }

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
        desired_output_size: tuple[int, int] | None = None,
        call_back_url: str | None = None,
        extra_payload: dict[str, object] | None = None,
        # KIE "market" jobs are often slow (queue + generation). Empirically 50~80s is common.
        # Default to a longer timeout so sync tool calls can still return images.
        poll_timeout: float = 120.0,
        poll_interval: float = 2.5,
    ) -> dict[str, object]:
        executor = self._get_executor(executor_id)
        normalized_type = (executor.type or "").lower()
        if normalized_type not in {"kie", "kie-market", "kie_market"}:
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_KIE")

        # Normalize common field aliases for market models.
        # Flux-2 expects input_urls; some callers still pass image_urls.
        if isinstance(input_payload, dict):
            if "input_urls" not in input_payload and "image_urls" in input_payload:
                model_key = str(model or "").strip().lower()
                if "flux-2" in model_key:
                    input_payload["input_urls"] = input_payload.get("image_urls")

        # Keep a copy of user intent before we mutate `input_payload` for retries/fallbacks.
        # Some KIE models ignore or strictly validate these fields; we may post-process.
        desired_aspect_ratio = str((input_payload or {}).get("aspect_ratio") or "").strip()
        desired_resolution = str((input_payload or {}).get("resolution") or "").strip()

        exclude: set[str] = set()
        last_msg: str | None = None
        base_url = ""
        headers: dict[str, str] = {}
        task_id: str | None = None

        # We allow a few retries to handle:
        # - API key rate limit rotation
        # - KIE strict validation errors (e.g. aspect_ratio enum/required)
        for _attempt in range(3):
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
                # Transient network issues: retry with the same key first, then rotate if needed.
                last_msg = f"KIE_HTTP_ERROR: {exc}"
                time.sleep(0.8)
                continue
            try:
                data = response.json()
            except ValueError as exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=502, detail="KIE_RESPONSE_INVALID") from exc

            code = data.get("code")
            ok = (response.status_code < 400) and (code in (200, "200", None))
            if not ok:
                last_msg = str(data.get("msg") or data)
                # Some KIE models validate `aspect_ratio` against a strict enum and/or
                # require the field. Coze users may also pass values with whitespace.
                # For robustness, retry with conservative fallbacks.
                if isinstance(input_payload, dict) and "aspect_ratio" in last_msg:
                    current = input_payload.get("aspect_ratio")
                    current_norm = str(current).strip() if current is not None else ""
                    # If required, fill it (prefer "auto").
                    if "aspect_ratio is required" in last_msg:
                        if not current_norm:
                            input_payload["aspect_ratio"] = "auto"
                            continue
                    # If invalid enum, try "auto" then "1:1".
                    if "aspect_ratio is not within the range of allowed options" in last_msg:
                        if current_norm.lower() != "auto":
                            input_payload["aspect_ratio"] = "auto"
                            continue
                        input_payload["aspect_ratio"] = "1:1"
                        continue
                # Resolution required/enum errors (Flux-2 models are stricter here).
                if isinstance(input_payload, dict) and "resolution" in last_msg:
                    cur_res = input_payload.get("resolution")
                    cur_res_norm = str(cur_res).strip().upper() if cur_res is not None else ""
                    if "resolution is required" in last_msg:
                        if not cur_res_norm:
                            input_payload["resolution"] = "1K"
                            continue
                    if "resolution is not within the range of allowed options" in last_msg:
                        # Try conservative fallbacks.
                        if cur_res_norm != "1K":
                            input_payload["resolution"] = "1K"
                            continue
                        input_payload["resolution"] = "2K"
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
        interval = max(poll_interval, 0.6)
        last_status_error: str | None = None
        while time.monotonic() < deadline:
            try:
                detail_data = self._fetch_kie_task(base_url, headers, task_id)
                last_status_error = None
            except HTTPException as exc:
                # Status polling is best-effort: gateway errors/timeouts are common on the KIE side.
                # Do not fail the whole sync call unless we hit the overall timeout.
                last_status_error = str(exc.detail or "KIE_STATUS_ERROR")
                time.sleep(interval)
                interval = min(interval * 1.35, 8.0)
                continue
            state = self._extract_kie_state(detail_data)
            if state in {"success", "fail"}:
                break
            time.sleep(interval)
            interval = min(interval * 1.15, 6.0)
        if detail_data is None:
            # If polling never returned a payload, keep a small hint so callers can diagnose quickly.
            detail_data = {"detail": last_status_error or "KIE_STATUS_EMPTY"}
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

        def _resize_with_pad(im: Image.Image, *, target_w: int, target_h: int) -> Image.Image:
            """Fit inside target and pad (no crop) to avoid losing elements."""
            im = im.convert("RGBA")
            src_w, src_h = im.size
            if src_w <= 0 or src_h <= 0:
                return im
            scale = min(target_w / src_w, target_h / src_h)
            new_w = max(1, int(round(src_w * scale)))
            new_h = max(1, int(round(src_h * scale)))
            resized = im.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
            left = max(0, (target_w - new_w) // 2)
            top = max(0, (target_h - new_h) // 2)
            canvas.paste(resized, (left, top), resized)
            return canvas

        # KIE's image-to-image models sometimes ignore `aspect_ratio`/`resolution`.
        # To keep workflows predictable, we optionally enforce:
        # - user-provided aspect_ratio(+resolution) as a post-process (pad, no crop)
        # - "default to input image size" when desired_output_size is provided
        # This only applies when the caller explicitly sets aspect_ratio != auto.
        requested_ratio = desired_aspect_ratio
        requested_res = desired_resolution

        def _parse_ratio(value: str) -> tuple[int, int] | None:
            v = (value or "").strip().lower()
            if not v or v == "auto":
                return None
            if ":" in v:
                a, b = v.split(":", 1)
                try:
                    x = int(a.strip())
                    y = int(b.strip())
                    if x > 0 and y > 0:
                        return x, y
                except Exception:
                    return None
            return None

        def _res_px(value: str) -> int | None:
            v = (value or "").strip().upper()
            return {"1K": 1024, "2K": 2048, "4K": 4096}.get(v)

        ratio_pair = _parse_ratio(requested_ratio)
        res_px = _res_px(requested_res)
        enforced_assets: list[dict[str, object]] = []
        enforced_urls: list[str] | None = None

        # 1) Enforce aspect ratio (pad, no crop). Target size uses resolution when present,
        # otherwise uses output long edge as baseline.
        if ratio_pair and stored_urls:
            rx, ry = ratio_pair
            enforced_urls = []
            for idx, oss_url in enumerate(stored_urls):
                try:
                    resp = httpx.get(oss_url, timeout=60)
                    resp.raise_for_status()
                    im = Image.open(BytesIO(resp.content))
                    src_w, src_h = im.size
                    if src_w <= 0 or src_h <= 0:
                        raise ValueError("invalid image size")
                    long_edge = res_px or max(int(src_w), int(src_h))
                    if rx >= ry:
                        target_w = long_edge
                        target_h = max(64, int(round(long_edge * (ry / rx))))
                    else:
                        target_h = long_edge
                        target_w = max(64, int(round(long_edge * (rx / ry))))
                    out_im = _resize_with_pad(im, target_w=target_w, target_h=target_h)
                    buf = BytesIO()
                    out_im.save(buf, format="PNG")
                    upload = oss_service.upload_bytes(
                        user_id="admin-kie",
                        filename=f"{model}-{idx + 1}-{target_w}x{target_h}.png",
                        data=buf.getvalue(),
                        content_type="image/png",
                    )
                    enforced_url = str(upload.get("url"))
                    enforced_urls.append(enforced_url)
                    enforced_assets.append(
                        {
                            "sourceUrl": oss_url,
                            "ossUrl": enforced_url,
                            "ossKey": upload.get("objectKey"),
                            "contentType": "image/png",
                            "tag": "kie-market-enforced",
                        }
                    )
                except Exception as exc:
                    self._logger.warning("KIE postprocess aspect_ratio pad failed: %s", exc)
                    enforced_urls.append(oss_url)

        # 2) Enforce "default to input image size" (pad, no crop). This takes precedence.
        if desired_output_size and stored_urls:
            try:
                target_w, target_h = int(desired_output_size[0]), int(desired_output_size[1])
            except Exception:
                target_w, target_h = 0, 0
            if target_w > 0 and target_h > 0:
                base_urls = enforced_urls or stored_urls
                final_urls: list[str] = []
                for idx, oss_url in enumerate(base_urls):
                    try:
                        resp = httpx.get(oss_url, timeout=60)
                        resp.raise_for_status()
                        im = Image.open(BytesIO(resp.content))
                        out_im = _resize_with_pad(im, target_w=target_w, target_h=target_h)
                        buf = BytesIO()
                        out_im.save(buf, format="PNG")
                        upload = oss_service.upload_bytes(
                            user_id="admin-kie",
                            filename=f"{model}-{idx + 1}-target-{target_w}x{target_h}.png",
                            data=buf.getvalue(),
                            content_type="image/png",
                        )
                        final_url = str(upload.get("url"))
                        final_urls.append(final_url)
                        enforced_assets.append(
                            {
                                "sourceUrl": oss_url,
                                "ossUrl": final_url,
                                "ossKey": upload.get("objectKey"),
                                "contentType": "image/png",
                                "tag": "kie-market-target-size",
                            }
                        )
                    except Exception as exc:
                        self._logger.warning("KIE postprocess target size pad failed: %s", exc)
                        final_urls.append(oss_url)
                enforced_urls = final_urls

        if enforced_urls:
            stored_urls = enforced_urls
        if enforced_assets:
            stored_assets.extend(enforced_assets)

        base_meta = {
            "provider": "kie",
            "model": model,
            "taskId": task_id,
            "state": state or (record.get("state") if isinstance(record, dict) else None),
            "executorId": executor.id,
            "baseUrl": base_url,
            # Include request payload to diagnose field mapping issues.
            "raw": {"response": detail_data, "request": payload},
        }

        if state == "fail":
            return {
                **base_meta,
                "status": "failed",
                "resultUrls": stored_urls or result_urls,
                "resultObject": result_object,
                "storedAssets": stored_assets,
            }
        # If KIE has not finished yet (or returned no images), mark it as running so
        # downstream polling can finalize later via /tasks/get.
        if state != "success" or not (stored_urls or result_urls):
            return {
                **base_meta,
                "status": "running",
                "resultUrls": stored_urls or result_urls,
                "resultObject": result_object,
                "storedAssets": stored_assets,
            }
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
            "status": "succeeded",
            "executorId": executor.id,
            "baseUrl": base_url,
        }

    def fetch_kie_market_result(
        self, *, executor_id: str, task_id: str, timeout: float = 20.0, max_retries: int = 1
    ) -> dict[str, object]:
        executor = self._get_executor(executor_id)
        api_key = self._pick_kie_api_key(executor)
        if not api_key:
            raise HTTPException(status_code=400, detail="KIE_API_KEY_MISSING")
        base_url, headers = self._prepare_kie_client(executor, api_key=api_key)
        detail_data = self._fetch_kie_task(
            base_url, headers, task_id, timeout=timeout, max_retries=max_retries
        )
        state = self._extract_kie_state(detail_data)
        result_urls, result_object = self._parse_kie_result(detail_data)
        stored_assets: list[dict[str, object]] = []
        stored_urls: list[str] = []
        for index, remote_url in enumerate(result_urls or []):
            asset = self._store_remote_asset(
                remote_url,
                user_id="admin-kie",
                filename=f"kie-{task_id}-{index + 1}",
                tag="kie-market",
            )
            if asset:
                stored_assets.append(asset)
                if isinstance(asset.get("ossUrl"), str):
                    stored_urls.append(str(asset["ossUrl"]))
        return {
            "state": state,
            "resultUrls": stored_urls or result_urls,
            "storedAssets": stored_assets,
            "resultObject": result_object,
            "raw": {"response": detail_data},
            "executorId": executor.id,
            "baseUrl": base_url,
        }

    def _fetch_kie_task(
        self,
        base_url: str,
        headers: dict[str, str],
        task_id: str,
        *,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> dict:
        detail_url = f"{base_url}/api/v1/jobs/recordInfo"
        response = None
        # KIE status calls can occasionally spike in latency or return transient gateway errors.
        # Retry a few times so Coze workflows don't fail due to a single timeout.
        retries = max(1, int(max_retries))
        for attempt in range(retries):
            try:
                response = httpx.get(detail_url, headers=headers, params={"taskId": task_id}, timeout=timeout)
            except httpx.HTTPError as exc:  # pragma: no cover - defensive
                # Backoff and retry on transient network errors/timeouts.
                if attempt < retries - 1:
                    time.sleep(0.8 * (1.6**attempt))
                    continue
                raise HTTPException(status_code=502, detail=f"KIE_STATUS_HTTP_ERROR: {exc}") from exc

            # Treat upstream 5xx as transient; include snippet for diagnostics.
            if response.status_code >= 500:
                if attempt < retries - 1:
                    time.sleep(0.8 * (1.6**attempt))
                    continue
                snippet = ""
                try:
                    snippet = (response.text or "")[:300]
                except Exception:
                    snippet = ""
                raise HTTPException(
                    status_code=502,
                    detail=f"KIE_STATUS_HTTP_{response.status_code} body={snippet!r}",
                )
            break
        if response is None:  # pragma: no cover - defensive
            return {}
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
    def submit_comfyui_workflow(
        self,
        *,
        executor_id: str,
        workflow_key: str,
        workflow_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a ComfyUI prompt and return immediately (no polling).

        This is useful for long-running ComfyUI graphs where we don't want to block
        a worker thread until generation completes. Callers can later poll
        `/history/{prompt_id}` to fetch images.
        """
        executor = self._get_executor(executor_id)
        if (executor.type or "").lower() != "comfyui":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_COMFYUI")
        adapter = registry.get(executor.type)
        if adapter is None:
            raise HTTPException(status_code=500, detail="EXECUTOR_ADAPTER_MISSING")

        config = executor.config or {}
        base_url = (executor.base_url or config.get("baseUrl") or config.get("base_url") or "").rstrip("/")
        if not base_url:
            raise HTTPException(status_code=400, detail="COMFYUI_BASE_URL_MISSING")

        payload: dict[str, Any] = dict(workflow_params or {})
        workflow_definition = {
            "workflow_key": workflow_key,
            "graph": self._get_comfyui_workflow_graph(workflow_key),
        }
        workflow_meta = self._get_comfyui_workflow_metadata(workflow_key)
        workflow = SimpleNamespace(
            id=f"{workflow_key}_submit",
            definition=workflow_definition,
            extra_metadata={"workflow_key": workflow_key, **(workflow_meta or {})},
        )
        context = ExecutionContext(
            task=SimpleNamespace(id=f"submit-{uuid4().hex}", user_id="admin-comfyui", assets=[]),
            workflow=workflow,
            executor=executor,
            payload=payload,
            api_key=None,
        )

        # Reuse adapter's input-mapping and seed logic for consistency.
        graph_payload = workflow_definition.get("graph") or workflow_definition
        overrides, override_error = adapter._prepare_graph_inputs(context, workflow_definition)  # type: ignore[attr-defined]
        if override_error:
            raise HTTPException(status_code=400, detail=override_error)
        if overrides:
            from app.services.executors.comfyui import _apply_inputs

            _apply_inputs(graph_payload, overrides)
        # Keep consistent with adapter.execute: seamless workflow keeps node 104 as a
        # fixed mask input. Do not mutate/remove it here.
        adapter._ensure_sampler_seed(graph_payload, context.payload or {})  # type: ignore[attr-defined]

        prompt_id = uuid4().hex
        submission = {"prompt": graph_payload, "prompt_id": prompt_id}
        try:
            resp = httpx.post(f"{base_url}/prompt", json=submission, timeout=30)
            resp.raise_for_status()
            resp_json = resp.json()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to submit ComfyUI prompt: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_SUBMIT_ERROR") from exc

        node_errors = resp_json.get("node_errors") if isinstance(resp_json, dict) else None
        if isinstance(node_errors, dict) and node_errors:
            # Make this explicit; otherwise callers will poll forever.
            raise HTTPException(status_code=502, detail=f"COMFYUI_SUBMIT_NODE_ERROR:{list(node_errors.keys())[:5]}")

        result: dict[str, Any] = {
            "provider": "comfyui",
            "executorId": executor.id,
            "baseUrl": base_url,
            "workflowKey": workflow_key,
            "promptId": prompt_id,
            "raw": {"response": resp_json},
        }
        if isinstance(workflow_meta, dict):
            raw_ids = workflow_meta.get("output_node_ids") or workflow_meta.get("outputNodeIds")
            if isinstance(raw_ids, list):
                result["outputNodeIds"] = [str(x) for x in raw_ids if str(x).strip()]
        return result

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
            "graph": self._get_comfyui_workflow_graph(workflow_key),
        }
        workflow_meta = self._get_comfyui_workflow_metadata(workflow_key)
        if isinstance(timeout_value, (int, float)) and timeout_value > 0:
            workflow_definition["timeout"] = max(60, min(int(timeout_value), 900))
        workflow = SimpleNamespace(
            id=f"{workflow_key}_test",
            definition=workflow_definition,
            extra_metadata={"workflow_key": workflow_key, **(workflow_meta or {})},
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
        status = payload.get("status") or payload.get("state")
        if isinstance(status, str):
            status = status.strip().lower() or None
        # Include executor info to simplify debugging/routing validation.
        config = executor.config or {}
        base_url = (executor.base_url or config.get("baseUrl") or config.get("base_url") or "").rstrip("/")
        result: dict[str, Any] = {
            "provider": "comfyui",
            "executorId": executor.id,
            "baseUrl": base_url,
            "workflowKey": workflow_key,
            "promptId": payload.get("promptId") or payload.get("prompt_id") or "",
            "storedUrl": stored_url,
            "assets": assets,
            "raw": payload.get("raw"),
        }
        if status:
            result["status"] = status
            result["state"] = status
        if isinstance(workflow_meta, dict):
            raw_ids = workflow_meta.get("output_node_ids") or workflow_meta.get("outputNodeIds")
            if isinstance(raw_ids, list):
                result["outputNodeIds"] = [str(x) for x in raw_ids if str(x).strip()]
        return result

    def get_comfyui_model_catalog(self, *, executor_id: str, include_nodes: bool = False) -> dict[str, Any]:
        executor = self._get_executor(executor_id)
        if (executor.type or "").lower() != "comfyui":
            raise HTTPException(status_code=400, detail="EXECUTOR_TYPE_NOT_COMFYUI")
        base_url, data = self._fetch_comfyui_object_info(executor)

        catalog = {
            "unet": self._extract_comfy_choices(data, "UNETLoader", "unet_name"),
            "clip": self._extract_comfy_choices(data, "CLIPLoader", "clip_name"),
            "vae": self._extract_comfy_choices(data, "VAELoader", "vae_name"),
            "lora": self._extract_comfy_choices(data, "LoraLoaderModelOnly", "lora_name"),
        }
        result: dict[str, Any] = {
            "executorId": executor.id,
            "baseUrl": base_url,
            "models": catalog,
        }
        if include_nodes:
            node_keys = [str(key) for key in data.keys() if isinstance(key, str)]
            result["nodeKeys"] = sorted(node_keys)
            result["nodeCount"] = len(node_keys)
        return result

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
        base_url = base_url.rstrip("/")
        if base_url.endswith("/api"):
            root_url = base_url[: -len("/api")]
            urls = (
                f"{root_url}/queue/status",
                f"{base_url}/queue",
                f"{root_url}/queue",
            )
        else:
            urls = (
                f"{base_url}/queue/status",
                f"{base_url}/api/queue",
                f"{base_url}/queue",
            )
        last_unsupported: int | None = None
        payload: dict[str, Any] | None = None
        for url in urls:
            try:
                response = httpx.get(url, timeout=15)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in {404, 405}:
                    last_unsupported = status_code
                    continue
                self._logger.warning("Failed to fetch ComfyUI queue status: %s", exc)
                raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR") from exc
            except httpx.HTTPError as exc:
                self._logger.warning("Failed to fetch ComfyUI queue status: %s", exc)
                raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_ERROR") from exc
            data = response.json()
            if not isinstance(data, dict):
                raise HTTPException(status_code=502, detail="COMFYUI_QUEUE_STATUS_INVALID")
            payload = data
            break

        if payload is None:
            self._logger.warning("ComfyUI queue endpoint unsupported at %s", base_url)
            return {
                "executorId": executor.id,
                "baseUrl": base_url,
                "runningCount": 0,
                "pendingCount": 0,
                "queueMaxSize": None,
                "supported": False,
                "message": "当前 ComfyUI 版本未暴露 /api/queue 或 /queue/status，无法读取队列状态。",
                "raw": {"status_code": last_unsupported},
            }
        running_entries = payload.get("queue_running")
        pending_entries = payload.get("queue_pending")
        running_count = len(running_entries) if isinstance(running_entries, list) else 0
        pending_count = len(pending_entries) if isinstance(pending_entries, list) else 0
        queue_max_size = payload.get("queue_size_max") or payload.get("queue_max_size")
        try:
            max_size_value = int(queue_max_size) if queue_max_size is not None else None
        except (TypeError, ValueError):
            max_size_value = None
        if max_size_value is None:
            # Many ComfyUI builds do not expose an explicit queue max. Use the
            # platform executor cap so ops can still see the intended capacity.
            try:
                max_size_value = max(1, int(executor.max_concurrency or 0))
            except (TypeError, ValueError):
                max_size_value = None
        if max_size_value is None:
            try:
                max_size_value = max(1, int(get_settings().comfyui_queue_batch_size or 0))
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

    def get_comfyui_queue_summary(self, *, executor_ids: list[str] | None = None) -> dict[str, Any]:
        """Return queue counts for all active ComfyUI executors (optionally filtered)."""
        with get_session() as session:
            query = select(Executor).where(Executor.status == "active", Executor.type == "comfyui")
            if executor_ids:
                query = query.where(Executor.id.in_(executor_ids))
            executors = session.execute(query.order_by(Executor.id.asc())).scalars().all()
        # Hide mock/test executors from ops queue summary.
        executors = [
            ex
            for ex in executors
            if not str(ex.id or "").startswith("executor_mock_")
            and not bool((ex.config or {}).get("mock"))
        ]
        executor_ids = [executor.id for executor in executors]
        backend_tasks = self._summarize_backend_comfyui_tasks(executor_ids)
        route_evidence = self._summarize_recent_comfyui_route_evidence(executor_ids)

        servers: list[dict[str, Any]] = []
        total_running = 0
        total_pending = 0
        total_capacity = 0
        supported_servers = 0
        unsupported_servers = 0
        saturated_servers = 0
        idle_servers = 0
        feed_gap_servers = 0
        backend_blocked_servers = 0
        recent_route_missing_servers = 0
        diagnostics: list[dict[str, str]] = []
        for executor in executors:
            try:
                fallback_queue_max = max(1, int(executor.max_concurrency or 0))
            except (TypeError, ValueError):
                fallback_queue_max = max(1, int(get_settings().comfyui_queue_batch_size or 10))
            try:
                status = self.get_comfyui_queue_status(executor_id=executor.id)
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "COMFYUI_QUEUE_STATUS_ERROR"
                status = {
                    "executorId": executor.id,
                    "baseUrl": executor.base_url or (executor.config or {}).get("baseUrl") or (executor.config or {}).get("base_url") or "",
                    "runningCount": 0,
                    "pendingCount": 0,
                    "queueMaxSize": fallback_queue_max,
                    "supported": False,
                    "message": detail,
                    "raw": None,
                }
            else:
                # Queue payloads can be very large; summary should only expose counts.
                status["raw"] = None
            backend = backend_tasks.get(executor.id, {})
            evidence = route_evidence.get(executor.id, self._empty_comfyui_route_evidence())
            capacity = self._coerce_positive_int(status.get("queueMaxSize"), fallback=fallback_queue_max)
            running = int(status.get("runningCount") or 0)
            pending = int(status.get("pendingCount") or 0)
            remote_total = running + pending
            backend_queued = int(backend.get("queued") or 0)
            backend_running = int(backend.get("running") or 0)
            backend_active = backend_queued + backend_running
            idle_slots = max(0, capacity - remote_total)
            utilization = round(remote_total / capacity, 4) if capacity > 0 else None
            saturation = "full" if capacity > 0 and remote_total >= capacity else ("busy" if remote_total > 0 else "idle")
            diagnosis_level = "success"
            diagnosis = "节点可用，队列未满。"
            feed_code = "normal"
            feed_level = "success"
            feed_diagnosis = "中台与 ComfyUI 队列衔接正常。"
            route_diagnosis_level = "success"
            route_diagnosis = "最近真实任务已命中过该线路。"

            if status.get("supported") is not True:
                unsupported_servers += 1
                diagnosis_level = "danger"
                diagnosis = str(status.get("message") or "节点不可达或队列接口不可用。")
                feed_code = "executor_unavailable"
                feed_level = "danger"
                feed_diagnosis = "该节点当前不可用于路由，任务应自动避开。"
                route_diagnosis_level = "danger"
                route_diagnosis = "线路不可达，最近命中证据只能作为历史参考。"
            else:
                supported_servers += 1
                total_capacity += capacity
                if remote_total >= capacity:
                    saturated_servers += 1
                    diagnosis_level = "warning"
                    diagnosis = "ComfyUI 队列已接近或达到容量上限。"
                elif remote_total == 0:
                    idle_servers += 1
                if backend_running > 0 and remote_total == 0:
                    backend_blocked_servers += 1
                    feed_code = "backend_running_not_visible"
                    feed_level = "danger"
                    feed_diagnosis = "中台显示执行中，但 ComfyUI 队列没有对应任务，需检查下发或结果回填。"
                elif backend_queued > 0 and idle_slots > 0:
                    feed_gap_servers += 1
                    feed_code = "backend_queued_with_idle_capacity"
                    feed_level = "warning"
                    feed_diagnosis = "中台仍有待下发任务，但该节点还有空闲容量，需检查 worker 并发或调度节奏。"
                elif backend_active > capacity and remote_total < capacity:
                    feed_gap_servers += 1
                    feed_code = "backend_active_over_capacity"
                    feed_level = "warning"
                    feed_diagnosis = "中台侧任务数超过该节点容量，但 ComfyUI 未被填满，需检查任务衔接。"
                if int(evidence.get("recentTotal") or 0) <= 0:
                    recent_route_missing_servers += 1
                    route_diagnosis_level = "warning"
                    route_diagnosis = "近 24 小时没有真实任务命中该线路，需确认路由是否只打到另一台机器。"

            status.update(
                {
                    "executorName": executor.name,
                    "executorStatus": executor.status,
                    "maxConcurrency": int(executor.max_concurrency or 1),
                    "tags": executor.tags,
                    "totalCount": remote_total,
                    "capacityTarget": capacity,
                    "idleSlots": idle_slots if status.get("supported") is True else 0,
                    "utilization": utilization,
                    "saturation": saturation,
                    "diagnosisLevel": diagnosis_level,
                    "diagnosis": diagnosis,
                    "backendQueued": backend_queued,
                    "backendRunning": backend_running,
                    "backendActive": backend_active,
                    "backendOldestQueuedAt": backend.get("oldestQueuedAt"),
                    "backendOldestRunningAt": backend.get("oldestRunningAt"),
                    "feedCode": feed_code,
                    "feedDiagnosisLevel": feed_level,
                    "feedDiagnosis": feed_diagnosis,
                    "routeEvidence": evidence,
                    "routeDiagnosisLevel": route_diagnosis_level,
                    "routeDiagnosis": route_diagnosis,
                }
            )
            servers.append(status)
            if status.get("supported"):
                total_running += running
                total_pending += pending

        self._write_comfyui_queue_health(servers)
        total_count = total_running + total_pending
        total_idle_slots = max(0, total_capacity - total_count)
        utilization = round(total_count / total_capacity, 4) if total_capacity > 0 else None
        if unsupported_servers:
            diagnostics.append(
                {
                    "level": "danger",
                    "code": "COMFYUI_EXECUTOR_UNAVAILABLE",
                    "message": f"{unsupported_servers} 台 ComfyUI 节点不可达或队列接口不可用，路由会避开这些节点。",
                }
            )
        if backend_blocked_servers:
            diagnostics.append(
                {
                    "level": "danger",
                    "code": "COMFYUI_BACKEND_RUNNING_NOT_VISIBLE",
                    "message": f"{backend_blocked_servers} 台节点存在“中台执行中但 ComfyUI 队列为空”的情况，优先排查下发和回填。",
                }
            )
        if feed_gap_servers:
            diagnostics.append(
                {
                    "level": "warning",
                    "code": "COMFYUI_FEED_GAP",
                    "message": f"{feed_gap_servers} 台节点存在中台待下发但 GPU 未填满的情况，需检查 worker 并发和路由节奏。",
                }
            )
        route_evidence_total = sum(int(item.get("recentTotal") or 0) for item in route_evidence.values())
        route_evidence_covered = sum(1 for item in route_evidence.values() if int(item.get("recentTotal") or 0) > 0)
        if route_evidence_total > 0 and recent_route_missing_servers > 0:
            diagnostics.append(
                {
                    "level": "warning",
                    "code": "COMFYUI_ROUTE_EVIDENCE_MISSING",
                    "message": f"{recent_route_missing_servers} 台 ComfyUI 节点近 24 小时没有真实任务命中，需确认路由没有长期偏向单机。",
                }
            )
        if not executors:
            diagnostics.append(
                {
                    "level": "danger",
                    "code": "COMFYUI_EXECUTOR_EMPTY",
                    "message": "当前没有可用的 ComfyUI 执行节点，生图类业务无法承载。",
                }
            )
        return {
            "totalRunning": total_running,
            "totalPending": total_pending,
            "totalCount": total_count,
            "totalCapacity": total_capacity,
            "totalIdleSlots": total_idle_slots,
            "utilization": utilization,
            "backendQueuedTotal": sum(int(item.get("queued") or 0) for item in backend_tasks.values()),
            "backendRunningTotal": sum(int(item.get("running") or 0) for item in backend_tasks.values()),
            "backendActiveTotal": sum(int(item.get("queued") or 0) + int(item.get("running") or 0) for item in backend_tasks.values()),
            "supportedServers": supported_servers,
            "unsupportedServers": unsupported_servers,
            "saturatedServers": saturated_servers,
            "idleServers": idle_servers,
            "feedGapServers": feed_gap_servers,
            "backendBlockedServers": backend_blocked_servers,
            "routeEvidenceWindowHours": 24,
            "routeEvidenceTotal": route_evidence_total,
            "routeEvidenceCoveredServers": route_evidence_covered,
            "recentRouteMissingServers": recent_route_missing_servers,
            "diagnostics": diagnostics,
            "servers": servers,
        }

    @staticmethod
    def _coerce_positive_int(value: Any, *, fallback: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(fallback or 1)
        return max(1, parsed)

    def _summarize_backend_comfyui_tasks(self, executor_ids: list[str]) -> dict[str, dict[str, Any]]:
        executor_id_set = {str(item).strip() for item in executor_ids if str(item).strip()}
        summary: dict[str, dict[str, Any]] = {
            executor_id: {"queued": 0, "running": 0, "oldestQueuedAt": None, "oldestRunningAt": None}
            for executor_id in executor_id_set
        }
        if not executor_id_set:
            return summary
        try:
            with get_session() as session:
                rows = (
                    session.execute(
                        select(
                            AbilityTask.status,
                            AbilityTask.request_payload,
                            AbilityTask.created_at,
                            AbilityTask.started_at,
                        ).where(
                            AbilityTask.ability_provider == "comfyui",
                            AbilityTask.status.in_(["queued", "running"]),
                        )
                    )
                    .all()
                )
        except Exception as exc:  # pragma: no cover - diagnostic endpoint must degrade safely
            self._logger.warning("Failed to summarize backend ComfyUI tasks: %s", exc)
            return summary
        for status, request_payload, created_at, started_at in rows:
            payload = request_payload if isinstance(request_payload, dict) else {}
            executor_id = str(payload.get("executorId") or "").strip()
            if executor_id not in executor_id_set:
                continue
            bucket = summary.setdefault(
                executor_id,
                {"queued": 0, "running": 0, "oldestQueuedAt": None, "oldestRunningAt": None},
            )
            normalized_status = str(status or "").strip().lower()
            if normalized_status == "queued":
                bucket["queued"] = int(bucket.get("queued") or 0) + 1
                self._keep_oldest_iso(bucket, "oldestQueuedAt", created_at)
            elif normalized_status == "running":
                bucket["running"] = int(bucket.get("running") or 0) + 1
                self._keep_oldest_iso(bucket, "oldestRunningAt", started_at or created_at)
        return summary

    @staticmethod
    def _empty_comfyui_route_evidence() -> dict[str, Any]:
        return {
            "recentTotal": 0,
            "recentQueued": 0,
            "recentRunning": 0,
            "recentSucceeded": 0,
            "recentFailed": 0,
            "recentCancelled": 0,
            "recentOther": 0,
            "latestTaskId": None,
            "latestStatus": None,
            "latestTaskAt": None,
        }

    def _summarize_recent_comfyui_route_evidence(
        self,
        executor_ids: list[str],
        *,
        window_hours: int = 24,
    ) -> dict[str, dict[str, Any]]:
        executor_id_set = {str(item).strip() for item in executor_ids if str(item).strip()}
        summary = {executor_id: self._empty_comfyui_route_evidence() for executor_id in executor_id_set}
        if not executor_id_set:
            return summary
        since = datetime.utcnow() - timedelta(hours=max(1, int(window_hours or 24)))
        try:
            with get_session() as session:
                rows = (
                    session.execute(
                        select(
                            AbilityTask.id,
                            AbilityTask.status,
                            AbilityTask.request_payload,
                            AbilityTask.result_payload,
                            AbilityTask.created_at,
                            AbilityTask.updated_at,
                            AbilityTask.finished_at,
                        ).where(
                            AbilityTask.ability_provider == "comfyui",
                            AbilityTask.created_at >= since,
                        )
                    )
                    .all()
                )
        except Exception as exc:  # pragma: no cover - diagnostic endpoint must degrade safely
            self._logger.warning("Failed to summarize recent ComfyUI route evidence: %s", exc)
            return summary
        for task_id, status, request_payload, result_payload, created_at, updated_at, finished_at in rows:
            executor_id = self._extract_comfyui_route_executor_id(request_payload, result_payload)
            if executor_id not in executor_id_set:
                continue
            bucket = summary.setdefault(executor_id, self._empty_comfyui_route_evidence())
            normalized_status = str(status or "").strip().lower()
            bucket["recentTotal"] = int(bucket.get("recentTotal") or 0) + 1
            if normalized_status in {"queued", "pending"}:
                bucket["recentQueued"] = int(bucket.get("recentQueued") or 0) + 1
            elif normalized_status in {"running", "processing", "submitted"}:
                bucket["recentRunning"] = int(bucket.get("recentRunning") or 0) + 1
            elif normalized_status in {"succeeded", "success", "completed"}:
                bucket["recentSucceeded"] = int(bucket.get("recentSucceeded") or 0) + 1
            elif normalized_status in {"failed", "error", "timeout", "rejected"}:
                bucket["recentFailed"] = int(bucket.get("recentFailed") or 0) + 1
            elif normalized_status in {"cancelled", "canceled", "stopped", "aborted"}:
                bucket["recentCancelled"] = int(bucket.get("recentCancelled") or 0) + 1
            else:
                bucket["recentOther"] = int(bucket.get("recentOther") or 0) + 1
            latest_at = finished_at or updated_at or created_at
            if self._is_later_iso(latest_at, bucket.get("latestTaskAt")):
                bucket["latestTaskId"] = task_id
                bucket["latestStatus"] = normalized_status or status
                bucket["latestTaskAt"] = latest_at.isoformat() if isinstance(latest_at, datetime) else None
        return summary

    @staticmethod
    def _extract_comfyui_route_executor_id(
        request_payload: dict[str, Any] | None,
        result_payload: dict[str, Any] | None,
    ) -> str:
        candidates = []
        if isinstance(result_payload, dict):
            candidates.append(result_payload)
            meta = result_payload.get("metadata")
            if isinstance(meta, dict):
                candidates.append(meta)
        if isinstance(request_payload, dict):
            candidates.append(request_payload)
            meta = request_payload.get("metadata")
            if isinstance(meta, dict):
                candidates.append(meta)
        for payload in candidates:
            for key in ("executorId", "executor_id", "executor"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    @staticmethod
    def _is_later_iso(value: datetime | None, current_iso: Any) -> bool:
        if value is None:
            return False
        if not isinstance(current_iso, str) or not current_iso:
            return True
        try:
            current = datetime.fromisoformat(current_iso)
        except ValueError:
            return True
        return value > current

    @staticmethod
    def _keep_oldest_iso(bucket: dict[str, Any], key: str, value: datetime | None) -> None:
        if value is None:
            return
        current = bucket.get(key)
        if not isinstance(current, str) or not current:
            bucket[key] = value.isoformat()
            return
        try:
            current_dt = datetime.fromisoformat(current)
        except ValueError:
            bucket[key] = value.isoformat()
            return
        if value < current_dt:
            bucket[key] = value.isoformat()

    def _write_comfyui_queue_health(self, servers: list[dict[str, Any]]) -> None:
        """Persist lightweight executor health from queue checks.

        This deliberately does not mutate `status`; operators still decide
        whether an unreachable executor should be restored or taken offline.
        """
        if not servers:
            return
        now = datetime.utcnow()
        try:
            with get_session() as session:
                changed = False
                for item in servers:
                    if not isinstance(item, dict):
                        continue
                    executor_id = str(item.get("executorId") or "").strip()
                    if not executor_id:
                        continue
                    executor = session.get(Executor, executor_id)
                    if not executor:
                        continue
                    if item.get("supported") is True:
                        executor.health_status = "healthy"
                        executor.last_heartbeat_at = now
                        changed = True
                    elif item.get("supported") is False:
                        executor.health_status = "failed"
                        changed = True
                if changed:
                    session.commit()
        except Exception:
            self._logger.exception("Failed to persist ComfyUI executor queue health")

    def get_comfyui_system_stats(self, *, executor_id: str) -> dict[str, Any]:
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
            response = httpx.get(f"{base_url}/system_stats", timeout=15)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - defensive
            self._logger.warning("Failed to fetch ComfyUI system stats: %s", exc)
            raise HTTPException(status_code=502, detail="COMFYUI_SYSTEM_STATS_ERROR") from exc
        data = response.json()
        system = data.get("system") if isinstance(data, dict) else None
        devices = data.get("devices") if isinstance(data, dict) else None
        return {
            "executorId": executor.id,
            "baseUrl": base_url,
            "system": system if isinstance(system, dict) else None,
            "devices": devices if isinstance(devices, list) else None,
            "raw": data if isinstance(data, dict) else None,
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
