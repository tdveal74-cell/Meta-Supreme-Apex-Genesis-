"""The estate owner's authenticated, metadata-only n8n inventory door."""

from fastapi import APIRouter, HTTPException

from app.security.deps import CurrentUser
from app.services.n8n_inventory import InventoryAccessError, read_inventory

router = APIRouter(prefix="/n8n", tags=["n8n Inventory"])


@router.get("/workflows")
async def workflow_inventory(current_user: CurrentUser) -> dict:
    try:
        return await read_inventory(str(current_user.id))
    except InventoryAccessError as exc:
        raise HTTPException(
            status_code=503 if exc.state == "disabled" else 403,
            detail=str(exc),
        ) from None
