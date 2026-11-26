"""The risk bot: one open position, one snapshot, at most one exit decision.

Source lines: 60 (first take, never average down, the trailing rest), 63
(stop, dead money, pulled liquidity, dev sold, venue warning) and 73 (the RED
figures: take at 1.5 times, trail, 90 minute time stop). SPEC.md section
"risk.py" is the contract.

INVENTED, per SPEC.md: the green trail figure (``trail_green_pct``), the
liquidity pull drop (``liquidity_pull_drop_pct``).

``evaluate`` is pure. It never mutates the position or the snapshot, never
changes ``qty`` or ``cost_usd``, and reads no clock: time is ``snap.ts``. The
caller applies a fill with ``positions.apply_exit_fill``.
"""
from __future__ import annotations

from dataclasses import replace

from .model import ExitDecision, ExitReason, Mode, Position, TokenSnapshot
from .settings import Settings


def evaluate(
    position: Position, snap: TokenSnapshot, mode: Mode, settings: Settings,
) -> tuple[Position, ExitDecision | None]:
    """Bring the peak and stop up to date, then return at most one exit.

    Raises ValueError when the snapshot is for another mint. With no price the
    position comes back unchanged and there is no decision; the caller records
    an alert.
    """
    if snap.mint != position.mint:
        raise ValueError(f"snapshot mint {snap.mint!r} is not the position's mint {position.mint!r}")
    price = snap.price_usd
    if price is None:
        return position, None

    peak = max(position.peak_price, price)
    stop = position.stop_price
    if position.took_first_take:
        trail = settings.trail_red_pct if mode is Mode.RED else settings.trail_green_pct
        stop = max(stop, peak * (1 - trail / 100))
    updated = replace(position, peak_price=peak, stop_price=stop)

    def exit_(reason: ExitReason, fraction: float, detail: str) -> tuple[Position, ExitDecision]:
        return updated, ExitDecision(mint=position.mint, reason=reason, fraction=fraction, detail=detail)

    # 1. stop or trail
    if price <= stop:
        reason = ExitReason.TRAIL if position.took_first_take else ExitReason.STOP
        return exit_(reason, 1.0, f"price {price:.8g} <= stop {stop:.8g}")

    # 2. venue warning
    warning = snap.venue_warning
    if isinstance(warning, str) and warning != "":
        return exit_(ExitReason.VENUE_WARNING, 1.0, "venue warning present")

    # 3. dev sold since entry
    if snap.dev_has_sold is True and position.entry_snapshot.dev_has_sold is not True:
        return exit_(ExitReason.DEV_SOLD, 1.0, "dev has sold since entry")

    # 4. liquidity pulled
    liq = snap.liquidity_usd
    if liq is not None:
        if liq < settings.liquidity_floor_usd:
            return exit_(
                ExitReason.LIQUIDITY_PULLED, 1.0,
                f"liquidity {liq:.2f} < floor {settings.liquidity_floor_usd:.2f}",
            )
        if position.entry_liquidity_usd > 0:
            limit = position.entry_liquidity_usd * (1 - settings.liquidity_pull_drop_pct / 100)
            if liq <= limit:
                return exit_(
                    ExitReason.LIQUIDITY_PULLED, 1.0,
                    f"liquidity {liq:.2f} <= {limit:.2f} ({settings.liquidity_pull_drop_pct:g}% under entry)",
                )

    # 5. first take
    if not position.took_first_take:
        multiple = settings.take_multiple_red if mode is Mode.RED else settings.take_multiple_green
        if price >= position.entry_price * multiple:
            taken = replace(updated, took_first_take=True)
            return taken, ExitDecision(
                mint=position.mint, reason=ExitReason.TAKE, fraction=settings.take_fraction,
                detail=f"price {price:.8g} >= {multiple:g} times entry {position.entry_price:.8g}",
            )

    held = snap.ts - position.entry_ts

    # 6. RED time stop
    if mode is Mode.RED and held >= settings.red_time_stop_s:
        return exit_(ExitReason.RED_TIME_STOP, 1.0, f"held {held}s >= {settings.red_time_stop_s}s in RED")

    # 7. dead money
    if held >= settings.dead_money_after_s:
        floor = position.entry_price * (1 + settings.dead_money_min_gain_pct / 100)
        if price < floor:
            return exit_(
                ExitReason.DEAD_MONEY, 1.0,
                f"held {held}s, price {price:.8g} < {floor:.8g} (gain under {settings.dead_money_min_gain_pct:g}%)",
            )

    return updated, None
