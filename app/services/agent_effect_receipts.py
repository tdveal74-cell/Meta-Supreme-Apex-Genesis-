"""Durable effect intent and receipt persistence for DEVON Agent Runtime.

Lives in the application layer. Does not move execution into services.devon.
All writes are fenced by the live task lease token and execution generation so
a stale worker cannot record a receipt for a lease it no longer owns.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_runtime import (
    AgentEffectIntentRecord,
    AgentEffectReceiptRecord,
    AgentTaskRecord,
)
from services.agent_runtime.contracts import (
    AmbiguousOutcome,
    EffectIntent,
    EffectReceipt,
    EffectStatus,
)


def arguments_hash(arguments: Dict[str, Any]) -> str:
    payload = json.dumps(arguments or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def new_intent_id() -> str:
    return f"INT-{secrets.token_hex(8).upper()}"


class EffectReceiptRepository:
    """Owner-scoped, lease-fenced intent and receipt storage."""

    async def record_intent(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        step_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: str,
        lease_token: str,
        execution_generation: int,
    ) -> EffectIntent:
        """Write an intent only while this worker still owns the task lease."""
        now = datetime.now(timezone.utc)
        # Fence: the live lease token must still match.
        task_result = await db.execute(
            select(AgentTaskRecord).where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
                AgentTaskRecord.lease_token == lease_token,
                AgentTaskRecord.execution_generation == execution_generation,
            )
        )
        if task_result.scalar_one_or_none() is None:
            raise RuntimeError(
                "effect intent refused: task lease token or generation no longer matches"
            )

        intent_id = new_intent_id()
        arg_hash = arguments_hash(arguments)
        row = AgentEffectIntentRecord(
            id=f"EIR-{secrets.token_hex(8).upper()}",
            intent_id=intent_id,
            task_id=task_id,
            owner_id=owner_id,
            step_id=step_id,
            tool_name=tool_name,
            arguments_hash=arg_hash,
            idempotency_key=idempotency_key,
            execution_generation=execution_generation,
            lease_token=lease_token,
            created_at=now,
        )
        db.add(row)
        await db.flush()
        return EffectIntent(
            intent_id=intent_id,
            task_id=task_id,
            step_id=step_id,
            tool_name=tool_name,
            arguments_hash=arg_hash,
            idempotency_key=idempotency_key,
            created_at=now,
        )

    async def record_receipt(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
        intent_id: str,
        status: EffectStatus,
        provider_receipt_id: str = "",
        raw_response: Optional[Dict[str, Any]] = None,
        lease_token: str,
        execution_generation: int,
    ) -> EffectReceipt:
        """Write a receipt only while this worker still owns the task lease."""
        now = datetime.now(timezone.utc)
        task_result = await db.execute(
            select(AgentTaskRecord).where(
                AgentTaskRecord.id == task_id,
                AgentTaskRecord.owner_id == owner_id,
                AgentTaskRecord.lease_token == lease_token,
                AgentTaskRecord.execution_generation == execution_generation,
            )
        )
        if task_result.scalar_one_or_none() is None:
            raise RuntimeError(
                "effect receipt refused: task lease token or generation no longer matches"
            )

        # Intent must exist for this owner/task.
        intent_result = await db.execute(
            select(AgentEffectIntentRecord).where(
                AgentEffectIntentRecord.owner_id == owner_id,
                AgentEffectIntentRecord.task_id == task_id,
                AgentEffectIntentRecord.intent_id == intent_id,
            )
        )
        if intent_result.scalar_one_or_none() is None:
            raise KeyError(f"unknown effect intent: {intent_id}")

        safe_response = dict(raw_response or {})
        # Never persist one-time approval credentials.
        if "approval_token" in safe_response:
            safe_response["approval_token"] = None

        row = AgentEffectReceiptRecord(
            id=f"ERR-{secrets.token_hex(8).upper()}",
            intent_id=intent_id,
            task_id=task_id,
            owner_id=owner_id,
            status=status.value,
            provider_receipt_id=provider_receipt_id or "",
            raw_response=safe_response,
            execution_generation=execution_generation,
            lease_token=lease_token,
            recorded_at=now,
        )
        db.add(row)
        await db.flush()
        return EffectReceipt(
            intent_id=intent_id,
            status=status,
            provider_receipt_id=provider_receipt_id or "",
            raw_response=safe_response,
            recorded_at=now,
        )

    async def find_orphan_intents(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        task_id: str,
    ) -> List[AmbiguousOutcome]:
        """Return intents that have no matching receipt (ambiguous after crash)."""
        intent_rows = await db.execute(
            select(AgentEffectIntentRecord).where(
                AgentEffectIntentRecord.owner_id == owner_id,
                AgentEffectIntentRecord.task_id == task_id,
            )
        )
        intents = list(intent_rows.scalars().all())
        if not intents:
            return []

        receipt_rows = await db.execute(
            select(AgentEffectReceiptRecord.intent_id).where(
                AgentEffectReceiptRecord.owner_id == owner_id,
                AgentEffectReceiptRecord.task_id == task_id,
            )
        )
        received = {row[0] for row in receipt_rows.all()}

        orphans: List[AmbiguousOutcome] = []
        for row in intents:
            if row.intent_id in received:
                continue
            intent = EffectIntent(
                intent_id=row.intent_id,
                task_id=row.task_id,
                step_id=row.step_id,
                tool_name=row.tool_name,
                arguments_hash=row.arguments_hash,
                idempotency_key=row.idempotency_key,
                created_at=row.created_at,
            )
            orphans.append(AmbiguousOutcome(intent=intent))
        return orphans
