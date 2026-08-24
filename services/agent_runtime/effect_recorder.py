"""Optional effect-recorder protocol for the portable Agent Runtime.

The runtime remains framework-free. When an application-layer recorder is
injected, WRITE / HIGH_IMPACT tool calls write an intent before execution and
a receipt afterward. Without a recorder the runtime behaves exactly as before.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from services.agent_runtime.contracts import EffectIntent, EffectReceipt, EffectStatus


class EffectRecorder(Protocol):
    """Application-supplied boundary for durable effect intents and receipts."""

    async def begin_effect(
        self,
        *,
        task_id: str,
        step_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        idempotency_key: str,
    ) -> EffectIntent: ...

    async def complete_effect(
        self,
        *,
        intent: EffectIntent,
        status: EffectStatus,
        provider_receipt_id: str = "",
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> EffectReceipt: ...
