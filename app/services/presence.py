"""Bounded, authenticated Presence completions on the API's existing ledger.

A socket's TTFT timeout or disconnect abandons its wait, not the paid call's
accounting. A strong task reference survives the HTTP request. Clean shutdown
drains these tasks; a process kill or provider timeout remains an unknown
provider outcome and is never reported as accepted or retried automatically.
"""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.tenant_context import bind_tenant, reset_tenant
from app.services.provider_usage import MeteredProvider
from services.intelligence.presence import PRESENCE_MAX_OUTPUT_TOKENS, PRESENCE_SYSTEM_PROMPT
from services.intelligence.providers import AIProvider, create_provider
from services.intelligence.providers.base import ChatMessage, CompletionRequest, CompletionResponse

logger = logging.getLogger(__name__)

MAX_PENDING_COMPLETIONS = 32
COMPLETION_DEADLINE_SECONDS = 45.0
SHUTDOWN_DRAIN_SECONDS = 50.0
_pending: set[asyncio.Task[CompletionResponse]] = set()
_accepting = True


@lru_cache
def get_presence_provider() -> AIProvider:
    """Same configured provider and model as the API, zero retries, strict ledger."""
    name = settings.DEFAULT_AI_PROVIDER
    model = settings.AI_MODEL or (
        settings.GEMINI_MODEL if name == "gemini"
        else settings.CEREBRAS_MODEL if name == "cerebras"
        else settings.OPENAI_MODEL if name == "openai"
        else settings.ANTHROPIC_MODEL if name == "anthropic"
        else None
    )
    inner = create_provider(
        name,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        cerebras_api_key=settings.CEREBRAS_API_KEY,
        gemini_api_key=settings.GEMINI_API_KEY,
        model=model,
        timeout_seconds=min(settings.AI_TIMEOUT_SECONDS, 30.0),
        max_retries=0,
    )
    return MeteredProvider(inner, strict_recording=True)


def start_accepting() -> None:
    global _accepting
    _accepting = True


def _finished(task: asyncio.Task[CompletionResponse]) -> None:
    _pending.discard(task)
    if task.cancelled():
        logger.error("presence completion cancelled; provider usage may be unconfirmed")
        return
    error = task.exception()
    if error is not None:
        # Never log the prompt, token, provider body or arbitrary exception text.
        logger.warning("presence completion ended without acceptance: %s", type(error).__name__)


async def _complete(provider: AIProvider, request: CompletionRequest) -> CompletionResponse:
    try:
        return await asyncio.wait_for(
            provider.complete(request), timeout=COMPLETION_DEADLINE_SECONDS
        )
    except asyncio.TimeoutError:
        raise AppError(
            "Presence inference timed out; provider usage is unconfirmed. No automatic retry.",
            status_code=504, code="presence_usage_unconfirmed",
        ) from None


async def complete_presence(
    *, owner_id: str, provider_name: str, prompt: str
) -> CompletionResponse:
    if not _accepting or len(_pending) >= MAX_PENDING_COMPLETIONS:
        raise AppError(
            "Presence completion capacity is unavailable; nothing was sent.",
            status_code=429, code="presence_capacity",
        )
    provider = get_presence_provider()
    if provider_name != provider.name:
        raise AppError(
            "Presence provider differs from the API's configured provider; nothing was sent.",
            status_code=409, code="presence_provider_mismatch",
        )
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content=prompt)],
        system=PRESENCE_SYSTEM_PROMPT,
        max_tokens=PRESENCE_MAX_OUTPUT_TOKENS,
        temperature=0.4,
        metadata={"component": "devon-presence"},
    )
    # Bind only the authenticated DB user's id. Context is copied into the task
    # and remains stable when its request ends or another tenant calls.
    binding = bind_tenant(owner_id)
    try:
        task = asyncio.create_task(_complete(provider, request), name="presence-completion")
    finally:
        reset_tenant(binding)
    _pending.add(task)
    task.add_done_callback(_finished)
    return await asyncio.shield(task)


async def drain_completions() -> None:
    """Stop admissions and wait for bounded accepted work before API shutdown."""
    global _accepting
    _accepting = False
    if not _pending:
        return
    _, pending = await asyncio.wait(set(_pending), timeout=SHUTDOWN_DRAIN_SECONDS)
    if pending:
        logger.error(
            "presence shutdown left %d completion(s) with unconfirmed usage", len(pending)
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
