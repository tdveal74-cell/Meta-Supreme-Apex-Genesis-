"""The Operations and Finance scoreboard.

A pure function over measurements the caller already holds. It never reads a
store and never estimates. A figure that was not measured is None and is
labelled as such, because a plausible invented revenue number is the exact
failure this estate's first law forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.company.functions import TARGET_MONTHLY_USD


@dataclass(frozen=True)
class Scoreboard:
    target_monthly_usd: int
    revenue_month_usd: Optional[float]
    revenue_measured: bool
    gap_to_target_usd: Optional[float]
    pct_of_target: Optional[float]
    spend_calls_today: int
    spend_tokens_today: int
    spend_cap_tokens: Optional[int]
    spend_headroom_tokens: Optional[int]
    cap_pct_used: Optional[float]
    notes: tuple


def build_scoreboard(
    *,
    revenue_month_usd: Optional[float],
    calls_today: int,
    tokens_today: int,
    cap_tokens: Optional[int],
    target_monthly_usd: int = TARGET_MONTHLY_USD,
) -> Scoreboard:
    notes = []
    if revenue_month_usd is None:
        gap = pct = None
        notes.append("Revenue is not connected, so the gap to target is not measured.")
    else:
        if revenue_month_usd < 0:
            raise ValueError("revenue cannot be negative")
        gap = max(0.0, target_monthly_usd - revenue_month_usd)
        pct = round(100.0 * revenue_month_usd / target_monthly_usd, 1)

    if cap_tokens is None or cap_tokens <= 0:
        headroom = used = None
        notes.append("No daily token cap is configured, so nothing refuses on budget.")
    else:
        headroom = max(0, cap_tokens - tokens_today)
        used = round(100.0 * tokens_today / cap_tokens, 1)

    return Scoreboard(
        target_monthly_usd=target_monthly_usd,
        revenue_month_usd=revenue_month_usd,
        revenue_measured=revenue_month_usd is not None,
        gap_to_target_usd=gap,
        pct_of_target=pct,
        spend_calls_today=calls_today,
        spend_tokens_today=tokens_today,
        spend_cap_tokens=cap_tokens if cap_tokens and cap_tokens > 0 else None,
        spend_headroom_tokens=headroom,
        cap_pct_used=used,
        notes=tuple(notes),
    )
