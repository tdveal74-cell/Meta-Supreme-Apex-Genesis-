"""Entry rules and the pre-trade recheck (SPEC.md, section entry.py).

``entry_signal`` says whether a strategy's entry rule fires on one snapshot.
It comes from source line 60 (buy only a set distance below the 10 minute
high), line 68 (the DIP strategy and its pool age window) and line 71 (the
GRAD strategy). ``pre_trade_recheck`` comes from source line 60: right before
acting, liquidity, price, cash and venue warnings are checked again.

INVENTED, labelled so in SPEC.md: the definition of "sellers drying up"
(``sellers_not_drying_up``) and the price drift tolerance behind
``price_drifted``. NEWS, COPY, WAVE and TREND have no entry rule here and
answer ``strategy_not_built``.

Pure functions. Nothing is mutated, and there is no clock, network or
randomness. An unknown (None) fails an entry check. The exception is the
recheck's two venue fields on a paper run, which SPEC.md describes.
"""
from __future__ import annotations

from .model import (
    BUILT_STRATEGIES,
    EntrySignal,
    ExecutorKind,
    Strategy,
    TokenSnapshot,
)
from .settings import Settings


def _no(strategy: Strategy, code: str, detail: str = "") -> EntrySignal:
    return EntrySignal(strategy=strategy, fires=False, reason_code=code, detail=detail)


def entry_signal(snap: TokenSnapshot, strategy: Strategy, settings: Settings) -> EntrySignal:
    """Whether ``strategy`` fires on ``snap``. The first failed check names the reason."""
    if strategy not in BUILT_STRATEGIES:
        return _no(strategy, "strategy_not_built", f"{strategy.value} has no entry rule in this build")

    missing = [
        name
        for name in (
            "price_usd",
            "high_10m_usd",
            "pool_created_ts",
            "liquidity_usd",
            "sell_volume_5m_usd",
            "sell_volume_prev_5m_usd",
        )
        if getattr(snap, name) is None
    ]
    if missing:
        return _no(strategy, "dip_data_missing", "missing: " + ", ".join(missing))
    assert snap.price_usd is not None and snap.high_10m_usd is not None
    assert snap.pool_created_ts is not None and snap.liquidity_usd is not None
    assert snap.sell_volume_5m_usd is not None and snap.sell_volume_prev_5m_usd is not None
    if snap.high_10m_usd <= 0:
        return _no(strategy, "dip_data_missing", f"high_10m_usd {snap.high_10m_usd:.6g} is not positive")

    age = snap.ts - snap.pool_created_ts
    if strategy is Strategy.DIP:
        if not (settings.dip_age_min_s <= age <= settings.dip_age_max_s):
            return _no(
                strategy,
                "age_outside_window",
                f"pool age {age}s outside {settings.dip_age_min_s}s to {settings.dip_age_max_s}s",
            )
        if snap.liquidity_usd < settings.liquidity_floor_usd:
            return _no(
                strategy,
                "liquidity_below_floor",
                f"liquidity {snap.liquidity_usd:.2f} < {settings.liquidity_floor_usd:.2f}",
            )
    else:  # GRAD, the only other built strategy
        if snap.from_pumpfun_graduation is None:
            return _no(strategy, "graduation_unknown", "from_pumpfun_graduation is unknown")
        if snap.from_pumpfun_graduation is False:
            return _no(strategy, "not_a_graduation", "the coin did not graduate from the launchpad")
        if age < settings.scanner_watch_s:
            return _no(strategy, "grad_wait", f"pool age {age}s < {settings.scanner_watch_s}s")

    pullback = (snap.high_10m_usd - snap.price_usd) / snap.high_10m_usd * 100
    if not pullback >= settings.dip_from_high_pct:
        return _no(
            strategy,
            "no_dip",
            f"pullback {pullback:.2f}% < {settings.dip_from_high_pct:.2f}%",
        )

    prev = snap.sell_volume_prev_5m_usd
    now = snap.sell_volume_5m_usd
    if not (prev > 0 and now <= settings.sell_dryup_ratio * prev):
        return _no(
            strategy,
            "sellers_not_drying_up",
            f"sell volume {now:.2f} against previous {prev:.2f}, ratio limit {settings.sell_dryup_ratio}",
        )

    return EntrySignal(strategy=strategy, fires=True, reason_code="entry", detail=f"pullback {pullback:.2f}%")


def pre_trade_recheck(
    decision: TokenSnapshot,
    fresh: TokenSnapshot,
    ticket_usd: float,
    free_cash_usd: float,
    settings: Settings,
    executor_kind: ExecutorKind,
) -> tuple[str, ...]:
    """Every reason to abort, in SPEC.md order. An empty tuple means go ahead."""
    reasons: list[str] = []

    if fresh.ts < decision.ts:
        reasons.append("stale_snapshot")

    if fresh.liquidity_usd is None:
        reasons.append("liquidity_unknown")
    elif fresh.liquidity_usd < settings.liquidity_floor_usd:
        reasons.append("liquidity_below_floor")

    if fresh.liquidity_usd is not None:
        if ticket_usd > settings.pool_liquidity_cap_pct / 100 * fresh.liquidity_usd:
            reasons.append("ticket_exceeds_liquidity_cap")

    if fresh.price_usd is None or decision.price_usd is None or not decision.price_usd > 0:
        reasons.append("price_unknown")
    else:
        drift = abs(fresh.price_usd - decision.price_usd) / decision.price_usd * 100
        if drift > settings.recheck_max_price_drift_pct:
            reasons.append("price_drifted")

    if ticket_usd > free_cash_usd:
        reasons.append("insufficient_cash")

    if fresh.venue_warning:
        reasons.append("venue_warning")

    if fresh.trading_disabled is True:
        reasons.append("trading_disabled")

    if executor_kind is ExecutorKind.LIVE and (
        fresh.trading_disabled is None or fresh.venue_warning is None
    ):
        reasons.append("venue_checks_missing")

    return tuple(reasons)
