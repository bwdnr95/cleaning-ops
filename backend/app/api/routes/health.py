"""헬스 체크.

Railway / Vercel 등의 healthcheck가 부드럽게 200/503 받도록.
- /api/health: 가벼운 ping (DB+storage 확인 없음, 로드밸런서용)
- /api/health/ready: DB 연결·storage 라이트 체크 (배포 직후 readiness)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal

router = APIRouter()


@router.get("", tags=["health"])
def liveness() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready", tags=["health"])
def readiness(response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}
    ok = True

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - 헬스체크는 모든 예외를 흡수
        checks["database"] = f"error: {type(exc).__name__}"
        ok = False

    storage_provider = settings.storage_provider.strip().lower()
    if storage_provider == "local":
        checks["storage"] = "local"
    elif storage_provider == "s3":
        # 런타임에 객체 PUT 까지 검사하면 비용/지연이 크므로 설정 충분 여부만 검사.
        if not settings.s3_bucket or not settings.s3_public_base_url:
            checks["storage"] = "error: s3 not configured"
            ok = False
        else:
            checks["storage"] = "configured"
    else:
        checks["storage"] = f"unknown: {storage_provider}"
        ok = False

    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if ok else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": checks,
    }
