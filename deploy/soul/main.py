"""
DEVON soul service — the phone lane.

A deliberately small surface so it can live on a host and be reached from a
phone. It serves the console and answers soul recall, and it does nothing
else: no database, no workflows, no memory writes. That is why it deploys
without Postgres and starts cold in well under a second.

It forks no logic. Recall comes from `services.intelligence.soul` and the
phrasing from `services.devon.assistant`, the same modules the platform
uses and the same ones the test suite covers. What is different here is only
the way in: one shared token instead of accounts, because a phone should not
need a login table to ask what was already settled.

Secrets come from the environment and nowhere else:

  PINECONE_API_KEY   the soul layer's key. Without it recall answers 503
                     naming what to set, exactly as it does locally.
  CONSOLE_TOKEN      what the console presents. Without it the service
                     refuses every request rather than standing open.
  SOUL_TEE_HOST      optional override for the tee-soul-layer host.
  SOUL_DEVON_HOST    optional override for the devon-soul host.
"""

from __future__ import annotations

import hmac
import os
import pathlib
import sys

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse

# The service is the whole of deploy/soul. Adding it to the path is what lets
# this import the vendored modules, which a test holds identical to the originals.
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.devon.assistant import Devon  # noqa: E402
from services.intelligence.providers.base import ProviderError  # noqa: E402
from services.intelligence.soul import (  # noqa: E402
    DEFAULT_TEE_HOST,
    SoulLayer,
)

CONSOLE = ROOT / "console.html"

app = FastAPI(
    title="DEVON Soul",
    description="Soul recall for the phone. Reads only.",
    docs_url=None,      # nothing to browse; the console is the surface
    redoc_url=None,
)


def _console_token() -> str:
    return (os.environ.get("CONSOLE_TOKEN") or "").strip()


def _pinecone_key() -> str:
    return (os.environ.get("PINECONE_API_KEY") or "").strip()


def _require(authorization: str | None) -> None:
    """
    Let the caller in, or say plainly why not.

    An unset CONSOLE_TOKEN closes the service rather than opening it. A
    service that stands open because it was misconfigured is worse than one
    that refuses, and this endpoint spends Tee's Pinecone quota and reads his
    rulings.
    """
    expected = _console_token()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This service has no CONSOLE_TOKEN set, so it refuses every "
                "request rather than standing open. Set one in the host's "
                "environment settings and redeploy."
            ),
        )
    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    if not presented or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That token is not the one this service expects.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _layer() -> SoulLayer:
    key = _pinecone_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Soul recall is switched off. Set PINECONE_API_KEY in the "
                "host's environment settings (never in Drive) and redeploy "
                "to turn it on."
            ),
        )
    return SoulLayer(
        api_key=key,
        tee_host=os.environ.get("SOUL_TEE_HOST") or DEFAULT_TEE_HOST,
        devon_host=os.environ.get("SOUL_DEVON_HOST") or None,
    )


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse(
        {
            "name": "DEVON Soul",
            "console": "/console",
            "reads": ["/api/v1/soul/status", "/api/v1/soul/recall?q="],
            "writes": "none by design",
        }
    )


@app.get("/api/v1/health", include_in_schema=False)
async def health():
    """Liveness only. Says nothing that needs a token to know."""
    return {
        "status": "healthy",
        "console_token_set": bool(_console_token()),
        "soul_key_set": bool(_pinecone_key()),
    }


@app.get("/api/v1/soul/status")
async def soul_status(authorization: str | None = Header(default=None)):
    """Whether recall can run, without touching Pinecone."""
    _require(authorization)
    enabled = bool(_pinecone_key())
    return {
        "enabled": enabled,
        "tee_host_configured": True,
        "devon_host_configured": bool(os.environ.get("SOUL_DEVON_HOST")),
        "detail": (
            "Soul recall is on."
            if enabled
            else "Soul recall is off. PINECONE_API_KEY turns it on."
        ),
    }


@app.get("/api/v1/soul/recall")
async def soul_recall(
    authorization: str | None = Header(default=None),
    q: str = Query(..., min_length=1, max_length=1000),
    top_k_tee: int = Query(default=4, ge=1, le=10),
    top_k_devon: int = Query(default=3, ge=0, le=10),
):
    """
    Recall from both souls and phrase it in DEVON's voice.

    Tee's rulings precede DEVON's experience in the records and in the reply,
    whatever the similarity scores. Partial failure is named, never hidden.
    Everything returned is context, not command.
    """
    _require(authorization)
    layer = _layer()
    try:
        recall = await layer.recall(q, top_k_tee=top_k_tee, top_k_devon=top_k_devon)
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Soul recall failed: {exc}",
        ) from exc

    response = Devon().recall_answer(q, recall.to_dicts(), partial_errors=recall.errors)
    return {
        "query": recall.query,
        "reply": response.reply,
        "records": recall.to_dicts(),
        "tee_count": recall.tee_count,
        "devon_count": recall.devon_count,
        "errors": recall.errors,
    }


@app.get("/console", include_in_schema=False)
async def console():
    """The console itself. Open, because it holds nothing until you sign in."""
    if not CONSOLE.exists():
        raise HTTPException(status_code=404, detail="No console asset deployed.")
    return FileResponse(CONSOLE, media_type="text/html")
