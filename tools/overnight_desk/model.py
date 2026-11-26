"""The data the desk's modules pass to each other.

Everything here is a plain frozen dataclass or an enum. No behaviour, no
clock, no network. Times are whole seconds since the Unix epoch, UTC, and are
always passed in. Prices and money are floats in US dollars.

``None`` in a snapshot field means "this source did not tell us". The rules
in SPEC.md say what each module does with an unknown. The analyst's layers,
the brain and a lesson's check treat an unknown as a failure. SPEC.md lists
the inputs that are exceptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Mode(str, Enum):
    """Market mode, source lines 76-77."""

    GREEN = "GREEN"
    RED = "RED"
    QUIET = "QUIET"


class Strategy(str, Enum):
    """Entry strategies named at source lines 65-74.

    The source lists RED as a seventh strategy. Here RED is a market mode
    only (SPEC.md, reading R1), so it is not a member.
    """

    DIP = "DIP"
    GRAD = "GRAD"
    NEWS = "NEWS"
    COPY = "COPY"
    WAVE = "WAVE"
    TREND = "TREND"


# Only these have an entry rule in this build. SPEC.md says why the rest wait.
BUILT_STRATEGIES = frozenset({Strategy.DIP, Strategy.GRAD})


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExitReason(str, Enum):
    """Why a position, or part of one, is sold."""

    STOP = "stop"
    TAKE = "take"
    TRAIL = "trail"
    DEAD_MONEY = "dead_money"
    LIQUIDITY_PULLED = "liquidity_pulled"
    DEV_SOLD = "dev_sold"
    VENUE_WARNING = "venue_warning"
    RED_TIME_STOP = "red_time_stop"


class ScanState(str, Enum):
    WATCHING = "watching"
    KILLED = "killed"
    PASSED = "passed"


class LayerStatus(str, Enum):
    GREEN = "green"
    RED = "red"
    UNKNOWN = "unknown"


class ExecutorKind(str, Enum):
    """PAPER is the only executor this build contains."""

    PAPER = "paper"
    LIVE = "live"


class Verification(str, Enum):
    """How a fill was confirmed, source line 83.

    A paper fill is never a verified order. It is its own value so a report
    cannot count it as one.
    """

    PAPER = "paper"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class MarketSnapshot:
    """One reading of the market-wide inputs to the mode rule."""

    ts: int
    btc_change_1h_pct: float | None = None
    sol_change_1h_pct: float | None = None
    fear_greed: int | None = None
    graduations_last_hour: int | None = None


@dataclass(frozen=True)
class MarketState:
    """The mode and what it does to new buys."""

    mode: Mode
    data_ok: bool
    blocks_new_buys: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TokenSnapshot:
    """One reading of one coin's pool and safety facts.

    ``liquidity_usd`` is the value of both sides of the pool. ``top10_pct``,
    ``dev_pct``, ``insiders_pct`` and ``lp_locked_or_burned_pct`` are
    percentages from 0 to 100. ``trading_disabled`` and ``venue_warning`` come
    from a trading venue and are ``None`` when no venue adapter supplied them.
    """

    ts: int
    mint: str
    symbol: str
    name: str = ""
    pool_created_ts: int | None = None
    from_pumpfun_graduation: bool | None = None
    liquidity_usd: float | None = None
    price_usd: float | None = None
    high_10m_usd: float | None = None
    change_1h_pct: float | None = None
    buys_5m: int | None = None
    sells_5m: int | None = None
    sell_volume_5m_usd: float | None = None
    sell_volume_prev_5m_usd: float | None = None
    holders: int | None = None
    holders_prev: int | None = None
    top10_pct: float | None = None
    dev_pct: float | None = None
    dev_has_sold: bool | None = None
    mint_authority_revoked: bool | None = None
    freeze_authority_revoked: bool | None = None
    lp_locked_or_burned_pct: float | None = None
    bundled_wallets: int | None = None
    insiders_pct: float | None = None
    dangerous_delegation: bool | None = None
    copycat_of: str | None = None
    trading_disabled: bool | None = None
    venue_warning: str | None = None
    social_score: float | None = None
    narrative_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanResult:
    """The scanner's view of one coin after an observation."""

    mint: str
    state: ScanState
    first_seen_ts: int
    reason_code: str = ""
    detail: str = ""


@dataclass(frozen=True)
class LayerResult:
    number: int
    name: str
    status: LayerStatus
    detail: str = ""


@dataclass(frozen=True)
class AuditResult:
    """The eight layers in order, stopping at the first that is not green.

    ``layers`` holds only the layers that were evaluated, so it ends at the
    first red or unknown layer. ``passed`` is true only for eight greens.
    """

    layers: tuple[LayerResult, ...]
    passed: bool
    first_failure: LayerResult | None = None


@dataclass(frozen=True)
class ScoreBreakdown:
    """The score and its parts. ``size_tier`` is 'full', 'half' or 'none'."""

    alive: float
    organic: float
    flush: float
    anti_chase: float
    social: float
    total: float
    passed: bool
    size_tier: str


@dataclass(frozen=True)
class EntrySignal:
    """Whether a strategy's entry rule fires on a snapshot."""

    strategy: Strategy
    fires: bool
    reason_code: str = ""
    detail: str = ""


@dataclass(frozen=True)
class PortfolioView:
    """What the brain may know about the account when it sizes a ticket."""

    free_cash_usd: float
    equity_usd: float
    open_positions: int
    exposure_usd: float
    night_start_equity_usd: float
    night_pnl_usd: float


@dataclass(frozen=True)
class SizeDecision:
    """A ticket size in dollars, or a reason to skip. Never both."""

    ticket_usd: float
    skip_reason_code: str = ""
    detail: str = ""

    @property
    def skipped(self) -> bool:
        return self.ticket_usd <= 0


@dataclass(frozen=True)
class HumanApproval:
    """A record that a named person approved one order. Needed by any executor but PAPER.

    It is a record and proves nothing about who built it. The desk checks that
    it names someone, carries a time and matches the order.
    """

    order_id: str
    approved_by: str
    approved_ts: int
    note: str = ""


@dataclass(frozen=True)
class OrderIntent:
    """What the desk wants done. The desk never executes one itself.

    A BUY carries ``usd``. A SELL carries ``qty`` in tokens. ``decision_price``
    is the snapshot price the decision was made on, or ``None`` when an exit
    was decided on a snapshot that had no price.
    """

    order_id: str
    ts: int
    mint: str
    symbol: str
    side: Side
    reason_code: str
    decision_price: float | None
    usd: float | None = None
    qty: float | None = None
    strategy: Strategy | None = None
    exit_reason: ExitReason | None = None


@dataclass(frozen=True)
class Quote:
    """A modelled price for an order of a given size, with every cost named."""

    side: Side
    spot_price: float
    fill_price: float
    qty: float
    gross_usd: float
    venue_fee_usd: float
    pool_fee_usd: float
    fixed_fee_usd: float
    price_impact_pct: float

    @property
    def fees_usd(self) -> float:
        return self.venue_fee_usd + self.pool_fee_usd + self.fixed_fee_usd


@dataclass(frozen=True)
class Fill:
    """An executed order. ``cash_delta_usd`` is negative for a buy."""

    order_id: str
    ts: int
    mint: str
    symbol: str
    side: Side
    qty: float
    price: float
    gross_usd: float
    fees_usd: float
    cash_delta_usd: float
    verification: Verification
    exit_reason: ExitReason | None = None


@dataclass(frozen=True)
class Position:
    """One open position. Replace it with ``dataclasses.replace``; never mutate.

    ``entry_price`` is the fill price. ``cost_usd`` is the cash that left the
    account for the tokens still held, fees included. ``stop_price`` only
    ever rises.
    """

    mint: str
    symbol: str
    strategy: Strategy
    entry_ts: int
    entry_price: float
    qty: float
    cost_usd: float
    stop_price: float
    peak_price: float
    took_first_take: bool
    entry_liquidity_usd: float
    entry_snapshot: TokenSnapshot


@dataclass(frozen=True)
class ExitDecision:
    """Risk's instruction for one position at one moment."""

    mint: str
    reason: ExitReason
    fraction: float
    detail: str = ""


@dataclass(frozen=True)
class Lesson:
    """A check written after a loss. It can only block a future trade."""

    lesson_id: str
    created_ts: int
    source_mint: str
    check: str
    why: str = ""


@dataclass(frozen=True)
class Skip:
    """One decision not to trade, with the stage and the reason."""

    ts: int
    mint: str
    symbol: str
    stage: str
    reason_code: str
    detail: str = ""


class Executor(Protocol):
    """Anything that can carry out an OrderIntent.

    ``kind`` tells the desk whether a HumanApproval is required. This build
    ships one implementation, the paper executor.
    """

    kind: ExecutorKind

    def execute(
        self, intent: OrderIntent, snapshot: TokenSnapshot, approval: HumanApproval | None = None
    ) -> Fill: ...
