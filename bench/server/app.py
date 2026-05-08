"""FastAPI app — single port serves /api/* + the built React frontend."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import providers as _providers  # noqa: F401  -- triggers @register_provider
from .. import tasks as _tasks  # noqa: F401          -- triggers @register_task
from ..config import load_config
from .api.models import router as models_router
from .api.results import router as results_router
from .api.runs import router as runs_router
from .api.samples import router as samples_router
from .api.showcase import router as showcase_router


def create_app() -> FastAPI:
    cfg = load_config()
    app = FastAPI(title="Likeness Detector", version="0.1.0")

    app.include_router(runs_router)
    app.include_router(results_router)
    app.include_router(samples_router)
    app.include_router(models_router)
    app.include_router(showcase_router)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/info")
    async def info():
        return {
            "default_benchmark": cfg.engine.default_benchmark,
            "models_available": len(cfg.models),
        }

    web_dist = cfg.web_dist_path()
    assets_dir = web_dist / "assets"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if web_dist.exists():
            target = web_dist / full_path
            if target.is_file():
                return FileResponse(target)
            index = web_dist / "index.html"
            if index.exists():
                return FileResponse(index)
        return JSONResponse(
            {
                "message": "Frontend not built. Run `make build` (or `cd web && npm run build`).",
                "api_root": "/api",
            },
            status_code=200,
        )

    return app


app = create_app()
