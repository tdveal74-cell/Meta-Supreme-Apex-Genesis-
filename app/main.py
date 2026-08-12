"""
Meta Supreme Apex Genesis — API Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    setup_logging()

    # Seed the agents table from the canonical registry (idempotent).
    # Failure is logged loudly but does not block startup — /health/ready
    # reports database availability, and seeding retries on demand.
    import logging

    from app.db.session import AsyncSessionLocal
    from app.services.intelligence import seed_agents

    log = logging.getLogger(__name__)

    try:
        async with AsyncSessionLocal() as session:
            await seed_agents(session)
            await session.commit()
        log.info("agent registry seeded")
    except Exception:  # noqa: BLE001 — startup must surface, not mask, DB issues
        log.exception("could not seed agent registry at startup; will retry on demand")

    # Reconcile runs orphaned by a previous process's death. Startup is the
    # right moment: this process's own predecessor is the likeliest cause,
    # and a restart is exactly when the damage becomes visible.
    if settings.WORKFLOW_SWEEP_ON_STARTUP:
        try:
            from app.services.maintenance import sweep_orphaned_runs

            async with AsyncSessionLocal() as session:
                swept = await sweep_orphaned_runs(
                    session,
                    older_than_minutes=settings.WORKFLOW_ORPHAN_TIMEOUT_MINUTES,
                )
                await session.commit()
            if swept:
                log.warning("startup sweep failed %d orphaned workflow run(s)", swept)
        except Exception:  # noqa: BLE001 — never block startup on maintenance
            log.exception("orphaned-run sweep failed; runs may remain stuck")

    yield
    # Shutdown: close connections gracefully


app = FastAPI(
    title="Meta Supreme Apex Genesis",
    description="Intelligence Operating System API",
    version="0.1.0",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# Consistent JSON error responses
register_exception_handlers(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount versioned API
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": "Meta Supreme Apex Genesis",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/api/docs",
        "phase": "5-workflows",
    }
