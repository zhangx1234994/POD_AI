"""FastAPI 主入口，聚合各领域路由。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import get_session
from app.services.ability_task_service import get_ability_task_service
from app.services.business_runs import get_business_run_service
from app.services.business_seed import ensure_default_business_capabilities
from app.services.eval_service import get_eval_service
from app.services.executor_seed import ensure_default_executors

from app.routers import (
    abilities,
    ability_tasks,
    health,
    media,
    wallet,
    points,
    admin_integrations,
    admin_billing,
    admin_dashboard,
    admin_abilities,
    admin_vendor,
    admin_evals,
    evals_public,
    auth,
    coze_podi_plugin,
    coze_podi_flux2_outpaint,
    tasks,
    notify,
    agent_management,
    business,
)


def create_app() -> FastAPI:
    app = FastAPI(title="PODI Backend", version="0.1.0")

    @app.on_event("startup")
    def _warmup_services() -> None:
        with get_session() as session:
            ensure_default_executors(session)
            ensure_default_business_capabilities(session)
        # Instantiate background queues once per process so pending tasks/runs are resumed.
        get_ability_task_service()
        get_business_run_service()
        get_eval_service()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"]
        ,
        allow_headers=["*"]
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(media.router, prefix="/api/media", tags=["media"])
    app.include_router(wallet.router, prefix="/api/wallet", tags=["wallet"])
    app.include_router(points.router, prefix="/api/op/v1", tags=["points"])
    app.include_router(points.router, prefix="/api/os/v1", tags=["points-public"])
    app.include_router(abilities.router, tags=["abilities"])
    app.include_router(ability_tasks.router)
    app.include_router(admin_integrations.router, prefix="/api", tags=["admin"])
    app.include_router(admin_billing.router, prefix="/api", tags=["admin-billing"])
    app.include_router(admin_abilities.router, prefix="/api", tags=["admin-abilities"])
    app.include_router(admin_vendor.router, prefix="/api", tags=["admin-vendor-api"])
    app.include_router(admin_dashboard.router, prefix="/api", tags=["admin-dashboard"])
    app.include_router(admin_evals.router, prefix="/api/admin", tags=["admin-evals"])
    app.include_router(evals_public.router)
    app.include_router(coze_podi_plugin.router)
    flux2_single_openapi_path = "/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json"
    if not any(getattr(route, "path", None) == flux2_single_openapi_path for route in app.routes):
        app.include_router(coze_podi_flux2_outpaint.router)
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(notify.router, tags=["notify"])
    app.include_router(agent_management.agent_router)
    app.include_router(agent_management.admin_router)
    app.include_router(business.router)
    app.include_router(business.admin_router, prefix="/api")
    return app


app = create_app()
