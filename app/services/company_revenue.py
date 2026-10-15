"""Read this month's revenue from Stripe for the scoreboard. Read only.

The deployed API cannot use the Claude connector, so it reads with its own
restricted key, STRIPE_READ_KEY. Only a live restricted key (rk_live_) is
accepted: an unrestricted secret key or a test key is refused by name, so the
scoreboard can neither move money nor report sandbox money as revenue. Any
failure returns not measured with a reason. It never returns zero for a read
that did not happen, and the key never appears in a note or a log line.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

import httpx

from app.core.config import settings
from services.company.revenue import RevenueUnreadable, sum_month_revenue

CHARGES_URL = "https://api.stripe.com/v1/charges"
PAGE_LIMIT = 100
MAX_PAGES = 20
TIMEOUT_S = 10.0


def month_start(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


async def read_month_revenue(
    now: Optional[datetime] = None,
    *,
    key: Optional[str] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Tuple[Optional[float], List[str]]:
    """Return (revenue_usd or None, notes). None means not measured."""
    key = key if key is not None else getattr(settings, "STRIPE_READ_KEY", None)
    if not key:
        return None, ["Revenue is not connected: STRIPE_READ_KEY is not set."]
    if not key.startswith("rk_live_"):
        return None, ["Revenue is not measured: STRIPE_READ_KEY must be a live restricted key (rk_live_)."]

    now = now or datetime.now(timezone.utc)
    since = month_start(now)
    charges: List[dict] = []
    params = {"limit": PAGE_LIMIT, "created[gte]": int(since.timestamp())}
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_S, transport=transport, headers={"Authorization": f"Bearer {key}"}
        ) as client:
            for _ in range(MAX_PAGES):
                resp = await client.get(CHARGES_URL, params=params)
                if resp.status_code != 200:
                    return None, [f"Revenue is not measured: Stripe answered HTTP {resp.status_code}."]
                body = resp.json()
                page = body.get("data")
                if not isinstance(page, list):
                    return None, ["Revenue is not measured: Stripe returned an unreadable page."]
                charges.extend(page)
                if not body.get("has_more"):
                    break
                if not page or not isinstance(page[-1], dict) or not page[-1].get("id"):
                    return None, ["Revenue is not measured: Stripe pagination was unreadable."]
                params = {**params, "starting_after": page[-1]["id"]}
            else:
                return None, [f"Revenue is not measured: more than {MAX_PAGES * PAGE_LIMIT} charges this month."]
    except (httpx.HTTPError, ValueError):
        return None, ["Revenue is not measured: the Stripe read failed."]

    try:
        reading = sum_month_revenue(charges)
    except RevenueUnreadable as exc:
        return None, [f"Revenue is not measured: {exc}."]
    notes = [
        f"Revenue read from Stripe (live): {reading.charge_count} paid charge(s) since "
        f"{since.date().isoformat()} UTC.",
        *reading.notes,
    ]
    return reading.revenue_usd, notes
