"""Service for AI ability evaluation runs (Coze workflow -> optional PODI task polling)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.models.eval import EvalRun, EvalWorkflowVersion
from app.models.integration import AbilityTask
from app.services.ability_task_service import get_ability_task_service
from app.services.coze_client import coze_client
from app.services.task_id_codec import decode_task_id


_HEX_TASK_ID = re.compile(r"^[0-9a-f]{24,64}$")


class EvalService:
    """Persisted evaluation runs with background execution in a bounded thread pool."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        settings = get_settings()
        max_workers = max(1, int(getattr(settings, "eval_run_max_workers", 6)))
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        # Best-effort: never block API startup on evaluation bookkeeping.
        # (In reload mode, mapper initialization can be sensitive to import order.)
        try:
            self._resume_pending_runs()
        except Exception as exc:  # pragma: no cover - defensive startup guard
            self._logger.warning("EvalService resume skipped: %s", exc)

    def create_eval_run(
        self,
        *,
        workflow_version_id: str,
        dataset_item_id: str | None,
        input_oss_urls: list[str] | None,
        parameters: dict[str, Any] | None,
        created_by: str,
        db: Session,
    ) -> EvalRun:
        workflow_version = db.get(EvalWorkflowVersion, workflow_version_id)
        if not workflow_version:
            raise ValueError(f"Workflow version {workflow_version_id} not found")

        normalized_params = (parameters or {}).copy()
        urls = [u for u in (input_oss_urls or []) if isinstance(u, str) and u.strip()]
        if urls:
            # Keep the convention: single image input uses `url` (string).
            normalized_params.setdefault("url", urls[0])
            if len(urls) > 1:
                normalized_params.setdefault("urls", urls)
            # Compat for some Coze workflows that use different casing.
            for alias in ("Url", "URL"):
                normalized_params.setdefault(alias, urls[0])

        # Coze will hard-fail if a workflow declares required params but they're missing.
        # Some workflows require `prompt` even when we want "no prompt" behavior; use a
        # whitespace prompt to satisfy Coze validation while keeping semantics neutral.
        schema = workflow_version.parameters_schema or {}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if isinstance(fields, list):
            for f in fields:
                if not isinstance(f, dict):
                    continue
                if f.get("name") != "prompt" or not f.get("required"):
                    continue
                v = normalized_params.get("prompt")
                if v is None or (isinstance(v, str) and not v.strip()):
                    normalized_params["prompt"] = " "

        run = EvalRun(
            id=uuid4().hex,
            workflow_version_id=workflow_version_id,
            dataset_item_id=dataset_item_id,
            input_oss_urls_json=urls or None,
            parameters_json=normalized_params or None,
            status="queued",
            created_by=created_by,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        self._executor.submit(self._execute_run, run.id)
        return run

    @staticmethod
    def _workflow_expects_callback(output_schema: dict[str, Any] | list[Any] | str | None) -> bool:
        """Best-effort: infer whether a workflow returns a callback task id in `output`."""
        schema: dict[str, Any] | list[Any] | str = output_schema or {}
        if isinstance(schema, str):
            raw = schema.strip()
            if raw:
                try:
                    schema = json.loads(raw)
                except json.JSONDecodeError:
                    schema = {}
        if isinstance(schema, list):
            schema = {"fields": schema}
        fields = schema.get("fields") if isinstance(schema, dict) else None
        if not isinstance(fields, list):
            return False
        for f in fields:
            if not isinstance(f, dict) or f.get("name") != "output":
                continue
            desc = str(f.get("description") or "")
            if "task" in desc.lower() or "回调" in desc:
                return True
        return False

    @staticmethod
    def _pop_fanout_count(params: dict[str, Any]) -> int:
        """Extract internal fan-out count (裂变数量) from params.

        This is a PODI evaluation-only control parameter and should NOT be sent to Coze,
        because most workflows don't declare it in their schema.
        """

        for key in ("count", "generateCount", "variantCount", "n"):
            if key not in params:
                continue
            raw = params.pop(key, None)
            try:
                value = int(str(raw).strip())
            except Exception:
                value = 0
            if value > 0:
                return min(value, 20)  # safety cap
        return 1

    def list_eval_runs(
        self,
        *,
        db: Session,
        workflow_version_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[EvalRun]]:
        stmt = select(EvalRun)
        count_stmt = select(func.count()).select_from(EvalRun)
        if workflow_version_id:
            stmt = stmt.where(EvalRun.workflow_version_id == workflow_version_id)
            count_stmt = count_stmt.where(EvalRun.workflow_version_id == workflow_version_id)
        if status:
            stmt = stmt.where(EvalRun.status == status)
            count_stmt = count_stmt.where(EvalRun.status == status)

        total = int(db.execute(count_stmt).scalar_one())
        items = (
            db.execute(stmt.order_by(EvalRun.created_at.desc()).offset(offset).limit(limit))
            .scalars()
            .all()
        )
        return total, items

    def _resume_pending_runs(self) -> None:
        """On process boot, re-queue runs left in queued/running."""
        with get_session() as session:
            pending_ids = (
                session.execute(select(EvalRun.id).where(EvalRun.status.in_(["queued", "running"])))
                .scalars()
                .all()
            )
            if pending_ids:
                session.execute(
                    EvalRun.__table__.update()
                    .where(EvalRun.id.in_(pending_ids))
                    .values(status="queued")
                )
                session.commit()
        for run_id in pending_ids:
            self._executor.submit(self._execute_run, run_id)

    @staticmethod
    def _append_run_images(run_id: str, *, image_urls: list[str]) -> None:
        if not image_urls:
            return
        cleaned: list[str] = []
        for u in image_urls:
            if not isinstance(u, str):
                continue
            s = u.strip()
            if not s:
                continue
            cleaned.append(s)
        if not cleaned:
            return
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            cur = run.result_image_urls_json or []
            seen = set(cur)
            for u in cleaned:
                if u in seen:
                    continue
                cur.append(u)
                seen.add(u)
            run.result_image_urls_json = cur
            session.add(run)
            session.commit()

    def _execute_run(self, run_id: str) -> None:
        started = time.monotonic()
        settings = get_settings()
        # Avoid using ORM instances outside the session scope (commit expires attrs by default).
        workflow_id: str | None = None
        expects_callback = False
        run_parameters: dict[str, Any] = {}
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            if isinstance(run.parameters_json, dict):
                run_parameters = run.parameters_json.copy()
            workflow_version = session.get(EvalWorkflowVersion, run.workflow_version_id)
            if not workflow_version:
                run.status = "failed"
                run.error_message = "WORKFLOW_VERSION_NOT_FOUND"
                session.add(run)
                session.commit()
                return
            workflow_id = str(workflow_version.workflow_id)
            expects_callback = self._workflow_expects_callback(workflow_version.output_schema)
            run.status = "running"
            session.add(run)
            session.commit()

        try:
            # Execute the workflow (non-streaming). OpenAPI tokens are handled by coze_client.
            if not workflow_id:
                raise RuntimeError("WORKFLOW_ID_MISSING")

            # Fan-out (裂变数量): run the same workflow multiple times and aggregate images.
            # Note: `count` is an internal eval control param and is not sent to Coze.
            coze_params = run_parameters.copy()
            # UI uses `similarity`; Coze workflows expect legacy `bili`.
            if "bili" not in coze_params and "similarity" in coze_params:
                coze_params["bili"] = coze_params.get("similarity")
            coze_params.pop("similarity", None)
            # Some outpaint workflows expect capitalized `Url`.
            if workflow_id in {"7597723984687267840", "7598587935331450880"}:
                if "Url" not in coze_params and "url" in coze_params:
                    coze_params["Url"] = coze_params.get("url")
            fanout = self._pop_fanout_count(coze_params)
            if fanout > 1:
                # Stable default: allow forcing sequential fan-out (max_workers=1) to
                # reduce pressure on Coze/tools and avoid connection resets under load.
                max_workers = min(fanout, max(1, int(getattr(settings, "eval_fanout_max_workers", 1))))
                all_images: list[str] = []
                errors: list[str] = []
                last_debug_url: str | None = None
                last_execute_id: str | None = None

                if max_workers <= 1:
                    # Sequential fan-out (stable mode).
                    for _ in range(fanout):
                        imgs, err, execute_id, debug_url = self._run_coze_async_item(
                            workflow_id, coze_params, settings, expects_callback
                        )
                        if imgs:
                            all_images.extend(imgs)
                            self._append_run_images(run_id, image_urls=imgs)
                        if err:
                            errors.append(err)
                        if debug_url:
                            last_debug_url = debug_url
                        if execute_id:
                            last_execute_id = execute_id
                else:
                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        futures = [
                            pool.submit(
                                self._run_coze_async_item,
                                workflow_id,
                                coze_params,
                                settings,
                                expects_callback,
                            )
                            for _ in range(fanout)
                        ]
                        for fut in as_completed(futures):
                            imgs, err, execute_id, debug_url = fut.result()
                            if imgs:
                                all_images.extend(imgs)
                                self._append_run_images(run_id, image_urls=imgs)
                            if err:
                                errors.append(err)
                            if debug_url:
                                last_debug_url = debug_url
                            if execute_id:
                                last_execute_id = execute_id

                # De-dup while preserving order.
                seen: set[str] = set()
                dedup: list[str] = []
                for u in all_images:
                    if u in seen:
                        continue
                    seen.add(u)
                    dedup.append(u)

                with get_session() as session:
                    run = session.get(EvalRun, run_id)
                    if run:
                        run.coze_execute_id = last_execute_id or run.coze_execute_id
                        run.coze_debug_url = last_debug_url or run.coze_debug_url
                        session.add(run)
                        session.commit()

                if dedup:
                    warn = None
                    if errors:
                        warn = "FANOUT_PARTIAL_FAILED: " + " | ".join(errors[:5]) + (" ..." if len(errors) > 5 else "")
                    self._mark_succeeded(run_id, image_urls=dedup, output_json=None, started=started, error_message=warn)
                    return
                self._mark_failed(run_id, message=errors[0] if errors else "FANOUT_EMPTY", started=started)
                return

            # Primary path: sync run (lower overhead).
            # Fallback: if Coze blocks longer than our HTTP timeout (common for long-running
            # generation workflows), switch to async submit + run_history polling.
            try:
                response = coze_client.run_workflow(workflow_id=workflow_id, parameters=coze_params, is_async=False)
            except HTTPException as exc:
                detail = str(getattr(exc, "detail", "") or "")
                lowered = detail.lower()
                is_timeout = "coze_request_failed" in lowered and ("timed out" in lowered or "timeout" in lowered)
                if is_timeout:
                    imgs, err, execute_id, debug_url = self._run_coze_async_item(
                        workflow_id, coze_params, settings, expects_callback
                    )
                    with get_session() as session:
                        run = session.get(EvalRun, run_id)
                        if run:
                            run.coze_execute_id = execute_id or run.coze_execute_id
                            run.coze_debug_url = debug_url or run.coze_debug_url
                            session.add(run)
                            session.commit()
                    if imgs:
                        self._mark_succeeded(run_id, image_urls=imgs, output_json=None, started=started, error_message=None)
                    else:
                        self._mark_failed(run_id, message=err or "COZE_ASYNC_EMPTY", started=started)
                    return
                raise

            execute_id = response.get("execute_id")
            debug_url = response.get("debug_url")
            with get_session() as session:
                run = session.get(EvalRun, run_id)
                if not run:
                    return
                run.coze_execute_id = str(execute_id) if execute_id else None
                run.coze_debug_url = str(debug_url) if debug_url else None
                session.add(run)
                session.commit()

            # Coze can return HTTP 200 with a non-zero `code` (or BaseResp.StatusCode) for failures.
            base_resp = response.get("BaseResp") or {}
            status_code = base_resp.get("StatusCode")
            code = response.get("code")
            if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                msg = response.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"

                # Coze validates required parameters before running nodes. Some workflows
                # may mark common fields like height/width as required. If callers omit them
                # (or send empty), Coze returns code=4000 with a "Missing required parameters"
                # message. We apply a best-effort fallback and retry once so UI users don't
                # get stuck with a hard failure for "obvious defaults".
                if (
                    isinstance(code, int)
                    and code == 4000
                    and isinstance(msg, str)
                    and "Missing required parameters" in msg
                ):
                    patched = self._patch_missing_required_params(run_parameters, msg)
                    if patched:
                        response = coze_client.run_workflow(
                            workflow_id=workflow_id,
                            parameters=patched,
                            is_async=False,
                        )
                        base_resp = response.get("BaseResp") or {}
                        status_code = base_resp.get("StatusCode")
                        code = response.get("code")
                        if (isinstance(code, int) and code != 0) or (
                            isinstance(status_code, int) and status_code != 0
                        ):
                            msg = response.get("msg") or base_resp.get("StatusMessage") or "COZE_EXECUTION_FAILED"
                        else:
                            # Continue normal success path below.
                            execute_id = response.get("execute_id")
                            debug_url = response.get("debug_url")
                            with get_session() as session:
                                run = session.get(EvalRun, run_id)
                                if not run:
                                    return
                                run.coze_execute_id = str(execute_id) if execute_id else None
                                run.coze_debug_url = str(debug_url) if debug_url else None
                                session.add(run)
                                session.commit()

                # Still failed after optional patch+retry.
                self._mark_failed(
                    run_id,
                    message=f"COZE_FAILED code={code} statusCode={status_code} msg={msg} debugUrl={debug_url}",
                    started=started,
                )
                return

            parsed = self._parse_coze_payload(response)
            # Some Coze workflows return a structured error payload even with HTTP 200.
            if isinstance(parsed, dict):
                if isinstance(parsed.get("$error"), str) and parsed.get("$error"):
                    self._mark_failed(
                        run_id,
                        message=f"COZE_WORKFLOW_ERROR: {parsed.get('$error')}",
                        started=started,
                    )
                    return
                if isinstance(parsed.get("error_msg"), str) and parsed.get("error_msg"):
                    self._mark_failed(
                        run_id,
                        message=f"COZE_WORKFLOW_ERROR: {parsed.get('error_msg')}",
                        started=started,
                    )
                    return

            output = parsed.get("output")
            podi_task_id: str | None = None
            if expects_callback and isinstance(output, str) and output.strip():
                # Callback workflows are expected to return the task id in `output`,
                # which may not be a hex string (e.g. snowflake ids).
                podi_task_id = decode_task_id(output.strip())
            else:
                podi_task_id = decode_task_id(self._guess_podi_task_id(parsed, output))
            if podi_task_id:
                # Prefer PODI ability_tasks.
                with get_session() as session:
                    task_row = session.get(AbilityTask, podi_task_id)
                if task_row:
                    self._poll_ability_task(run_id=run_id, task_id=podi_task_id, started=started)
                    return
                # Fallback: if output is a raw ComfyUI id, resolve via a callback workflow.
                callback_wf = settings.coze_comfyui_callback_workflow_id
                if callback_wf:
                    with get_session() as session:
                        run = session.get(EvalRun, run_id)
                        if run:
                            run.podi_task_id = podi_task_id
                            session.add(run)
                            session.commit()
                    image_urls = self._poll_callback_images(
                        callback_workflow_id=callback_wf,
                        taskid=podi_task_id,
                    )
                    if image_urls:
                        self._mark_succeeded(run_id, image_urls=image_urls, started=started)
                        return
                    self._mark_failed(run_id, message="CALLBACK_IMAGES_EMPTY", started=started)
                    return

            image_urls = self._extract_image_urls(parsed)
            output_json = self._extract_output_json(parsed)
            # Callback workflows must eventually return a task id (then we resolve it to images).
            # If Coze returns an empty string while the job is still processing, we should not
            # silently mark success with empty outputs.
            if expects_callback and not image_urls:
                if not (isinstance(output, str) and output.strip()):
                    self._mark_failed(run_id, message="CALLBACK_OUTPUT_EMPTY", started=started)
                    return
            if expects_callback and not image_urls and isinstance(output, str) and output.strip():
                self._mark_failed(
                    run_id,
                    message=f"CALLBACK_TASK_NOT_RESOLVED output={output.strip()[:128]}",
                    started=started,
                )
                return
            self._mark_succeeded(run_id, image_urls=image_urls, output_json=output_json, started=started)
        except HTTPException as exc:
            self._mark_failed(run_id, message=str(exc.detail), started=started)
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_failed(run_id, message=str(exc), started=started)

    @staticmethod
    def _patch_missing_required_params(
        params: dict[str, Any],
        msg: str,
    ) -> dict[str, Any] | None:
        """Best-effort patch for Coze code=4000 missing required parameters.

        Coze error messages can look like:
          "Missing required parameters：'height'. ..."
        We parse the missing field name(s) and fill with safe defaults.
        """

        missing = set(re.findall(r"'([^']+)'", msg or ""))
        if not missing:
            return None

        patched = params.copy()
        changed = False
        for name in missing:
            if name in patched and patched[name] is not None and str(patched[name]).strip():
                continue
            key = str(name)
            # Common numeric-like fields: provide conservative defaults as strings.
            if key in {"height", "width"}:
                patched[key] = "1024"
                changed = True
                continue
            if key.startswith("expand_"):
                patched[key] = "0"
                changed = True
                continue
            if key in {"dpi", "pdi"}:
                patched[key] = "300"
                changed = True
                continue
            # Generic: provide a whitespace string so it is "present" and non-empty.
            patched[key] = " "
            changed = True

        return patched if changed else None

    def _run_coze_async_item(
        self,
        workflow_id: str,
        coze_params: dict[str, Any],
        settings: Any,
        expects_callback: bool,
    ) -> tuple[list[str], str | None, str | None, str | None]:
        """Submit+poll one Coze run via async mode; return resolved image URLs.

        Returns: (image_urls, error_message, execute_id, debug_url)
        """

        def _is_transient(msg: str) -> bool:
            lowered = (msg or "").lower()
            return any(
                key in lowered
                for key in (
                    "timeout",
                    "temporarily",
                    "rate",
                    "too many",
                    "bad gateway",
                    "gateway timeout",
                    "502",
                    "503",
                    "504",
                    "coze_invalid_response",
                )
            )

        params = coze_params.copy()
        execute_id: str | None = None
        debug_url: str | None = None

        # 1) Submit (async) with retry+backoff.
        last_err: str | None = None
        for attempt in range(3):
            try:
                resp = coze_client.run_workflow(workflow_id=workflow_id, parameters=params, is_async=True)
                base_resp = resp.get("BaseResp") or {}
                status_code = base_resp.get("StatusCode")
                code = resp.get("code")
                if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                    msg = resp.get("msg") or base_resp.get("StatusMessage") or "COZE_SUBMIT_FAILED"
                    if (
                        isinstance(code, int)
                        and code == 4000
                        and isinstance(msg, str)
                        and "Missing required parameters" in msg
                    ):
                        patched = self._patch_missing_required_params(params, msg)
                        if patched:
                            params = patched
                            continue
                    last_err = f"COZE_SUBMIT_FAILED code={code} statusCode={status_code} msg={msg}"
                    if attempt < 2 and isinstance(msg, str) and _is_transient(msg):
                        time.sleep(0.6 * (1.9**attempt))
                        continue
                    return [], last_err, None, None

                execute_id = str(resp.get("execute_id") or "").strip() or None
                debug_url = str(resp.get("debug_url") or "").strip() or None
                if execute_id:
                    break
                last_err = "COZE_SUBMIT_MISSING_EXECUTE_ID"
            except HTTPException as exc:
                last_err = str(exc.detail)
                if attempt < 2 and _is_transient(last_err):
                    time.sleep(0.6 * (1.9**attempt))
                    continue
                return [], last_err, None, None
            except Exception as exc:  # pragma: no cover - defensive
                last_err = str(exc)
                if attempt < 2:
                    time.sleep(0.6 * (1.9**attempt))
                    continue
                return [], last_err, None, None

        if not execute_id:
            return [], last_err or "COZE_SUBMIT_FAILED", None, debug_url

        # 2) Poll run history until output appears or failure.
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.2
        while time.monotonic() < deadline:
            try:
                hist = coze_client.get_workflow_run_history(execute_id=execute_id, workflow_id=workflow_id)
            except HTTPException as exc:
                detail = str(exc.detail)
                if _is_transient(detail):
                    time.sleep(interval)
                    interval = min(interval * 1.4, 8.0)
                    continue
                return [], detail, execute_id, debug_url
            base_resp = hist.get("BaseResp") or {}
            status_code = base_resp.get("StatusCode")
            code = hist.get("code")
            if (isinstance(code, int) and code != 0) or (isinstance(status_code, int) and status_code != 0):
                msg = hist.get("msg") or base_resp.get("StatusMessage") or "COZE_HISTORY_FAILED"
                return [], f"COZE_HISTORY_FAILED code={code} statusCode={status_code} msg={msg}", execute_id, debug_url

            parsed = self._parse_coze_payload(hist)
            # Coze may surface node failures as a JSON `{ "$error": "..." }` output.
            if isinstance(parsed, dict):
                if isinstance(parsed.get("$error"), str) and parsed.get("$error"):
                    return [], f"COZE_WORKFLOW_ERROR: {parsed.get('$error')}", execute_id, debug_url
                if isinstance(parsed.get("error_msg"), str) and parsed.get("error_msg"):
                    return [], f"COZE_WORKFLOW_ERROR: {parsed.get('error_msg')}", execute_id, debug_url
            images = self._extract_image_urls(parsed)
            output = parsed.get("output")
            # Treat empty-string output as "not ready yet" (common while tools are still running).
            output_present = output is not None and not (isinstance(output, str) and not output.strip())
            if images or output_present:
                podi_task_id: str | None = None
                if expects_callback and isinstance(output, str) and output.strip():
                    podi_task_id = decode_task_id(output.strip())
                else:
                    podi_task_id = decode_task_id(self._guess_podi_task_id(parsed, output))
                if podi_task_id:
                    with get_session() as session:
                        task_row = session.get(AbilityTask, podi_task_id)
                    if task_row:
                        imgs = self._poll_ability_task_inline(task_id=podi_task_id)
                        if imgs:
                            return imgs, None, execute_id, debug_url
                        return [], "TASK_IMAGES_EMPTY", execute_id, debug_url
                    callback_wf = settings.coze_comfyui_callback_workflow_id
                    if callback_wf:
                        imgs = self._poll_callback_images(callback_workflow_id=callback_wf, taskid=podi_task_id)
                        if imgs:
                            return imgs, None, execute_id, debug_url
                        return [], "CALLBACK_IMAGES_EMPTY", execute_id, debug_url
                if images:
                    return images, None, execute_id, debug_url
                return [], f"OUTPUT_NO_IMAGES output={str(output)[:128]}", execute_id, debug_url

            status = parsed.get("status") or parsed.get("run_status") or parsed.get("state")
            if isinstance(status, str) and status.lower() in {"failed", "error", "canceled", "cancelled"}:
                return [], f"COZE_RUN_{status}", execute_id, debug_url

            time.sleep(interval)
            interval = min(interval * 1.4, 8.0)

        return [], "COZE_ASYNC_TIMEOUT", execute_id, debug_url

    @staticmethod
    def _parse_coze_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize Coze response to a dict with parsed `data`.

        Coze `/v1/workflow/get_run_history` commonly returns:
        - data: [{..., input: "<json str>", output: "<json str>", execute_status: "...", ...}]
        We should parse the inner `output` JSON (not the entire record), otherwise we may
        mistakenly treat debug/input URLs as "image outputs".
        """
        data = payload.get("data")
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                # Some workflows return plain strings.
                return {"output": data}
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            # Run history: pick the latest record and parse its `output` JSON.
            if data:
                last = data[-1]
                if isinstance(last, dict):
                    out = last.get("output")
                    run_status = last.get("execute_status") or last.get("executeStatus") or last.get("status")
                    debug_url = last.get("debug_url") or last.get("debugUrl")
                    error_msg = last.get("error_msg") or last.get("errorMsg")

                    parsed_out: dict[str, Any] | None = None
                    if isinstance(out, str):
                        try:
                            maybe = json.loads(out)
                            if isinstance(maybe, dict):
                                parsed_out = maybe
                            else:
                                parsed_out = {"output": maybe}
                        except Exception:
                            parsed_out = {"output": out}
                    elif isinstance(out, dict):
                        parsed_out = out
                    elif out is not None:
                        parsed_out = {"output": out}

                    if isinstance(parsed_out, dict):
                        # Attach minimal metadata so callers can show status/debug links.
                        if run_status is not None and "run_status" not in parsed_out and "status" not in parsed_out:
                            parsed_out["run_status"] = run_status
                        if debug_url and "debug_url" not in parsed_out:
                            parsed_out["debug_url"] = debug_url
                        if error_msg and "error_msg" not in parsed_out:
                            parsed_out["error_msg"] = error_msg
                        return parsed_out

            # Fallback: keep the list under a predictable key; callers can recursively scan it.
            return {"output": data}
        # Fallback to the top-level payload (best-effort).
        if isinstance(payload, dict):
            return payload
        return {}

    @staticmethod
    def _guess_podi_task_id(parsed: dict[str, Any], output: Any) -> str | None:
        for key in ("podi_task_id", "task_id", "taskId"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(output, str) and _HEX_TASK_ID.match(output.strip()):
            return output.strip()
        return None

    @staticmethod
    def _extract_image_urls(payload: dict[str, Any]) -> list[str]:
        """Extract image URLs from common workflow outputs."""
        candidates: list[str] = []

        def _looks_like_image_url(url: str) -> bool:
            u = url.strip()
            if not u.startswith(("http://", "https://")):
                return False
            lower = u.lower()
            # Exclude known non-image URLs that sometimes appear in debug payloads.
            if "/work_flow" in lower or "/workflow" in lower and "execute_id=" in lower:
                return False
            if "execute_mode=" in lower and "execute_id=" in lower:
                return False
            # Accept common image/video extensions.
            if re.search(r"\.(png|jpe?g|webp|gif|bmp|mp4)(\\?|$)", lower):
                return True
            # Accept ComfyUI /view?filename=xxx.png style URLs.
            if "filename=" in lower and re.search(r"filename=[^&]+\\.(png|jpe?g|webp|gif|bmp)", lower):
                return True
            return False

        def _push(value: Any) -> None:
            if isinstance(value, str) and _looks_like_image_url(value):
                candidates.append(value)

        def _scan_any(value: Any, *, depth: int = 0) -> None:
            # Coze workflows are not consistent: outputs may be nested under `output`,
            # `data`, arrays, or custom fields. We do a bounded recursive scan as a
            # last-resort so "success but empty output" becomes less common.
            if depth > 6:
                return
            if len(candidates) >= 50:
                return
            if isinstance(value, str):
                _push(value)
                return
            if isinstance(value, dict):
                for v in value.values():
                    _scan_any(v, depth=depth + 1)
                return
            if isinstance(value, list):
                for item in value:
                    _scan_any(item, depth=depth + 1)
                return

        for key in ("imageUrl", "image_url", "url"):
            _push(payload.get(key))
        for key in ("imageUrls", "image_urls", "urls"):
            val = payload.get(key)
            if isinstance(val, list):
                for item in val:
                    _push(item)

        assets = payload.get("assets")
        if isinstance(assets, list):
            for item in assets:
                if isinstance(item, dict):
                    _push(item.get("storedUrl") or item.get("ossUrl") or item.get("url"))

        # Legacy: some workflows use output for a single URL.
        _push(payload.get("output"))
        # Fallback: recursively scan the payload for any http(s) string.
        if not candidates:
            _scan_any(payload)

        # Preserve order, de-dup.
        seen: set[str] = set()
        out: list[str] = []
        for u in candidates:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    def _poll_callback_images(self, *, callback_workflow_id: str, taskid: str) -> list[str]:
        """Resolve images for workflows that output a raw ComfyUI task id.

        The callback workflow may return empty images while the underlying job is still running,
        so we poll for a bounded period.
        """
        deadline = time.monotonic() + 180.0
        interval = 2.0
        last_images: list[str] = []
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            resolved = coze_client.run_workflow(
                workflow_id=callback_workflow_id,
                parameters={"taskid": taskid},
                is_async=False,
            )
            parsed = self._parse_coze_payload(resolved)
            images = self._extract_image_urls(parsed)
            last_images = images
            if images:
                break
            time.sleep(interval)
            interval = min(interval * 1.4, 8.0)
        return last_images

    def _poll_ability_task_inline(self, *, task_id: str) -> list[str]:
        """Poll an ability_task and return image URLs (for fan-out runs)."""
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.5
        attempts = 0

        while time.monotonic() < deadline:
            with get_session() as session:
                task_row = session.get(AbilityTask, task_id)
                if not task_row:
                    return []
                task = get_ability_task_service().to_dict(task_row)

            status = task.get("status")
            if status == "succeeded":
                result_payload = task.get("result_payload") or {}
                image_urls: list[str] = []
                if isinstance(result_payload, dict):
                    images = result_payload.get("images") or []
                    if isinstance(images, list):
                        for it in images:
                            if not isinstance(it, dict):
                                continue
                            for k in ("ossUrl", "sourceUrl", "url"):
                                v = it.get(k)
                                if isinstance(v, str) and v.strip():
                                    image_urls.append(v.strip())
                                    break
                return image_urls

            if status == "failed":
                return []

            # For long-running ComfyUI "submit only" tasks, the DB row stays running until we
            # finalize it by polling ComfyUI /history and ingesting outputs. Coze normally
            # triggers this via `/api/coze/podi/tasks/get`, but eval polling should be able
            # to finalize on its own (otherwise "generated but never refreshed" happens).
            attempts += 1
            if attempts % 3 == 0:
                self._try_finalize_comfyui_task(task_id=task_id)

            time.sleep(interval)
            interval = min(interval * 1.3, 10.0)

        return []

    def _poll_ability_task(self, *, run_id: str, task_id: str, started: float) -> None:
        deadline = time.monotonic() + 60 * 20  # 20 minutes max
        interval = 1.5
        last_status: str | None = None
        attempts = 0

        while time.monotonic() < deadline:
            with get_session() as session:
                task_row = session.get(AbilityTask, task_id)
                if not task_row:
                    self._mark_failed(run_id, message="TASK_NOT_FOUND", started=started)
                    return
                task = get_ability_task_service().to_dict(task_row)
            status = task.get("status")
            if status != last_status:
                last_status = status
                with get_session() as session:
                    run = session.get(EvalRun, run_id)
                    if run:
                        run.podi_task_id = task_id
                        session.add(run)
                        session.commit()

            if status == "succeeded":
                result_payload = task.get("result_payload") or {}
                image_urls: list[str] = []
                if isinstance(result_payload, dict):
                    images = result_payload.get("images") or []
                    if isinstance(images, list):
                        for it in images:
                            if not isinstance(it, dict):
                                continue
                            for k in ("ossUrl", "sourceUrl", "url"):
                                v = it.get(k)
                                if isinstance(v, str) and v.strip():
                                    image_urls.append(v.strip())
                                    break
                self._mark_succeeded(run_id, image_urls=image_urls, started=started)
                return

            if status == "failed":
                self._mark_failed(run_id, message=task.get("error_message") or "TASK_FAILED", started=started)
                return

            attempts += 1
            if attempts % 3 == 0:
                # Try to finalize ComfyUI submitted-only tasks.
                self._try_finalize_comfyui_task(task_id=task_id)

            time.sleep(interval)
            interval = min(interval * 1.3, 10.0)

        self._mark_failed(run_id, message="TASK_TIMEOUT", started=started)

    def _try_finalize_comfyui_task(self, *, task_id: str) -> None:
        """Best-effort: finalize a ComfyUI submitted-only task by polling /history.

        This mirrors the behavior in `/api/coze/podi/tasks/get` so eval runs can refresh
        without relying on a separate Coze callback workflow.
        """

        with get_session() as session:
            task_row = session.get(AbilityTask, task_id)
            if not task_row:
                return
            if (task_row.ability_provider or "").lower() != "comfyui":
                return
            if task_row.status not in {"queued", "running"}:
                return
            result_payload = task_row.result_payload or {}
            if not isinstance(result_payload, dict):
                return
            meta = result_payload.get("metadata") if isinstance(result_payload.get("metadata"), dict) else {}
            prompt_id = meta.get("promptId") or meta.get("taskId")
            base_url = meta.get("baseUrl")
            executor_id = meta.get("executorId")
            # Multi-ComfyUI support: prefer executor config if available.
            if isinstance(executor_id, str) and executor_id.strip():
                try:
                    from app.models.integration import Executor

                    ex = session.get(Executor, executor_id.strip())
                    if ex:
                        cfg = ex.config or {}
                        ex_base = (ex.base_url or cfg.get("baseUrl") or cfg.get("base_url") or "").strip()
                        if ex_base:
                            base_url = ex_base
                except Exception:
                    pass

            if not (isinstance(prompt_id, str) and prompt_id.strip() and isinstance(base_url, str) and base_url.strip()):
                return

        # Avoid importing heavy modules unless needed.
        try:
            import httpx
            from types import SimpleNamespace

            from app.services.executors.base import ExecutionContext
            from app.services.executors.registry import registry
        except Exception:
            return

        adapter = registry.get("comfyui")
        if adapter is None:
            return

        try:
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
                with get_session() as session:
                    db_task = session.get(AbilityTask, task_id)
                    if db_task:
                        db_task.status = "failed"
                        db_task.error_message = "COMFYUI_ERROR"
                        session.add(db_task)
                        session.commit()
                return
            if status_str != "success":
                return

            images = outputs.get("images") if isinstance(outputs, dict) else None
            if not isinstance(images, list) or not images:
                return

            ctx = ExecutionContext(
                task=SimpleNamespace(id=task_id, user_id="eval", assets=[]),
                workflow=SimpleNamespace(id="eval_finalize", definition={}, extra_metadata={}),
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

            if not assets:
                return

            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if not db_task:
                    return
                next_payload = dict(db_task.result_payload or {})
                next_payload["images"] = assets
                next_payload["assets"] = assets
                next_payload["status"] = "succeeded"
                db_task.status = "succeeded"
                db_task.result_payload = next_payload
                session.add(db_task)
                session.commit()
        except Exception as exc:
            # Best-effort; keep task running but record the last diagnostic hint for operators.
            with get_session() as session:
                db_task = session.get(AbilityTask, task_id)
                if db_task and db_task.status in {"queued", "running"}:
                    db_task.error_message = str(exc)[:240]
                    session.add(db_task)
                    session.commit()
            return

    @staticmethod
    def _extract_output_json(payload: dict[str, Any]) -> Any:
        """Best-effort extraction of `output` for non-image workflows.

        Coze often returns `output` as:
        - a JSON string (e.g. "{...}") for tagging/metadata flows
        - a primitive/string for text flows
        """

        if not isinstance(payload, dict):
            return None
        output = payload.get("output")
        if output is None:
            if any(k in payload for k in ("servers", "totalPending", "totalRunning", "totalCount", "timestamp")):
                return payload
            return None
        if isinstance(output, (dict, list, int, float, bool)):
            return output
        if isinstance(output, str):
            s = output.strip()
            if not s:
                return None
            # Try parsing JSON-like strings for nicer rendering in the UI.
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    parsed = json.loads(s)
                    return parsed
                except Exception:
                    pass
            # Avoid persisting huge bodies.
            return s[:8000]
        return str(output)[:8000]

    @staticmethod
    def _mark_succeeded(
        run_id: str,
        *,
        image_urls: list[str],
        output_json: Any | None = None,
        started: float,
        error_message: str | None = None,
    ) -> None:
        # Last-line defense: avoid persisting obvious non-image debug URLs as "image outputs".
        cleaned: list[str] = []
        for u in image_urls or []:
            if not isinstance(u, str):
                continue
            s = u.strip()
            if not s:
                continue
            lower = s.lower()
            if "/work_flow" in lower or ("/workflow" in lower and "execute_id=" in lower):
                continue
            if "execute_mode=" in lower and "execute_id=" in lower:
                continue
            cleaned.append(s)

        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            run.status = "succeeded"
            run.error_message = error_message
            run.result_image_urls_json = cleaned or []
            run.result_output_json = output_json
            run.duration_ms = int((time.monotonic() - started) * 1000)
            session.add(run)
            session.commit()

    @staticmethod
    def _mark_failed(run_id: str, *, message: str, started: float) -> None:
        with get_session() as session:
            run = session.get(EvalRun, run_id)
            if not run:
                return
            run.status = "failed"
            run.error_message = message
            run.duration_ms = int((time.monotonic() - started) * 1000)
            session.add(run)
            session.commit()


@lru_cache
def get_eval_service() -> EvalService:
    """Lazy singleton to avoid import-time side effects (important under uvicorn reload)."""

    return EvalService()
