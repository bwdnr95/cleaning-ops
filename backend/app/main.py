from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.mount(
        settings.storage_public_base_path,
        StaticFiles(directory=settings.storage_root, check_dir=False),
        name="uploads",
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    _mount_spa(app)

    return app


def _mount_spa(app: FastAPI) -> None:
    """frontend/dist 가 빌드되어 있으면 SPA로 서빙. 없으면 무시 (API-only 모드)."""
    dist_dir = (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist").resolve()
    if not dist_dir.is_dir():
        return

    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str) -> Response:
        if spa_path:
            candidate = (dist_dir / spa_path).resolve()
            try:
                candidate.relative_to(dist_dir)
            except ValueError:
                return Response(status_code=404)
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(dist_dir / "index.html")


app = create_app()
