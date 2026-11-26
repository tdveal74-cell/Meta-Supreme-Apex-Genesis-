"""The brain: how big a ticket is, or why there is none (SPEC.md, section brain.py).

Source line 57 gives the sizing rule and the tiers; the risk and exposure
limits are OWNER settings. The brain sizes. It picks no coin and executes
nothing.

INVENTED, labelled so in SPEC.md (reading R4): the night stop takes the
night's starting equity as its basis and applies in every market mode.

Pure. Nothing is mutated, and there is no clock, network or randomness.
"""
from __future__ import annotations

from .model import Lesson, MarketState, PortfolioView, ScoreBreakdown, SizeDecision, TokenSnapshot
from .settings import Settings


def _skip(code: str, detail: str = "") -> SizeDecision:
    return SizeDecision(ticket_usd=0.0, skip_reason_code=code, detail=detail)


def size_ticket(
    score: ScoreBreakdown,
    snap: TokenSnapshot,
    portfolio: PortfolioView,
    market: MarketState,
    lesson: Lesson | None,
    settings: Settings,
) -> SizeDecision:
    """A sized ticket, or a skip with its reason code. Checks run in SPEC.md order."""
    assert settings.max_ticket_usd is not None
    assert settings.max_open_positions is not None
    assert settings.max_total_exposure_pct is not None

    if market.blocks_new_buys:
        return _skip("market_blocks_buys", f"market mode {market.mode.value}")
    if lesson is not None:
        return _skip("lesson_blocks", f"lesson {lesson.lesson_id}: {lesson.check}")
    if portfolio.night_start_equity_usd > 0 and (
        portfolio.night_pnl_usd <= -settings.night_stop_pct / 100 * portfolio.night_start_equity_usd
    ):
        return _skip(
            "night_stop",
            f"night pnl {portfolio.night_pnl_usd:.2f} on starting equity {portfolio.night_start_equity_usd:.2f}",
        )
    if score.size_tier == "none":
        return _skip("score_below_pass", f"score {score.total:.1f}")
    if portfolio.open_positions >= settings.max_open_positions:
        return _skip("max_open_positions", f"{portfolio.open_positions} open")
    if snap.liquidity_usd is None:
        return _skip("liquidity_unknown")

    room = settings.max_total_exposure_pct / 100 * portfolio.equity_usd - portfolio.exposure_usd
    if room <= 0:
        return _skip("exposure_cap", f"exposure room {room:.2f}")

    base = portfolio.free_cash_usd * settings.risk_per_trade_pct / settings.stop_loss_pct
    if score.size_tier == "half":
        base = base / 2
    ticket = min(
        base,
        settings.pool_liquidity_cap_pct / 100 * snap.liquidity_usd,
        settings.max_ticket_usd,
        room,
        portfolio.free_cash_usd,
    )
    if ticket < settings.min_ticket_usd:
        return _skip("ticket_below_min", f"ticket {ticket:.2f} < {settings.min_ticket_usd:.2f}")

    return SizeDecision(ticket_usd=ticket, skip_reason_code="", detail=f"{score.size_tier} size")
