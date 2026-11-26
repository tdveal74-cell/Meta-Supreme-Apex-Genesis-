"""Position arithmetic shared by the risk module and the paper ledger.

Pure functions. A Position is never mutated; each function returns a new one.
"""
from __future__ import annotations

from dataclasses import replace

from .model import Fill, Position, Side, Strategy, TokenSnapshot
from .settings import Settings


class PositionError(ValueError):
    """A fill does not fit the position it is applied to."""


def open_position(fill: Fill, snapshot: TokenSnapshot, strategy: Strategy, settings: Settings) -> Position:
    """The position a BUY fill opens.

    The stop sits ``stop_loss_pct`` below the fill price (source lines 57, 63).
    ``cost_usd`` is all the cash that left the account, fees included.
    """
    if fill.side is not Side.BUY:
        raise PositionError("only a BUY fill opens a position")
    if fill.qty <= 0 or fill.price <= 0:
        raise PositionError("a BUY fill needs a positive quantity and price")
    return Position(
        mint=fill.mint,
        symbol=fill.symbol,
        strategy=strategy,
        entry_ts=fill.ts,
        entry_price=fill.price,
        qty=fill.qty,
        cost_usd=-fill.cash_delta_usd,
        stop_price=fill.price * (1 - settings.stop_loss_pct / 100),
        peak_price=fill.price,
        took_first_take=False,
        entry_liquidity_usd=snapshot.liquidity_usd or 0.0,
        entry_snapshot=snapshot,
    )


def realized_pnl(position: Position, fill: Fill) -> float:
    """Cash received by a SELL fill, less the cost of the tokens it sold."""
    _check_sell(position, fill)
    return fill.cash_delta_usd - position.cost_usd * (fill.qty / position.qty)


def apply_exit_fill(position: Position, fill: Fill) -> Position | None:
    """The position left after a SELL fill, or ``None`` when it is closed.

    Cost falls in proportion to the quantity sold. The stop and the peak are
    left as they were.
    """
    _check_sell(position, fill)
    remaining = position.qty - fill.qty
    if remaining <= position.qty * 1e-9:
        return None
    return replace(position, qty=remaining, cost_usd=position.cost_usd * (remaining / position.qty))


def _check_sell(position: Position, fill: Fill) -> None:
    if fill.side is not Side.SELL:
        raise PositionError("expected a SELL fill")
    if fill.mint != position.mint:
        raise PositionError("the fill is for a different coin")
    if fill.qty <= 0 or fill.qty > position.qty * (1 + 1e-9):
        raise PositionError("a SELL fill must sell a positive quantity no larger than the position")
