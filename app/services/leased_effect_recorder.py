"""Application-layer EffectRecorder bound to a live task lease."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_effect_receipts import EffectReceiptRepository
from services.agent_runtime.contracts import EffectIntent, EffectReceipt, EffectStatus


class LeasedEffectRecorder:
    """Records intents and receipts under the current execution lease fence."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        owner_id: str,
        lease_token: str,
        execution_generation: int,
        repository: Optional[EffectReceiptRepository] = None,
    ) -> None:
        self.db = db
        self.owner_id = owner_id
        self.lease_token = lease_token
        self.execution_generation = execution_generation
        self.repository = repository or EffectReceiptRepository()

    async def begin_effect(
        self,
        *,
        task_id: str,
        step_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: str,
    ) -> EffectIntent:
        return await self.repository.record_intent(
            self.db,
            owner_id=self.owner_id,
            task_id=task_id,
            step_id=step_id,
            tool_name=tool_name,
            arguments=arguments,
            idempotency_key=idempotency_key,
            lease_token=self.lease_token,
            execution_generation=self.execution_generation,
        )

    async def complete_effect(
        self,
        *,
        intent: EffectIntent,
        status: EffectStatus,
        provider_receipt_id: str = "",
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> EffectReceipt:
        return await self.repository.record_receipt(
            self.db,
            owner_id=self.owner_id,
            task_id=intent.task_id,
            intent_id=intent.intent_id,
            status=status,
            provider_receipt_id=provider_receipt_id,
            raw_response=raw_response,
            lease_token=self.lease_token,
            execution_generation=self.execution_generation,
        )
