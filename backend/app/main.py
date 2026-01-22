"""FastAPI 主入口，聚合各领域路由。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    abilities,
    ability_tasks,
    health,
    media,
    wallet,
    points,
    admin_integrations,
    admin_dashboard,
    admin_abilities,
    admin_evals,
    evals_public,
    auth,
    coze_podi_plugin,
    tasks,
    notify,
)


def create_app() -> FastAPI:
    app = FastAPI(title="PODI Backend", version="0.1.0")

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
    app.include_router(admin_abilities.router, prefix="/api", tags=["admin-abilities"])
    app.include_router(admin_dashboard.router, prefix="/api", tags=["admin-dashboard"])
    app.include_router(admin_evals.router, prefix="/api/admin", tags=["admin-evals"])
    app.include_router(evals_public.router)
    app.include_router(coze_podi_plugin.router)
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(notify.router, tags=["notify"])
    return app


app = create_app()
