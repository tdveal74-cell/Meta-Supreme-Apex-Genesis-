"""Per-tenant provider spend: the ledger, the cap, and the wrapper that enforces both.

Fix PR 15 from the DEVON and Hermes audit (H15). Every lane that reaches a
provider does so through the provider that `app.services.intelligence`
builds, so that is where the cap lives: `MeteredProvider` wraps whatever
provider is configured, reads the calling account's `provider_usage` row for
the current UTC day before each completion, refuses with a typed 429 once
input plus output tokens have reached `PROVIDER_DAILY_TOKEN_CAP`, and after
each completion upserts what the provider reported. `MeteredEmbeddingProvider`
does the same for embeddings, which carry input tokens only.

Two properties the wrapper guarantees:

- The record is durable whatever happens to the request afterwards. It is
  written in its own short transaction on the engine, not on the request
  session, so a council that fails after nine agents answered still leaves
  nine calls on the ledger, and a request whose session rolls back does not
  take the spend with it.
- The refusal happens before anything is sent. The check reads the ledger;
  it never touches the provider.

The cap is checked before and recorded after, so concurrent calls that all
pass the check can overshoot by at most one completion each. That is the
price of not serializing every provider call on a row lock, and it is
bounded by the concurrency the council allows.

The account comes from `app.core.tenant_context`. A call with no account in
context is spent under the `system` bucket, which is capped like any other:
work the operator's own process does is small, and an uncapped bucket is
exactly where an attribution gap would drain to.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.tenant_context import SYSTEM_TENANT, current_tenant_id
from app.db.session import engine
from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
)
from services.intelligence.providers.embeddings import (
    EmbeddingProvider,
    EmbeddingResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The refusal
# ---------------------------------------------------------------------------


class ProviderSpendCapExceeded(AppError):
    """The account has reached its provider spend cap for the UTC day.

    Deliberately not a ProviderError: the routes translate those into 502
    "provider error", and this is not one. Nothing was sent to the provider.
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        cap: int,
        used: int,
        day: date,
        resets_at: datetime,
    ) -> None:
        self.tenant_id = tenant_id
        self.cap = cap
        self.used = used
        self.day = day
        self.resets_at = resets_at
        retry_after = max(1, int((resets_at - datetime.now(timezone.utc)).total_seconds()))
        self.headers = {"Retry-After": str(retry_after)}
        super().__init__(
            "Provider spend cap reached: this account has used "
            f"{used:,} of {cap:,} tokens on {day.isoformat()} (UTC). "
            f"The cap resets at {resets_at.isoformat()}. "
            "Nothing was sent to the provider.",
            status_code=429,
            code="provider_spend_cap",
        )


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyUsage:
    """One account's provider spend for one UTC day."""

    tenant_id: str
    day: date
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def cap_resets_at(day: date) -> datetime:
    """The UTC midnight that opens the day after `day`."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)


def spend_bucket() -> str:
    """The account the current call is spent against, or the system bucket."""
    return current_tenant_id() or SYSTEM_TENANT


_READ = text(
    "SELECT calls, input_tokens, output_tokens FROM provider_usage "
    "WHERE user_id = :user_id AND usage_day = :usage_day"
)

_UPSERT = text(
    "INSERT INTO provider_usage (user_id, usage_day, calls, input_tokens, output_tokens, updated_at) "
    "VALUES (:user_id, :usage_day, 1, :input_tokens, :output_tokens, NOW()) "
    "ON CONFLICT (user_id, usage_day) DO UPDATE SET "
    "calls = provider_usage.calls + 1, "
    "input_tokens = provider_usage.input_tokens + EXCLUDED.input_tokens, "
    "output_tokens = provider_usage.output_tokens + EXCLUDED.output_tokens, "
    "updated_at = NOW()"
)


async def read_usage(tenant_id: str, day: Optional[date] = None) -> DailyUsage:
    """The account's row for the day, or an empty one when it has not spent yet."""
    usage_day = day or utc_today()
    async with engine.connect() as conn:
        row = (
            await conn.execute(_READ, {"user_id": tenant_id, "usage_day": usage_day})
        ).first()
    if row is None:
        return DailyUsage(tenant_id=tenant_id, day=usage_day)
    return DailyUsage(
        tenant_id=tenant_id,
        day=usage_day,
        calls=int(row.calls),
        input_tokens=int(row.input_tokens),
        output_tokens=int(row.output_tokens),
    )


async def record_usage(
    tenant_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
    day: Optional[date] = None,
) -> None:
    """Add one completion to the account's row for the day. One upsert, its own transaction."""
    async with engine.begin() as conn:
        await conn.execute(
            _UPSERT,
            {
                "user_id": tenant_id,
                "usage_day": day or utc_today(),
                "input_tokens": max(0, int(input_tokens)),
                "output_tokens": max(0, int(output_tokens)),
            },
        )


async def refuse_if_capped(tenant_id: str) -> DailyUsage:
    """Read the day's row and refuse when the cap is already reached.

    Reads the setting at call time so a deployment can change the cap without
    a restart and the suite can drive it through monkeypatching. Returns the
    usage read so a caller that wants to log it does not read twice.
    """
    cap = int(settings.PROVIDER_DAILY_TOKEN_CAP or 0)
    day = utc_today()
    if cap <= 0:
        return DailyUsage(tenant_id=tenant_id, day=day)
    usage = await read_usage(tenant_id, day)
    if usage.total_tokens >= cap:
        logger.warning(
            "provider spend cap reached: tenant=%s used=%d cap=%d day=%s",
            tenant_id, usage.total_tokens, cap, day.isoformat(),
        )
        raise ProviderSpendCapExceeded(
            tenant_id=tenant_id,
            cap=cap,
            used=usage.total_tokens,
            day=day,
            resets_at=cap_resets_at(day),
        )
    return usage


async def _record_or_log(tenant_id: str, *, input_tokens: int, output_tokens: int) -> None:
    """Record, and if the ledger write fails, say so loudly and keep the answer.

    The provider has already been paid by the time this runs; failing the
    request would lose the answer without recovering the spend. A failed
    record under-counts the account by one call, which the log names.
    """
    try:
        await record_usage(tenant_id, input_tokens=input_tokens, output_tokens=output_tokens)
    except Exception:  # noqa: BLE001 - the answer is already paid for
        logger.exception(
            "provider usage not recorded: tenant=%s input=%d output=%d",
            tenant_id, input_tokens, output_tokens,
        )


# ---------------------------------------------------------------------------
# The wrappers
# ---------------------------------------------------------------------------


class MeteredProvider(AIProvider):
    """The configured completion provider, metered and capped per account.

    Presents the inner provider's name and model so `provider.name == "mock"`
    and the status route keep reading the truth. Retries stay inside the
    inner provider's `complete`; one successful completion is one record.
    """

    def __init__(self, inner: AIProvider) -> None:
        super().__init__(
            default_model=inner.default_model,
            timeout_seconds=inner.timeout_seconds,
            max_retries=inner.max_retries,
        )
        self.name = inner.name
        self.inner = inner

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        tenant_id = spend_bucket()
        await refuse_if_capped(tenant_id)
        response = await self.inner.complete(request)
        # Shielded: the provider has already been paid by the time this line
        # runs, so a client that disconnects between the call and the record
        # must not take the record with it.
        await asyncio.shield(
            _record_or_log(
                tenant_id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
        )
        return response

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        # The abstract contract, kept for anything that drives a provider by
        # the single-attempt method. `complete` above is the metered path.
        return await self.inner._complete_once(request)


class MeteredEmbeddingProvider(EmbeddingProvider):
    """The configured embedding provider, metered and capped per account."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        super().__init__(
            default_model=inner.default_model,
            timeout_seconds=inner.timeout_seconds,
            max_retries=inner.max_retries,
        )
        self.name = inner.name
        self.inner = inner

    async def embed(self, texts: List[str]) -> EmbeddingResponse:
        if not texts:
            return await self.inner.embed(texts)
        tenant_id = spend_bucket()
        await refuse_if_capped(tenant_id)
        response = await self.inner.embed(texts)
        await asyncio.shield(
            _record_or_log(tenant_id, input_tokens=response.input_tokens, output_tokens=0)
        )
        return response

    async def _embed_once(self, texts: List[str]) -> EmbeddingResponse:
        return await self.inner._embed_once(texts)
