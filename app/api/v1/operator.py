"""Authenticated execution surface for the DEVON Operator Bridge.

DEVON itself remains execution-free. This router owns the separate capability
boundary and consults DEVON's approval queue before any mutating command runs.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.devon import _queue as approvals
from services.operator.bridge import OperatorBridge, OperatorError, Risk

router = APIRouter(prefix="/operator", tags=["DEVON Operator"])
_bridge = OperatorBridge()


def _authorize(key: Optional[str]) -> None:
    try:
        _bridge.authenticate(key)
    except OperatorError as exc:
        message = str(exc)
        status = 503 if "disabled" in message or "not configured" in message else 401
        raise HTTPException(status_code=status, detail=message) from exc


class CommandBody(BaseModel):
    command: str = Field(..., min_length=1, max_length=4000)
    cwd: Optional[str] = None
    timeout_seconds: int = Field(default=60, ge=1, le=300)


class ExecuteBody(BaseModel):
    request_id: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=60, ge=1, le=300)


@router.get("/status")
async def operator_status() -> Dict[str, Any]:
    """Configuration state only. Never returns the operator key."""
    return {
        "name": "DEVON Operator Bridge",
        "enabled": _bridge.enabled,
        "configured": _bridge.configured,
        "root": str(_bridge.root),
        "devon_core_executes": False,
        "boundary": (
            "DEVON plans and gates. The Operator Bridge confines the working directory "
            "to the configured root. Approved commands still run with the API process "
            "user's operating-system permissions."
        ),
    }


@router.post("/command")
async def operator_command(
    body: CommandBody,
    x_devon_operator_key: Optional[str] = Header(default=None, alias="X-Devon-Operator-Key"),
) -> Dict[str, Any]:
    """Run a read-only command or raise a DEVON approval for a mutating one."""
    _authorize(x_devon_operator_key)

    try:
        plan = _bridge.plan(body.command, body.cwd)
        if plan.risk is Risk.BLOCKED:
            raise HTTPException(status_code=403, detail=plan.reason)

        if plan.risk is Risk.READ:
            result = _bridge.execute_read(plan, body.timeout_seconds)
            return {
                "state": "completed",
                "plan": plan.to_dict(),
                "result": result.to_dict(),
            }

        request_id, token = _bridge.request(plan, approvals)
        return {
            "state": "approval_required",
            "plan": plan.to_dict(),
            "approval": {
                "request_id": request_id,
                "token": token,
                "decision_endpoint": "/api/v1/devon/approvals/decide",
                "execute_endpoint": "/api/v1/operator/execute",
                "note": "The token is returned once and is consumed by the DEVON approval decision.",
            },
        }
    except HTTPException:
        raise
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute")
async def execute_approved(
    body: ExecuteBody,
    x_devon_operator_key: Optional[str] = Header(default=None, alias="X-Devon-Operator-Key"),
) -> Dict[str, Any]:
    """Execute one already-approved command. Each request id is single-use."""
    _authorize(x_devon_operator_key)

    try:
        result = _bridge.execute_approved(
            body.request_id,
            approvals,
            body.timeout_seconds,
        )
        return {
            "state": "completed",
            "request_id": body.request_id,
            "result": result.to_dict(),
        }
    except OperatorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
