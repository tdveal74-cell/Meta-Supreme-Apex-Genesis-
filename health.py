"""
Health monitoring endpoints.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check for load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "service": "meta-supreme-apex-genesis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness probe — extend later with DB and dependency checks.
    """
    # TODO: Check database connectivity, Redis, AI provider reachability
    return {
        "status": "ready",
        "checks": {
            "database": "pending",
            "ai_providers": "pending",
        },
    }
