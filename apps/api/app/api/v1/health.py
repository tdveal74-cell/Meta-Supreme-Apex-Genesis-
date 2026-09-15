"""
Health monitoring endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "meta-supreme-apex-genesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness probe. Ready means the database answered SELECT 1 through this
    process's session factory on this call; nothing else is checked, and the
    checks block says so rather than reporting a check that never ran.

    Until 2026-09-15 this route returned "ready" unconditionally with two
    checks marked "pending", so a process with a dead database answered ready
    and every database backed route failed after it. Railway probes
    /api/v1/health, the liveness route, so no platform probe keyed on the
    lie; a reader of the JSON did.
    """
    checks = {"database": "unchecked", "ai_providers": "unchecked"}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - any failure to reach the database is not ready
        checks["database"] = f"error: {type(exc).__name__}"
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
