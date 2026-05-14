#!/usr/bin/env python3
"""Audit FastAPI routes against the PODI external API boundary."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@dataclass(frozen=True)
class Surface:
    name: str
    audience: str
    business_facing: str
    note: str


SURFACES: tuple[tuple[str, Surface], ...] = (
    (
        "/api/business/openapi.json",
        Surface("业务 API 文档", "业务方/开发联调", "是", "公开文档入口，不应包含密钥或内部排障字段。"),
    ),
    (
        "/api/business",
        Surface("业务 API", "业务方/业务系统/Coze 新工作流", "是", "必须使用业务 API Key、服务 Token、登录态或可信内网。"),
    ),
    (
        "/api/coze/podi",
        Surface("Coze 工具箱", "Coze 工作流", "否", "OpenAPI 可导入；执行接口需内网或服务 Token。"),
    ),
    (
        "/api/admin",
        Surface("管理端 API", "管理员", "否", "必须管理员鉴权。"),
    ),
    (
        "/api/evals",
        Surface("评测 API", "内部测评", "否", "用于回归和打分，不承诺业务接入稳定性。"),
    ),
    (
        "/api/abilities",
        Surface("原子能力 API", "内部编排/测评/高级开发", "否", "普通业务方优先使用业务 API。"),
    ),
    (
        "/api/ability-tasks",
        Surface("原子能力任务 API", "内部编排/测评/高级开发", "否", "普通业务方优先使用业务 API。"),
    ),
    (
        "/api/media",
        Surface("媒资 API", "管理端/测评端/内部工具", "否", "上传凭证与签名下载，不作为业务生成入口。"),
    ),
    (
        "/api/agent",
        Surface("Agent API", "ComfyUI 轻 Agent", "否", "运行期应使用 Agent Token。"),
    ),
    (
        "/api/tasks/v1",
        Surface("历史任务中心", "历史兼容", "否", "新业务禁止使用。"),
    ),
    (
        "/api/wallet",
        Surface("历史钱包 API", "历史兼容/内部", "否", "当前只做框架和兼容。"),
    ),
    (
        "/api/op/v1",
        Surface("历史积分 API", "历史兼容/内部", "否", "当前是占位联调接口。"),
    ),
    (
        "/api/os/v1",
        Surface("历史积分公开别名", "历史兼容/内部", "否", "当前是占位联调接口。"),
    ),
    (
        "/api/notify",
        Surface("通知 API", "内部页面/联调", "否", "不作为业务方正式接口。"),
    ),
    (
        "/api/auth",
        Surface("认证 API", "管理端/内部用户", "否", "业务 API Key 不通过登录接口获取。"),
    ),
    (
        "/health",
        Surface("健康检查", "运维/发布检查", "否", "只表达服务存活，不代表业务链路健康。"),
    ),
)


def classify(path: str) -> Surface:
    for prefix, surface in SURFACES:
        if path == prefix or path.startswith(f"{prefix}/"):
            return surface
    return Surface("未分类", "待确认", "否", "需要纳入接口边界规范。")


def dependency_names(route: object) -> list[str]:
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return []
    names: list[str] = []
    for dep in getattr(dependant, "dependencies", []) or []:
        call = getattr(dep, "call", None)
        names.append(getattr(call, "__name__", str(call)))
    return names


def auth_note(path: str, deps: Iterable[str]) -> str:
    dep_set = set(deps)
    if "require_admin" in dep_set:
        return "管理员鉴权"
    if "get_current_user" in dep_set:
        return "登录/服务 Token"
    if "_resolve_business_user" in dep_set:
        return "业务 Key/登录/服务 Token/可信内网"
    if "_document_bearer" in dep_set:
        return "函数内校验 Agent Token"
    if path.startswith("/api/coze/podi/tools") or path.startswith("/api/coze/podi/tasks"):
        return "函数内校验内网/服务 Token"
    if path.endswith("/openapi.json") or path == "/health":
        return "公开读取"
    return "无路由级鉴权"


def iter_routes() -> list[dict[str, str]]:
    from fastapi.routing import APIRoute
    from app.main import app

    rows: list[dict[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = str(route.path)
        surface = classify(path)
        deps = dependency_names(route)
        rows.append(
            {
                "methods": ",".join(sorted(route.methods or [])),
                "path": path,
                "surface": surface.name,
                "businessFacing": surface.business_facing,
                "audience": surface.audience,
                "auth": auth_note(path, deps),
                "note": surface.note,
            }
        )
    return sorted(rows, key=lambda item: (item["surface"], item["path"], item["methods"]))


def print_summary(rows: list[dict[str, str]]) -> None:
    surface_counts = Counter(row["surface"] for row in rows)
    auth_counts = Counter(row["auth"] for row in rows)
    print("# PODI 接口边界审计摘要")
    print()
    print(f"- route_count: {len(rows)}")
    print(f"- unclassified_count: {surface_counts.get('未分类', 0)}")
    print()
    print("## 按接口层级")
    for surface, count in surface_counts.most_common():
        print(f"- {surface}: {count}")
    print()
    print("## 按鉴权提示")
    for auth, count in auth_counts.most_common():
        print(f"- {auth}: {count}")
    print()


def print_table(rows: list[dict[str, str]]) -> None:
    print("| Methods | Path | 层级 | 给业务方 | 鉴权提示 |")
    print("| --- | --- | --- | --- | --- |")
    for row in rows:
        print(
            f"| `{row['methods']}` | `{row['path']}` | {row['surface']} | {row['businessFacing']} | {row['auth']} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="Only print grouped summary.")
    args = parser.parse_args()

    rows = iter_routes()
    print_summary(rows)
    if not args.summary:
        print_table(rows)
    return 1 if any(row["surface"] == "未分类" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
