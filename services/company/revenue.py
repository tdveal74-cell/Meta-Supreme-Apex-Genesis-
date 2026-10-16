"""Month revenue from a list of Stripe charges. Pure: no network, no clock, no store.

The caller fetches the charges. This module decides what counts and refuses
anything it cannot count honestly, because a plausible revenue figure that is
wrong is the failure the first law forbids.

What counts: a charge that is paid, has status succeeded, is in USD and is not
refunded. Net revenue for a charge is its amount minus the amount refunded, in
cents. What is refused: any other currency (no conversion is guessed), a charge
without an integer amount, and a refund larger than the charge. A disputed
charge is counted at face value and the reading says so, because the outcome of
a dispute is not known when the charge is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


class RevenueUnreadable(ValueError):
    """The charges cannot be turned into a trustworthy figure."""


@dataclass(frozen=True)
class RevenueReading:
    revenue_usd: float
    charge_count: int
    disputed_count: int
    notes: tuple


def _cents(charge: dict, field: str) -> int:
    value = charge.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RevenueUnreadable(f"charge {charge.get('id', '?')} has no valid {field}")
    return value


def sum_month_revenue(charges: Iterable[dict]) -> RevenueReading:
    total_cents = 0
    counted = 0
    disputed = 0
    uncaptured = 0
    for charge in charges:
        if not isinstance(charge, dict):
            raise RevenueUnreadable("a charge is not an object")
        if charge.get("status") != "succeeded" or charge.get("paid") is not True:
            continue
        if charge.get("captured") is False:
            # An authorization that was never captured holds funds and takes none.
            uncaptured += 1
            continue
        if str(charge.get("currency", "")).lower() != "usd":
            raise RevenueUnreadable(
                f"charge {charge.get('id', '?')} is not in USD; no conversion is guessed"
            )
        amount = _cents(charge, "amount")
        refunded = _cents(charge, "amount_refunded")
        if refunded > amount:
            raise RevenueUnreadable(f"charge {charge.get('id', '?')} refunds more than it took")
        total_cents += amount - refunded
        counted += 1
        if charge.get("disputed") is True:
            disputed += 1
    notes: List[str] = []
    if uncaptured:
        notes.append(f"{uncaptured} uncaptured authorization(s) are not counted as revenue.")
    if disputed:
        notes.append(f"{disputed} disputed charge(s) are counted at face value; dispute outcomes are unknown.")
    return RevenueReading(
        revenue_usd=round(total_cents / 100.0, 2),
        charge_count=counted,
        disputed_count=disputed,
        notes=tuple(notes),
    )
