"""Opt-in, authenticated, read-only DEVON ARF shadow diagnostic surface.

This endpoint never runs a task, grants an approval, mutates task state,
claims human review or activates ARF. It updates only rate-limit accounting.
Disabled by default until the operator
approves real evidence-source and access-boundary verification.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.deps import CurrentUser
from app.services.agent_tasks import agent_tasks_service, build_tool_registry
from app.services.arf_declared_gate import RuntimeDeclaredChecksGateReader
from app.services.arf_evidence_source import EvidenceReadRefused, observe_persisted_task
from app.services.arf_shadow_rate_limit import (
    ShadowRateLimitExceeded,
    ShadowRateLimitUnavailable,
    consume_shadow_budget,
)
from services.agent_runtime.reliability.policy import ReliabilityPolicy

router = APIRouter(prefix="/agent-tasks", tags=["ARF Shadow (read-only)"])
_POLICY_PATH = Path(__file__).resolve().parents[3] / "policies/reliability/profiles.v1.json"


def shadow_read_enabled() -> bool:
    """Explicit operator gate; a missing or unknown value is disabled."""
    return os.getenv("ARF_SHADOW_READ_ENABLED", "").strip().lower() in {"1", "true", "yes"}


@router.get("/{task_id}/reliability-shadow")
async def reliability_shadow(
    task_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Read DEVON build diagnostics only; no route to release authorization."""
    if not shadow_read_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    # Authentication's SELECT already opened a transaction on the FastAPI
    # dependency session. Save the trusted owner before rollback expires ORM
    # attributes, then release its checked-out connection before the limiter
    # acquires a separate accounting connection. Never overlap checkouts.
    owner_id = current_user.id
    await db.rollback()
    # Charge by authenticated account before task/evidence queries. Unknown
    # task IDs and rejected evidence cannot bypass or refund the same budget.
    try:
        await consume_shadow_budget(owner_id)
    except ShadowRateLimitExceeded as exc:
        raise HTTPException(
            status_code=429, detail="ARF diagnostic request limit reached",
            headers={"Retry-After": str(exc.retry_after), "Cache-Control": "no-store"},
        ) from exc
    except ShadowRateLimitUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="ARF diagnostic protection unavailable",
            headers={"Retry-After": "2", "Cache-Control": "no-store"},
        ) from exc
    task = await agent_tasks_service.get_task(db, owner_id=owner_id, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # End the preliminary owner lookup before beginning a new read-only,
    # repeatable-read snapshot on the SAME dependency session. This releases
    # the checkout rather than holding one connection idle while requesting
    # a second connection from the bounded pool.
    await db.rollback()
    try:
        policy = ReliabilityPolicy.from_json(_POLICY_PATH)
        result = await observe_persisted_task(
            db=db,
            approval_db=None,  # No verified cross-database approval snapshot.
            owner_id=owner_id,
            task_id=task_id,
            domain="devon",
            workflow_stage="build",
            policy=policy,
            tool_registry=build_tool_registry(),
            gate_reader=RuntimeDeclaredChecksGateReader(db),
        )
    except EvidenceReadRefused as exc:
        # Never leak another tenant's task IDs or underlying DB details.
        raise HTTPException(status_code=409, detail="ARF evidence reconciliation refused") from exc
    return result.to_dict()
