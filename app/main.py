"""
Meta Supreme Apex Genesis — API Entry Point
"""

import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

    # Say what the CORS allowlist will actually accept. On 2026-08-27 every
    # browser call from the Command Center failed and nothing in any log named
    # the allowed origins, so diagnosing it meant reading Railway's HTTP stream
    # and inferring the cause from a 400 on a preflight.
    from app.core.cors import log_cors_configuration

    log_cors_configuration(log, settings.CORS_ORIGINS, settings.ENVIRONMENT)

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
        "console": "/console",
        "phase": "6-soul",
    }


# I serve the Loop HUD same-origin at GET /console so remember / file a ruling /
# find hit /api/v1/soul on this host with the CurrentUser JWT. CORS is not
# this path. The newest SYS_OPS console in the assets folder wins, and that
# file is kept byte-identical to deploy/soul/console.html. The unwired v8
# asset is superseded. devon-soul.vercel.app still cannot persist.
_CONSOLE_DIR = Path(__file__).resolve().parent.parent / "docs" / "devon" / "assets"


def _newest_console() -> Optional[Path]:
    def _version(page: Path) -> int:
        match = re.search(r"_v(\d+)_", page.name)
        return int(match.group(1)) if match else 0

    candidates = [
        p
        for p in _CONSOLE_DIR.glob("SYS_OPS_devon-console_v*.html")
        if not p.name.startswith("SUPERSEDED_")
    ]
    # max by numeric version, not lexical sort: v10 must beat v4.
    return max(candidates, key=_version, default=None)


@app.get("/console", include_in_schema=False)
async def console():
    page = _newest_console()
    if page is None:
        raise HTTPException(status_code=404, detail="No console asset found")
    return FileResponse(page, media_type="text/html")
