"""Minimal router for shimmed layout — prefer standalone_api for offline."""
from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/health")
async def health():
    return {"status": "ok", "mode": "shim", "hint": "use standalone_api for full offline surface"}
