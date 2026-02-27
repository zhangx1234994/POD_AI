"""Task execution engine for desktop agent."""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import jwt

from .center_client import CenterClient
from .models import DesktopConfig
from .state_store import StateStore


@dataclass
class TaskContext:
    task_id: str
    token: str
    nonce: str
    manifest_url: str
    actions: dict[str, bool]


class TaskError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TaskEngine:
    def __init__(self, *, config: DesktopConfig, store: StateStore, client: CenterClient) -> None:
        self.config = config
        self.store = store
        self.client = client
        self._lock = threading.Lock()
        self._running_task_id: str | None = None

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        ctx = self._parse_task_payload(payload)
        with self._lock:
            if self._running_task_id:
                raise TaskError("AGENT_BUSY", f"busy with task {self._running_task_id}")
            self._running_task_id = ctx.task_id
        failed_items: dict[str, list[str]] = {"models": [], "plugins": [], "workflows": []}
        try:
            self.store.upsert_task(task_id=ctx.task_id, status="running", request_payload=payload)
            self._report_event(ctx, level="info", message="task started", stage="submit")
            self._validate_task_token(ctx)
            self.client.verify_task_token(
                {
                    "token": ctx.token,
                    "agent_id": self.config.agent_id,
                    "task_id": ctx.task_id,
                    "nonce": ctx.nonce,
                }
            )
            self._report_event(ctx, level="info", message="token verified", stage="verify")
            manifest = self.client.fetch_manifest(ctx.manifest_url, ctx.token)
            content = manifest.get("content") if isinstance(manifest, dict) else {}
            if not isinstance(content, dict):
                content = {}
            self._report_event(ctx, level="info", message="manifest fetched", stage="manifest")

            if ctx.actions.get("sync_models"):
                self._sync_models(content.get("models"), failed_items["models"])
            if ctx.actions.get("sync_plugins"):
                self._sync_git_collection(
                    content.get("plugins"),
                    Path(self.config.comfyui_path).expanduser() / "custom_nodes",
                    failed_items["plugins"],
                )
            if ctx.actions.get("sync_workflows"):
                self._sync_git_collection(
                    content.get("workflows"),
                    Path(self.config.comfyui_path).expanduser() / "workflows",
                    failed_items["workflows"],
                )
            if ctx.actions.get("sync_comfyui"):
                self._sync_comfyui_version(content.get("comfyui"))
            if ctx.actions.get("restart"):
                self._report_event(ctx, level="info", message="restart requested", stage="restart")

            self.store.set_snapshot(
                str(manifest.get("version") or ""),
                {
                    "manifest": manifest,
                    "failed_items": failed_items,
                },
            )
            result = {
                "summary": "ok",
                "failed_items": failed_items,
            }
            self.store.upsert_task(task_id=ctx.task_id, status="success", result_payload=result)
            self.client.report_complete(ctx.task_id, ctx.token, result)
            return {"status": "accepted", "task_id": ctx.task_id}
        except TaskError as exc:
            self.store.upsert_task(task_id=ctx.task_id, status="failed", message=exc.message)
            failed_payload = {
                "error_code": exc.code,
                "message": exc.message,
                "failed_items": failed_items,
            }
            try:
                self.client.report_failed(ctx.task_id, ctx.token, failed_payload)
            except Exception:
                pass
            raise
        except Exception as exc:  # pragma: no cover - runtime fallback
            message = str(exc)
            self.store.upsert_task(task_id=ctx.task_id, status="failed", message=message)
            failed_payload = {
                "error_code": "EXECUTION_FAILED",
                "message": message,
                "failed_items": failed_items,
            }
            try:
                self.client.report_failed(ctx.task_id, ctx.token, failed_payload)
            except Exception:
                pass
            raise TaskError("EXECUTION_FAILED", message) from exc
        finally:
            with self._lock:
                self._running_task_id = None

    def _parse_task_payload(self, payload: dict[str, Any]) -> TaskContext:
        task_id = str(payload.get("task_id") or payload.get("taskId") or "").strip()
        token = str(payload.get("token") or "").strip()
        nonce = str(payload.get("nonce") or "").strip()
        manifest_url = str(payload.get("manifest_url") or payload.get("manifestUrl") or "").strip()
        if not task_id:
            raise TaskError("TASK_ID_REQUIRED", "task_id is required")
        if not token:
            raise TaskError("TASK_TOKEN_REQUIRED", "token is required")
        if not manifest_url:
            raise TaskError("MANIFEST_URL_REQUIRED", "manifest_url is required")
        actions = self._normalize_actions(payload.get("actions"))
        return TaskContext(
            task_id=task_id,
            token=token,
            nonce=nonce,
            manifest_url=manifest_url,
            actions=actions,
        )

    @staticmethod
    def _normalize_actions(raw: Any) -> dict[str, bool]:
        defaults = {
            "sync_models": True,
            "sync_plugins": True,
            "sync_workflows": True,
            "sync_comfyui": False,
            "restart": False,
        }
        if isinstance(raw, dict):
            merged = dict(defaults)
            for key, value in raw.items():
                merged[str(key)] = bool(value)
            return merged
        if isinstance(raw, list):
            merged = {key: False for key in defaults}
            for item in raw:
                key = str(item).strip()
                if key:
                    merged[key] = True
            return merged
        return defaults

    def _validate_task_token(self, ctx: TaskContext) -> None:
        if not self.config.jwt_keys:
            raise TaskError("JWT_KEYS_MISSING", "no jwt key configured")
        try:
            header = jwt.get_unverified_header(ctx.token)
        except jwt.PyJWTError as exc:
            raise TaskError("TASK_TOKEN_INVALID", str(exc)) from exc
        kid = str(header.get("kid") or "").strip()
        secret = ""
        for item in self.config.jwt_keys:
            if item.kid == kid:
                secret = item.secret
                break
        if not secret and len(self.config.jwt_keys) == 1:
            secret = self.config.jwt_keys[0].secret
        if not secret:
            raise TaskError("TASK_TOKEN_KID_INVALID", f"kid {kid or '<empty>'} not found")
        try:
            payload = jwt.decode(ctx.token, secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise TaskError("TASK_TOKEN_INVALID", str(exc)) from exc
        token_task_id = str(payload.get("task_id") or "")
        if token_task_id and token_task_id != ctx.task_id:
            raise TaskError("TASK_TOKEN_MISMATCH", "task_id mismatch")
        token_agent_id = str(payload.get("agent_id") or "")
        if token_agent_id and self.config.agent_id and token_agent_id != self.config.agent_id:
            raise TaskError("TASK_TOKEN_MISMATCH", "agent_id mismatch")

    def _report_event(self, ctx: TaskContext, *, level: str, message: str, stage: str) -> None:
        self.client.report_event(
            ctx.task_id,
            ctx.token,
            {
                "level": level,
                "stage": stage,
                "message": message,
            },
        )

    def _sync_models(self, models: Any, failed_items: list[str]) -> None:
        if not isinstance(models, list):
            return
        comfyui_root = Path(self.config.comfyui_path).expanduser()
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            url = str(item.get("url") or "").strip()
            sha256 = str(item.get("sha256") or "").strip().lower()
            dest_rel = str(item.get("dest_path") or item.get("destPath") or "").strip()
            if not name or not url or not dest_rel:
                failed_items.append(name or url or "unknown_model")
                continue
            dest = comfyui_root / dest_rel
            try:
                self._download_file(url, dest)
                if sha256:
                    digest = self._sha256(dest)
                    if digest != sha256:
                        raise TaskError("CHECKSUM_MISMATCH", f"{name} checksum mismatch")
            except Exception:
                failed_items.append(name)

    def _sync_git_collection(self, items: Any, root_dir: Path, failed_items: list[str]) -> None:
        if not isinstance(items, list):
            return
        root_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            repo = str(item.get("repo") or "").strip()
            commit = str(item.get("commit") or "").strip()
            if not repo:
                failed_items.append(name or "unknown_repo")
                continue
            folder_name = name or Path(repo.rstrip("/")).stem.replace(".git", "")
            target = root_dir / folder_name
            try:
                if not target.exists():
                    self._run(["git", "clone", repo, str(target)])
                else:
                    self._run(["git", "-C", str(target), "fetch", "--all", "--tags", "--prune"])
                if commit:
                    self._run(["git", "-C", str(target), "checkout", commit])
                else:
                    self._run(["git", "-C", str(target), "pull", "--ff-only"])
            except Exception:
                failed_items.append(folder_name)

    def _sync_comfyui_version(self, comfyui_meta: Any) -> None:
        if not isinstance(comfyui_meta, dict):
            return
        commit = str(comfyui_meta.get("commit") or "").strip()
        if not commit:
            return
        comfyui_root = Path(self.config.comfyui_path).expanduser()
        if not comfyui_root.exists():
            raise TaskError("COMFYUI_PATH_MISSING", str(comfyui_root))
        self._run(["git", "-C", str(comfyui_root), "fetch", "--all", "--tags", "--prune"])
        self._run(["git", "-C", str(comfyui_root), "checkout", commit])

    @staticmethod
    def _download_file(url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".part")
        with httpx.stream("GET", url, timeout=300) as response:
            response.raise_for_status()
            with temp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    if chunk:
                        handle.write(chunk)
        os.replace(temp, target)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest().lower()

    @staticmethod
    def _run(cmd: list[str]) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "command failed").strip()
            raise TaskError("COMMAND_FAILED", message)
