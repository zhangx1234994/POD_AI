"""Fallback standalone Coze toolbox route for FLUX2-Klein outpaint.

This router exists so the single-tool OpenAPI remains available even when the
main Coze plugin router was deployed without the dedicated route.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.routers.coze_podi_plugin import _build_openapi_filtered


router = APIRouter(prefix="/api/coze/podi", tags=["coze-plugin"])


@router.get("/comfyui/execute/flux2-klein-9b-outpaint/openapi.json")
def get_comfyui_flux2_klein_9b_outpaint_openapi(request: Request) -> dict[str, Any]:
    """OpenAPI for standalone ComfyUI FLUX2-Klein outpaint toolbox."""
    doc = _build_openapi_filtered(
        request=request,
        providers={"comfyui"},
        title="PODI ComfyUI 执行 · FLUX2-Klein 扩图",
        description="ComfyUI FLUX2-Klein 扩图独立工具箱（含提交工具与任务轮询）。",
        prefer_url_field=True,
    )
    paths = doc.get("paths") or {}
    allowed = {
        "/api/coze/podi/tools/comfyui/flux2_klein_9b_outpaint",
        "/api/coze/podi/tasks/get",
    }
    doc["paths"] = {k: v for k, v in paths.items() if k in allowed}
    return doc
