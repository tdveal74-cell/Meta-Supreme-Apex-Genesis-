"""Helpers for adapter-level durable effect intents and receipts.

These helpers are framework-free and sit beside the existing contracts.
They do not perform I/O. Persistence and lease fencing live in the
application layer that already owns multi-worker execution.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any, Dict, Mapping

from services.agent_runtime.contracts import (
    EffectIntent,
    EffectReceipt,
    EffectStatus,
)


def arguments_hash(arguments: Mapping[str, Any]) -> str:
    """Stable SHA-256 over a canonical JSON encoding of the tool arguments."""
    payload = json.dumps(
        dict(arguments),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def new_intent_id() -> str:
    return f"EI-{secrets.token_hex(8).upper()}"


def build_effect_intent(
    *,
    task_id: str,
    step_id: str,
    tool_name: str,
    arguments: Mapping[str, Any],
    idempotency_key: str,
) -> EffectIntent:
    return EffectIntent(
        intent_id=new_intent_id(),
        task_id=task_id,
        step_id=step_id,
        tool_name=tool_name,
        arguments_hash=arguments_hash(arguments),
        idempotency_key=idempotency_key,
    )


def build_effect_receipt(
    *,
    intent_id: str,
    status: EffectStatus,
    provider_receipt_id: str = "",
    raw_response: Dict[str, Any] | None = None,
) -> EffectReceipt:
    return EffectReceipt(
        intent_id=intent_id,
        status=status,
        provider_receipt_id=provider_receipt_id or "",
        raw_response=dict(raw_response or {}),
    )


def sanitize_receipt_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Strip known sensitive keys before a receipt is persisted."""
    blocked = {
        "approval_token",
        "token",
        "access_token",
        "password",
        "secret",
        "api_key",
        "authorization",
    }
    return {
        str(key): value
        for key, value in dict(payload).items()
        if str(key).lower() not in blocked
    }
