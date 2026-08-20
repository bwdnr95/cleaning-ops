from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.middleware import CustomerAsRequestBodyLimitMiddleware, SecurityHeadersMiddleware
from app.core.observability import (
    RequestIDMiddleware,
    configure_structlog,
    init_sentry,
)
from app.services.lifespan import app_lifespan


def create_app() -> FastAPI:
    init_sentry(settings)
    configure_structlog(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=app_lifespan,
    )
    if settings.storage_provider.strip().lower() == "local":
        app.mount(
            settings.storage_public_base_path,
            StaticFiles(directory=settings.storage_root, check_dir=False),
            name="uploads",
        )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CustomerAsRequestBodyLimitMiddleware)

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


class _ImmutableAssets(StaticFiles):
    """해시 파일명 자산은 영구 캐시. 내용이 바뀌면 파일명이 바뀌므로 stale이 될 수 없다."""

    def is_not_modified(self, response_headers, request_headers) -> bool:  # type: ignore[override]
        response_headers.setdefault("cache-control", _IMMUTABLE_CACHE)
        return super().is_not_modified(response_headers, request_headers)

    async def get_response(self, path: str, scope) -> Response:  # type: ignore[override]
        response = await super().get_response(path, scope)
        response.headers.setdefault("cache-control", _IMMUTABLE_CACHE)
        return response


_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
# index.html은 항상 재검증한다. 이 파일이 캐시되면 배포 후에도 옛 청크 해시를 계속
# 물고 있어(터널/브라우저 캐시) 운영자가 "고쳤는데 화면이 그대로"를 겪는다.
_NO_CACHE = "no-cache, no-store, must-revalidate"


def _mount_spa(app: FastAPI) -> None:
    """frontend/dist 가 빌드되어 있으면 SPA로 서빙. 없으면 무시 (API-only 모드)."""
    dist_dir = (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist").resolve()
    if not dist_dir.is_dir():
        return

    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", _ImmutableAssets(directory=str(assets_dir)), name="spa-assets")

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_fallback(spa_path: str) -> Response:
        if spa_path:
            candidate = (dist_dir / spa_path).resolve()
            try:
                candidate.relative_to(dist_dir)
            except ValueError:
                return Response(status_code=404)
            if candidate.is_file():
                return FileResponse(candidate, headers={"cache-control": _NO_CACHE})
        return FileResponse(dist_dir / "index.html", headers={"cache-control": _NO_CACHE})


app = create_app()
