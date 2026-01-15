"""Utility helpers to seed executor records with default vendor credentials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.integration import Executor

settings = get_settings()


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
        raw = yaml.safe_load(path.read_text()) or []
    except yaml.YAMLError:
        return []
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
        seed = ExecutorSeed(
            id=str(entry.get("id") or ""),
            name=str(entry.get("name") or ""),
            type=str(entry.get("type") or ""),
            base_url=entry.get("base_url") or entry.get("baseUrl"),
            status=str(entry.get("status") or "active"),
            weight=int(entry.get("weight") or 1),
            max_concurrency=int(entry.get("max_concurrency") or entry.get("maxConcurrency") or 1),
            config=config,
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
    """Insert default executors when they do not exist; return True if new rows created."""

    created = False
    for seed in DEFAULT_EXECUTOR_SEEDS:
        if not seed.config:
            continue
        stmt = select(Executor).where(Executor.id == seed.id)
        existing = session.execute(stmt).scalar_one_or_none()
        if existing:
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
        created = True
    if created:
        session.commit()
    return created
