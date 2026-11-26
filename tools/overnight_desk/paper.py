"""The paper executor, its cost model and the ledger.

Source line 80 says a PAPER fill is "taken from the quote" and the source
states no cost anywhere. This module makes every cost explicit. The cost model
(a constant-product pool plus a venue fee, a pool fee and a flat fee per side)
is INVENTED, and its three rates are OWNER settings with no default. The
per-order human gate in ``require_approval`` comes from source line 80 and the
SPEC.md "paper.py" section; it is not a setting. The rule that a position is
never averaged down is source line 60. Nothing here reads a clock, the network
or a random source, and no argument is mutated.

INVENTED rule, drained pool: a SELL into a pool whose liquidity is known and
exactly zero is quoted as a total loss (zero proceeds, price impact -100
percent) instead of being refused, because a drained pool is the case the exit
rules exist for and it must be recordable as a loss. It needs no price.
"""
from __future__ import annotations

from .model import (
    ExecutorKind,
    Fill,
    HumanApproval,
    OrderIntent,
    PortfolioView,
    Position,
    Quote,
    Side,
    TokenSnapshot,
    Verification,
)
from .positions import apply_exit_fill, realized_pnl
from .settings import Settings


class PaperError(ValueError):
    """An order or a ledger entry cannot be modelled or recorded."""


class ApprovalRequired(PermissionError):
    """A non paper executor was asked to act without a matching approval."""


def model_quote(
    side: Side,
    snap: TokenSnapshot,
    settings: Settings,
    usd: float | None = None,
    qty: float | None = None,
) -> Quote:
    """Quote an order against a constant-product pool. INVENTED cost model.

    INVENTED rule, drained pool: when ``side`` is SELL and the liquidity is
    known and exactly 0, the quote is a total loss. ``qty`` is the amount
    offered, every price and fee is 0.0, ``price_impact_pct`` is -100.0 and
    ``spot_price`` is the snapshot price when that is above 0, else 0.0. No
    price is needed. The argument checks still run first. Unknown, negative or
    NaN liquidity is refused on both sides, and a BUY into a drained pool too.
    """
    liquidity = snap.liquidity_usd
    price = snap.price_usd
    if liquidity is None or liquidity != liquidity or liquidity < 0:
        raise PaperError("liquidity is unknown or negative")
    drained = side is Side.SELL and liquidity == 0
    if not drained:
        if not liquidity > 0:
            raise PaperError("liquidity is unknown or not positive")
        if price is None or not price > 0:
            raise PaperError("price is unknown or not positive")
    if (usd is None) == (qty is None):
        raise PaperError("give exactly one of usd and qty")
    if side is Side.BUY and usd is None:
        raise PaperError("a BUY takes usd")
    if side is Side.SELL and qty is None:
        raise PaperError("a SELL takes qty")
    amount = usd if side is Side.BUY else qty
    if amount is None or not amount > 0:
        raise PaperError("the amount must be positive")

    if drained:
        return Quote(
            side=side,
            spot_price=price if price is not None and price > 0 else 0.0,
            fill_price=0.0,
            qty=amount,
            gross_usd=0.0,
            venue_fee_usd=0.0,
            pool_fee_usd=0.0,
            fixed_fee_usd=0.0,
            price_impact_pct=-100.0,
        )

    assert price is not None
    if (
        settings.venue_fee_pct_per_side is None
        or settings.pool_fee_pct_per_side is None
        or settings.fixed_fee_usd_per_side is None
    ):
        raise PaperError("a fee setting is not set")
    v = settings.venue_fee_pct_per_side / 100
    p = settings.pool_fee_pct_per_side / 100
    f = settings.fixed_fee_usd_per_side

    rq = liquidity / 2
    rt = rq / price

    if side is Side.BUY:
        venue_fee_usd = v * amount
        fixed_fee_usd = f
        to_pool = amount - venue_fee_usd - fixed_fee_usd
        if not to_pool > 0:
            raise PaperError("fees take the whole order")
        pool_fee_usd = p * to_pool
        effective = to_pool - pool_fee_usd
        out_qty = rt * effective / (rq + effective)
        if not out_qty > 0:
            raise PaperError("the order buys no tokens")
        gross_usd = to_pool
        fill_price = to_pool / out_qty
    else:
        out_qty = amount
        effective = out_qty * (1 - p)
        gross_usd = rq * effective / (rt + effective)
        pool_fee_usd = out_qty * p * price
        venue_fee_usd = v * gross_usd
        fixed_fee_usd = f
        fill_price = gross_usd / out_qty

    return Quote(
        side=side,
        spot_price=price,
        fill_price=fill_price,
        qty=out_qty,
        gross_usd=gross_usd,
        venue_fee_usd=venue_fee_usd,
        pool_fee_usd=pool_fee_usd,
        fixed_fee_usd=fixed_fee_usd,
        price_impact_pct=(fill_price / price - 1) * 100,
    )


def require_approval(intent: OrderIntent, kind: ExecutorKind, approval: HumanApproval | None) -> None:
    """The per-order human gate. Any executor but PAPER needs a matching approval."""
    if kind is ExecutorKind.PAPER:
        return
    if approval is None:
        raise ApprovalRequired("a human approval is required for this order")
    if approval.order_id != intent.order_id:
        raise ApprovalRequired("the approval is for a different order")
    if not isinstance(approval.approved_by, str) or not approval.approved_by.strip():
        raise ApprovalRequired("the approval names no person")
    ts = approval.approved_ts
    if not isinstance(ts, int) or isinstance(ts, bool) or not ts > 0:
        raise ApprovalRequired("the approval carries no time")


class PaperExecutor:
    """The only executor in this build. Its fills are never verified orders."""

    kind = ExecutorKind.PAPER

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(
        self,
        intent: OrderIntent,
        snapshot: TokenSnapshot,
        approval: HumanApproval | None = None,
    ) -> Fill:
        require_approval(intent, self.kind, approval)
        if snapshot.mint != intent.mint:
            raise PaperError("the snapshot is for a different coin than the intent")
        if intent.side is Side.BUY:
            if intent.usd is None:
                raise PaperError("a BUY intent needs usd")
            quote = model_quote(Side.BUY, snapshot, self.settings, usd=intent.usd)
            cash_delta = -intent.usd
        else:
            if intent.qty is None:
                raise PaperError("a SELL intent needs qty")
            quote = model_quote(Side.SELL, snapshot, self.settings, qty=intent.qty)
            cash_delta = max(0.0, quote.gross_usd - quote.venue_fee_usd - quote.fixed_fee_usd)
        return Fill(
            order_id=intent.order_id,
            ts=snapshot.ts,
            mint=intent.mint,
            symbol=intent.symbol,
            side=intent.side,
            qty=quote.qty,
            price=quote.fill_price,
            gross_usd=quote.gross_usd,
            fees_usd=quote.fees_usd,
            cash_delta_usd=cash_delta,
            verification=Verification.PAPER,
            exit_reason=intent.exit_reason,
        )


class Ledger:
    """Cash, open positions and the record of fills."""

    def __init__(self, starting_cash_usd: float) -> None:
        self.cash_usd: float = starting_cash_usd
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self.realized_pnl_usd: float = 0.0
        self.fees_usd: float = 0.0

    def record_buy(self, fill: Fill, position: Position) -> None:
        if fill.side is not Side.BUY:
            raise PaperError("record_buy needs a BUY fill")
        if position.mint != fill.mint:
            raise PaperError("the position is for a different coin than the fill")
        if fill.mint in self.positions:
            raise PaperError("a position in this coin is already open; never average down")
        cost = -fill.cash_delta_usd
        if cost > self.cash_usd:
            raise PaperError("the cost is above the cash on hand")
        self.cash_usd -= cost
        self.positions[fill.mint] = position
        self.fees_usd += fill.fees_usd
        self.fills.append(fill)

    def record_sell(self, fill: Fill) -> float:
        position = self.positions.get(fill.mint)
        if position is None:
            raise PaperError("no open position in this coin")
        pnl = realized_pnl(position, fill)
        rest = apply_exit_fill(position, fill)
        self.cash_usd += fill.cash_delta_usd
        if rest is None:
            del self.positions[fill.mint]
        else:
            self.positions[fill.mint] = rest
        self.fees_usd += fill.fees_usd
        self.realized_pnl_usd += pnl
        self.fills.append(fill)
        return pnl

    def exposure_usd(self) -> float:
        return sum(p.cost_usd for p in self.positions.values())

    def equity_usd(self, prices: dict[str, float]) -> float:
        total = self.cash_usd
        for mint, pos in self.positions.items():
            price = prices.get(mint)
            total += pos.qty * price if price is not None else pos.cost_usd
        return total

    def view(self, prices: dict[str, float], night_start_equity_usd: float) -> PortfolioView:
        equity = self.equity_usd(prices)
        return PortfolioView(
            free_cash_usd=self.cash_usd,
            equity_usd=equity,
            open_positions=len(self.positions),
            exposure_usd=self.exposure_usd(),
            night_start_equity_usd=night_start_equity_usd,
            night_pnl_usd=equity - night_start_equity_usd,
        )


__all__ = [
    "ApprovalRequired",
    "Ledger",
    "PaperError",
    "PaperExecutor",
    "model_quote",
    "require_approval",
]
