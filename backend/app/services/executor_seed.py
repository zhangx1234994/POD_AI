"""Utility helpers to seed executor records with default vendor credentials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import os
import re
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integration import ApiKey, Executor, ExecutorApiKey

settings = get_settings()

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _read_dotenv(path: Path) -> dict[str, str]:
    """Best-effort .env parser (keeps this module dependency-free)."""

    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k:
            out[k] = v
    return out


def _env_lookup() -> dict[str, str]:
    # Pydantic reads `backend/.env` without exporting it to the process env.
    # Read it so `${VAR}` in `config/executors.yaml` resolves correctly.
    env = dict(os.environ)
    backend_dir = Path(__file__).resolve().parents[2]
    env.update(_read_dotenv(backend_dir / ".env"))
    return env


def _interpolate_env(value: Any, env: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: env.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v, env) for v in value]
    return value


@dataclass(frozen=True)
class ExecutorSeed:
    id: str
    name: str
    type: str
    base_url: str | None = None
    status: str = "active"
    weight: int = 1
    max_concurrency: int = 1
    config: dict[str, Any] | None = None


def _load_external_seeds() -> list[ExecutorSeed]:
    raw_path = Path(settings.executor_config_path)
    path: Path | None = None
    if raw_path.is_absolute() and raw_path.exists():
        path = raw_path
    elif raw_path.exists():
        path = raw_path
    else:
        project_root = Path(__file__).resolve().parents[3]
        candidate = project_root / raw_path
        if candidate.exists():
            path = candidate
    if path is None or not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError:
        return []
    env = _env_lookup()
    seeds: list[ExecutorSeed] = []
    if isinstance(raw, dict):
        items = raw.get("executors") if isinstance(raw.get("executors"), list) else []
    else:
        items = raw if isinstance(raw, list) else []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        config = entry.get("config")
        if not config or not isinstance(config, dict):
            continue
        config = _interpolate_env(config, env)
        seed = ExecutorSeed(
            id=str(entry.get("id") or ""),
            name=str(entry.get("name") or ""),
            type=str(entry.get("type") or ""),
            base_url=entry.get("base_url") or entry.get("baseUrl"),
            status=str(entry.get("status") or "active"),
            weight=int(entry.get("weight") or 1),
            max_concurrency=int(entry.get("max_concurrency") or entry.get("maxConcurrency") or 1),
            config=config if isinstance(config, dict) else None,
        )
        if seed.id and seed.name and seed.type:
            seeds.append(seed)
    return seeds


def _fallback_env_seeds() -> list[ExecutorSeed]:
    seeds: list[ExecutorSeed] = []
    if settings.baidu_api_key and settings.baidu_secret_key:
        seeds.append(
            ExecutorSeed(
                id="executor_baidu_image_default",
                name="百度图像处理 · 默认节点",
                type="baidu",
                base_url=settings.baidu_base_url,
                status="active",
                weight=1,
                max_concurrency=2,
                config={
                    "apiKey": settings.baidu_api_key,
                    "secretKey": settings.baidu_secret_key,
                },
            )
        )
    if settings.volcengine_api_key:
        seeds.append(
            ExecutorSeed(
                id="executor_volcengine_default",
                name="火山 Doubao · 默认节点",
                type="volcengine",
                base_url=settings.volcengine_base_url,
                status="active",
                weight=1,
                max_concurrency=2,
                config={
                    "apiKey": settings.volcengine_api_key,
                    "baseUrl": settings.volcengine_base_url,
                },
            )
        )
    return seeds


DEFAULT_EXECUTOR_SEEDS: list[ExecutorSeed] = _load_external_seeds() or _fallback_env_seeds()


def ensure_default_executors(session: Session) -> bool:
    """Insert (or lightly repair) default executors; return True if DB changed.

    Notes:
    - We seed from `config/executors.yaml` which may use `${ENV}` placeholders.
    - If executors already exist but still contain unresolved placeholders, we update
      them so internal integrations (Coze) can run without manual admin steps.
    """

    def has_unresolved_placeholders(obj: Any) -> bool:
        if obj is None:
            return False
        if isinstance(obj, str):
            return "${" in obj
        if isinstance(obj, dict):
            return any(has_unresolved_placeholders(v) for v in obj.values())
        if isinstance(obj, list):
            return any(has_unresolved_placeholders(v) for v in obj)
        return False

    def merge_missing_values(existing: Any, desired: Any) -> tuple[Any, bool]:
        """Fill empty-string values in existing dicts from desired dicts."""
        changed_local = False
        if isinstance(existing, dict) and isinstance(desired, dict):
            out: dict[str, Any] = dict(existing)
            for k, v in desired.items():
                if k not in out:
                    out[k] = v
                    changed_local = True
                    continue
                cur = out.get(k)
                if isinstance(cur, str) and cur == "" and isinstance(v, str) and v != "":
                    out[k] = v
                    changed_local = True
                elif isinstance(cur, dict) and isinstance(v, dict):
                    merged, ch = merge_missing_values(cur, v)
                    if ch:
                        out[k] = merged
                        changed_local = True
            return out, changed_local
        return existing, False

    changed = False
    for seed in DEFAULT_EXECUTOR_SEEDS:
        if not seed.config:
            continue
        stmt = select(Executor).where(Executor.id == seed.id)
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
            # Only "repair" obviously-broken placeholders; do not blindly overwrite.
            if has_unresolved_placeholders(existing.config) and not has_unresolved_placeholders(seed.config):
                existing.config = seed.config
                changed = True
            else:
                # Also fill missing/empty values when env vars were set later.
                merged, did_change = merge_missing_values(existing.config or {}, seed.config or {})
                if did_change:
                    existing.config = merged
                    changed = True
            if (existing.base_url or "") != (seed.base_url or "") and seed.base_url:
                existing.base_url = seed.base_url
                changed = True
            if existing.status != seed.status:
                existing.status = seed.status
                changed = True
            if existing.weight != seed.weight:
                existing.weight = seed.weight
                changed = True
            if existing.max_concurrency != seed.max_concurrency:
                existing.max_concurrency = seed.max_concurrency
                changed = True
            continue
        executor = Executor(
            id=seed.id,
            name=seed.name,
            type=seed.type,
            base_url=seed.base_url,
            status=seed.status,
            weight=seed.weight,
            max_concurrency=seed.max_concurrency,
            config=seed.config,
        )
        session.add(executor)
        changed = True

        # We may want to create default API key bindings for this executor.
        # (done after insert below)
    if changed:
        session.commit()
    # Even if no executors were created, we may still need to repair placeholders or
    # create ApiKey bindings from executor.config.
    changed = _ensure_executor_api_keys(session) or changed
    return changed


def _ensure_executor_api_keys(session: Session) -> bool:
    """Best-effort: materialize api_keys + bindings from executor.config.

    This keeps backwards-compatibility with the existing "config/executors.yaml"
    / env-var based setup, while enabling DB-based key rotation.
    """

    def upsert_key(*, provider: str, name: str, key_value: str, metadata: dict[str, Any] | None = None) -> ApiKey:
        existing = (
            session.execute(select(ApiKey).where(ApiKey.provider == provider, ApiKey.key == key_value))
            .scalars()
            .first()
        )
        if existing:
            return existing
        api_key = ApiKey(
            id=os.urandom(16).hex(),
            provider=provider,
            name=name,
            key=key_value,
            status="active",
            extra_metadata=metadata,
        )
        session.add(api_key)
        return api_key

    def ensure_link(*, executor_id: str, api_key_id: str, priority: int = 0) -> bool:
        link = session.get(ExecutorApiKey, {"executor_id": executor_id, "api_key_id": api_key_id})
        if link:
            return False
        session.add(ExecutorApiKey(executor_id=executor_id, api_key_id=api_key_id, priority=priority))
        return True

    executors = session.execute(select(Executor)).scalars().all()
    mutated = False
    for ex in executors:
        cfg = ex.config or {}
        provider = (ex.type or "").lower()

        if provider in {"volcengine", "kie"}:
            key_value = cfg.get("apiKey") or cfg.get("api_key")
            if isinstance(key_value, str) and key_value.strip():
                api_key = upsert_key(provider=provider, name=f"{ex.name} · API Key", key_value=key_value.strip())
                mutated = ensure_link(executor_id=ex.id, api_key_id=api_key.id, priority=0) or mutated

        if provider == "baidu":
            api_key_val = cfg.get("apiKey")
            secret_key_val = cfg.get("secretKey")
            if (
                isinstance(api_key_val, str)
                and api_key_val.strip()
                and isinstance(secret_key_val, str)
                and secret_key_val.strip()
            ):
                api_key = upsert_key(
                    provider="baidu",
                    name=f"{ex.name} · API Key",
                    key_value=api_key_val.strip(),
                    metadata={"secretKey": secret_key_val.strip()},
                )
                mutated = ensure_link(executor_id=ex.id, api_key_id=api_key.id, priority=0) or mutated

    if mutated:
        session.commit()
    return mutated
