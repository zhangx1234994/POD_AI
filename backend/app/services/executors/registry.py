"""Executor adapter registry."""

from __future__ import annotations

from typing import Dict

from .base import ExecutorAdapter
from .mock import MockExecutorAdapter
from .baidu_image import BaiduImageExecutorAdapter
from .comfyui import ComfyUIExecutorAdapter


class ExecutorRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, ExecutorAdapter] = {}

    def register(self, executor_type: str, adapter: ExecutorAdapter) -> None:
        self._adapters[executor_type] = adapter

    def get(self, executor_type: str) -> ExecutorAdapter | None:
        return self._adapters.get(executor_type) or self._adapters.get("mock")


registry = ExecutorRegistry()
registry.register("mock", MockExecutorAdapter())
registry.register("baidu", BaiduImageExecutorAdapter())
registry.register("comfyui", ComfyUIExecutorAdapter())

# 默认将常见 provider 指向对应实现（暂以 mock 作为 fallback）
for provider_type in ("openai", "volcengine", "aliyun"):
    registry.register(provider_type, registry.get(provider_type) or registry.get("mock"))  # type: ignore[arg-type]
