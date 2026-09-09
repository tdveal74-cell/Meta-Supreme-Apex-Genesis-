"""
Read the caller's provider spend for the current UTC day.

Migration 017 gave the estate a durable spend ledger and a hard cap that
refuses at 429, but nothing ever exposed it. The control plane's cost panel
needs a read, so this is that read and nothing more: one GET, no mutation.

Two things this route deliberately does not do.

It does not break spend down by provider, because the table cannot. The
017 ledger is one row per account per UTC day carrying calls, input tokens and
output tokens, with no provider column. A breakdown here would be invented, so
the response says the dimension is unavailable rather than fabricating one.

It does not carry its own copy of the cap. The number comes from the same
setting `refuse_if_capped` reads at call time, so the figure shown can never
drift from the figure enforced.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.security.deps import CurrentUser
from app.services.provider_usage import cap_resets_at, read_usage, utc_today

router = APIRouter(prefix="/usage", tags=["Usage"])


class DailyUsageOut(BaseModel):
    """One account's spend for one UTC day, and where the cap sits."""

    date: str = Field(..., description="The UTC day this window covers, ISO 8601.")
    calls: int = Field(..., description="Provider calls recorded for the day.")
    input_tokens: int
    output_tokens: int
    tokens: int = Field(..., description="Input plus output, the figure the cap measures.")
    cap_tokens: Optional[int] = Field(
        None,
        description=(
            "The daily cap in tokens, read from the same setting the refusal reads. "
            "Null when no cap is configured, in which case nothing refuses on budget."
        ),
    )
    remaining_tokens: Optional[int] = Field(
        None, description="Headroom before the refusal. Null when no cap is configured."
    )
    resets_at: str = Field(..., description="The UTC midnight that opens the next window.")
    providers_available: bool = Field(
        False,
        description=(
            "Whether a per provider breakdown can be served. Always false: the 017 "
            "ledger has no provider column, so the dimension does not exist to report."
        ),
    )


@router.get("", response_model=DailyUsageOut, summary="Today's provider spend for the caller")
async def read_daily_usage(current_user: CurrentUser) -> DailyUsageOut:
    """Return the caller's own spend. An account with no calls reads as zeros.

    Zeros here are a real measurement, not a failed read: a fresh account has
    genuinely spent nothing, and the client can tell the difference because a
    failure is an HTTP error rather than a body full of zeros.
    """
    day = utc_today()
    usage = await read_usage(str(current_user.id), day)
    cap = int(settings.PROVIDER_DAILY_TOKEN_CAP or 0)
    capped = cap > 0

    return DailyUsageOut(
        date=day.isoformat(),
        calls=usage.calls,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        tokens=usage.total_tokens,
        cap_tokens=cap if capped else None,
        remaining_tokens=max(0, cap - usage.total_tokens) if capped else None,
        resets_at=cap_resets_at(day).isoformat(),
        providers_available=False,
    )
