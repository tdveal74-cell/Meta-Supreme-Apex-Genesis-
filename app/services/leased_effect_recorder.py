"""Application-layer EffectRecorder bound to a live task lease."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_effect_receipts import EffectReceiptRepository
from services.agent_runtime.contracts import EffectIntent, EffectReceipt, EffectStatus


class LeasedEffectRecorder:
    """Records intents and receipts under the current execution lease fence.

    The intent must survive a worker crash that happens after the external
    effect ran, or the orphan-intent refusal can never fire and the next
    worker silently re-executes the effect. With a session_factory the intent
    is therefore committed in its own transaction before the adapter runs.
    The receipt stays on the run transaction so it commits atomically with
    the lease-fenced result, and a rollback leaves the durable intent behind
    as the ambiguity marker.
    """

    def __init__(
        self,
        *,
        db: AsyncSession,
        owner_id: str,
        lease_token: str,
        execution_generation: int,
        repository: Optional[EffectReceiptRepository] = None,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
    ) -> None:
        self.db = db
        self.owner_id = owner_id
        self.lease_token = lease_token
        self.execution_generation = execution_generation
        self.repository = repository or EffectReceiptRepository()
        self.session_factory = session_factory

    async def begin_effect(
        self,
        *,
        task_id: str,
        step_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: str,
    ) -> EffectIntent:
        if self.session_factory is None:
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
        async with self.session_factory() as session:
            intent = await self.repository.record_intent(
                session,
                owner_id=self.owner_id,
                task_id=task_id,
                step_id=step_id,
                tool_name=tool_name,
                arguments=arguments,
                idempotency_key=idempotency_key,
                lease_token=self.lease_token,
                execution_generation=self.execution_generation,
            )
            await session.commit()
            return intent

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
