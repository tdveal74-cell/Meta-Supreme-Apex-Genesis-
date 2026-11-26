"""The desk: one tick takes the market and the coins seen, and decides.

It wires the five bots of the source prompt (lines 39-63) together. Risk runs
first in every tick, because sells go before buys (source line 63, "sells jump
the click queue"):

    market mode -> risk on open positions -> scanner -> analyst -> brain
    -> entry rule -> pre-trade recheck -> executor

The desk never executes an order itself. It hands an OrderIntent to an
Executor, and for any executor that is not the paper one it demands a
HumanApproval for that order first. An order the executor refuses, or one with
no approval, is recorded and the tick carries on: a refused buy is a skip, and
an exit that could not be carried out is an alert and a rule violation. So one
position's trouble never stops the next position's stop from being checked.

INVENTED here, and labelled so in SPEC.md: candidates are tried best score
first; a coin traded once in a night is not traded again that night; a skip
or an alert is recorded when it changes, not on every tick; a reading older
than ``max_snapshot_age_s`` is never bought on; an exit that cannot be filled
is a violation.

The pre-trade recheck compares the snapshot with itself in this build. The
desk gets one reading per coin per tick, so price drift between the decision
and the order cannot be seen. The night report says so.

No clock, no network. The time is the ``now`` passed to ``tick``.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from . import analyst, brain, entry, lessons, market_mode, paper, positions, risk
from .live_gate import live_gate_blockers
from .model import (
    Executor,
    ExecutorKind,
    ExitReason,
    Fill,
    HumanApproval,
    Lesson,
    MarketSnapshot,
    MarketState,
    Mode,
    OrderIntent,
    Position,
    ScanState,
    Side,
    Skip,
    Strategy,
    TokenSnapshot,
    Verification,
)
from .scanner import Scanner
from .settings import Settings

ApprovalSource = Callable[[OrderIntent], HumanApproval | None]

# A loss may exceed the budget by this much before it is called a violation.
_BUDGET_TOLERANCE_USD = 1e-9


@dataclass(frozen=True)
class TickReport:
    """What one tick did."""

    ts: int
    mode: Mode
    blocks_new_buys: bool
    fills: tuple[Fill, ...]
    skips: tuple[Skip, ...]
    alerts: tuple[str, ...]
    lessons_added: tuple[Lesson, ...]


class Desk:
    """One night of the desk. Create a new Desk for a new night."""

    def __init__(
        self,
        settings: Settings,
        starting_cash_usd: float,
        executor: Executor | None = None,
        lesson_book: lessons.LessonBook | None = None,
        strategies: Sequence[Strategy] = (Strategy.GRAD, Strategy.DIP),
        approve: ApprovalSource | None = None,
    ) -> None:
        if (
            isinstance(starting_cash_usd, bool)
            or not isinstance(starting_cash_usd, (int, float))
            or not math.isfinite(starting_cash_usd)
            or starting_cash_usd <= 0
        ):
            raise ValueError("starting cash must be a positive, finite number")
        self.settings = settings
        self.executor: Executor = executor if executor is not None else paper.PaperExecutor(settings)
        self.lessons = lesson_book if lesson_book is not None else lessons.LessonBook()
        self.strategies = tuple(strategies)
        self._approve = approve
        self.ledger = paper.Ledger(starting_cash_usd)
        self.scanner = Scanner(settings)
        self.night_start_equity_usd = float(starting_cash_usd)
        self.skips: list[Skip] = []
        self.alerts: list[str] = []
        self.violations: list[dict[str, Any]] = []
        self.losses: list[dict[str, Any]] = []
        self.mode_log: list[dict[str, Any]] = []
        self.lessons_added: list[Lesson] = []
        self._prices: dict[str, float] = {}
        self._traded: set[str] = set()
        self._last_skip: dict[str, tuple[str, str]] = {}
        self._alerting: dict[str, set[str]] = {}
        self._unexecuted: set[tuple[str, str]] = set()
        self._cash_at_entry: dict[str, float] = {}
        self._realized: dict[str, float] = {}
        self._snap_ts: dict[str, int] = {}
        self._first_ts: int | None = None
        self._last_ts: int | None = None
        self._ticks = 0
        self._snapshots_seen = 0
        self._seq = 0

    # ------------------------------------------------------------------ tick

    def tick(
        self, now: int, market: MarketSnapshot | None, snapshots: Sequence[TokenSnapshot]
    ) -> TickReport:
        if self._last_ts is not None and now < self._last_ts:
            raise ValueError("ticks must not go back in time")
        by_mint: dict[str, TokenSnapshot] = {}
        for snap in snapshots:
            if snap.mint in by_mint:
                raise ValueError(f"two snapshots for {snap.mint} in one tick")
            if snap.ts > now:
                raise ValueError(f"snapshot for {snap.mint} is from after the tick")
            seen = self._snap_ts.get(snap.mint)
            if seen is not None and snap.ts < seen:
                raise ValueError(f"snapshot for {snap.mint} is older than the last one seen")
            by_mint[snap.mint] = snap
        # Nothing above changed the desk, so a refused tick leaves it as it was.
        # Nothing below raises on a well formed tick: an order that is refused
        # is recorded, never raised.
        self._ticks += 1
        self._snapshots_seen += len(by_mint)
        if self._first_ts is None:
            self._first_ts = now
        self._last_ts = now
        for snap in by_mint.values():
            self._snap_ts[snap.mint] = snap.ts
            price = snap.price_usd
            # A price of 0.0 is a reading: it values a held coin at nothing.
            if price is not None and math.isfinite(price) and price >= 0:
                self._prices[snap.mint] = price

        mark = _Mark(self)
        state = market_mode.assess(market, self.settings)
        if not self.mode_log or self.mode_log[-1]["mode"] != state.mode.value or (
            self.mode_log[-1]["blocks_new_buys"] != state.blocks_new_buys
        ):
            self.mode_log.append(
                {
                    "ts": now,
                    "mode": state.mode.value,
                    "blocks_new_buys": state.blocks_new_buys,
                    "data_ok": state.data_ok,
                    "reasons": list(state.reasons),
                }
            )

        fills: list[Fill] = []
        self._risk_pass(now, by_mint, state.mode, fills)
        passed = self._scan_pass(now, by_mint)
        self._buy_pass(now, passed, state, fills)
        return TickReport(
            ts=now,
            mode=state.mode,
            blocks_new_buys=state.blocks_new_buys,
            fills=tuple(fills),
            skips=tuple(self.skips[mark.skips :]),
            alerts=tuple(self.alerts[mark.alerts :]),
            lessons_added=tuple(self.lessons_added[mark.lessons :]),
        )

    # ------------------------------------------------------------- the passes

    def _risk_pass(
        self, now: int, by_mint: dict[str, TokenSnapshot], mode: Mode, fills: list[Fill]
    ) -> None:
        for mint in sorted(self.ledger.positions):
            position = self.ledger.positions[mint]
            snap = by_mint.get(mint)
            raised: set[str] = set()
            if snap is None:
                self._alert(now, position, "no_reading_for_position", "the coin was not in this tick", raised)
            else:
                self._risk_one(now, position, snap, mode, fills, raised)
            if raised and mint in self.ledger.positions:
                self._alerting[mint] = raised
            else:
                self._alerting.pop(mint, None)

    def _risk_one(
        self, now: int, position: Position, snap: TokenSnapshot, mode: Mode,
        fills: list[Fill], raised: set[str],
    ) -> None:
        mint = position.mint
        age = now - snap.ts
        if age > self.settings.max_snapshot_age_s:
            # Risk still acts on it: an old reading is better than none for an exit.
            self._alert(now, position, "stale_reading_for_position", f"the reading is {age}s old", raised)
        updated, decision = risk.evaluate(position, snap, mode, self.settings)
        if decision is None:
            if snap.price_usd is None:
                self._alert(now, position, "no_price_for_position", "the reading has no price", raised)
            self.ledger.positions[mint] = updated
            return
        intent = OrderIntent(
            order_id=self._next_id(now),
            ts=now,
            mint=mint,
            symbol=position.symbol,
            side=Side.SELL,
            reason_code=decision.reason.value,
            decision_price=snap.price_usd,
            qty=position.qty * decision.fraction,
            strategy=position.strategy,
            exit_reason=decision.reason,
        )
        fill, code, why = self._execute(intent, snap)
        if fill is None:
            # The position is left exactly as it was: same quantity, same stop,
            # and a first take that did not happen is not marked as taken.
            detail = f"{decision.reason.value} was decided and not carried out ({code}: {why})"
            self._alert(now, position, "exit_not_executed", detail, raised, key=decision.reason.value)
            key = (mint, decision.reason.value)
            if key not in self._unexecuted:
                self._unexecuted.add(key)
                self.violations.append(
                    {
                        "ts": now,
                        "rule": "exit_not_executed",
                        "mint": mint,
                        "symbol": position.symbol,
                        "exit_reason": decision.reason.value,
                        "detail": detail,
                    }
                )
            return
        self.ledger.positions[mint] = updated
        pnl = self.ledger.record_sell(fill)
        fills.append(fill)
        self._realized[mint] = self._realized.get(mint, 0.0) + pnl
        if mint not in self.ledger.positions:
            self._close_out(now, updated, fill, decision.reason)

    def _scan_pass(self, now: int, by_mint: dict[str, TokenSnapshot]) -> list[TokenSnapshot]:
        passed: list[TokenSnapshot] = []
        for mint in sorted(by_mint):
            snap = by_mint[mint]
            result = self.scanner.observe(snap)
            if mint in self.ledger.positions:
                continue
            if result.state is ScanState.PASSED:
                if mint in self._traded:
                    self._skip(now, snap, "desk", "already_traded_tonight", "")
                else:
                    passed.append(snap)
            else:
                self._skip(now, snap, "scanner", result.reason_code, result.detail)
        return passed

    def _buy_pass(
        self, now: int, passed: list[TokenSnapshot], state: MarketState, fills: list[Fill]
    ) -> None:
        scored = []
        for snap in passed:
            audit, score = analyst.analyse(snap, self.settings)
            if not audit.passed or score is None:
                layer = audit.first_failure
                code = f"layer_{layer.number}_{layer.status.value}" if layer else "audit_failed"
                detail = f"{layer.name}: {layer.detail}".strip(": ") if layer else ""
                self._skip(now, snap, "analyst", code, detail)
                continue
            scored.append((snap, score))
        scored.sort(key=lambda pair: (-pair[1].total, pair[0].mint))

        for snap, score in scored:
            view = self.ledger.view(self._prices, self.night_start_equity_usd)
            lesson = self.lessons.blocking(snap)
            decision = brain.size_ticket(score, snap, view, state, lesson, self.settings)
            if decision.skipped:
                detail = decision.detail
                if lesson is not None and decision.skip_reason_code == "lesson_blocks":
                    detail = f"{lesson.lesson_id}: {lesson.check}"
                self._skip(now, snap, "brain", decision.skip_reason_code, detail)
                continue
            signals = [entry.entry_signal(snap, strategy, self.settings) for strategy in self.strategies]
            fired = next((s for s in signals if s.fires), None)
            if fired is None:
                detail = "; ".join(f"{s.strategy.value}:{s.reason_code}" for s in signals)
                self._skip(now, snap, "executor", "no_entry_signal", detail)
                continue
            age = now - snap.ts
            if age > self.settings.max_snapshot_age_s:
                self._skip(now, snap, "executor", "stale_snapshot", f"the reading is {age}s old")
                continue
            # One reading per coin per tick: the decision and the fresh snapshot
            # are the same object, so drift and staleness cannot fire here.
            reasons = entry.pre_trade_recheck(
                snap, snap, decision.ticket_usd, view.free_cash_usd, self.settings, self.executor.kind
            )
            if reasons:
                self._skip(now, snap, "executor", reasons[0], "; ".join(reasons))
                continue
            intent = OrderIntent(
                order_id=self._next_id(now),
                ts=now,
                mint=snap.mint,
                symbol=snap.symbol,
                side=Side.BUY,
                reason_code="entry",
                decision_price=snap.price_usd,
                usd=decision.ticket_usd,
                strategy=fired.strategy,
            )
            fill, code, why = self._execute(intent, snap)
            if fill is None:
                self._skip(now, snap, "executor", code, why)
                continue
            position = positions.open_position(fill, snap, fired.strategy, self.settings)
            self.ledger.record_buy(fill, position)
            fills.append(fill)
            self._traded.add(snap.mint)
            self._cash_at_entry[snap.mint] = view.free_cash_usd
            self._realized[snap.mint] = 0.0

    # ---------------------------------------------------------------- helpers

    def _execute(self, intent: OrderIntent, snap: TokenSnapshot) -> tuple[Fill | None, str, str]:
        """Hand one intent to the executor, behind the per-order human gate.

        Returns ``(fill, "", "")``, or ``(None, code, why)`` when the order was
        not filled: ``approval_missing`` when the gate refused it, and
        ``order_refused`` when the executor did. Neither is raised, so the
        rest of the tick still runs.
        """
        approval: HumanApproval | None = None
        if self.executor.kind is not ExecutorKind.PAPER and self._approve is not None:
            approval = self._approve(intent)
        try:
            paper.require_approval(intent, self.executor.kind, approval)
            return self.executor.execute(intent, snap, approval), "", ""
        except paper.ApprovalRequired as exc:
            return None, "approval_missing", str(exc)
        except paper.PaperError as exc:
            return None, "order_refused", str(exc)

    def _close_out(self, now: int, position: Position, fill: Fill, reason: ExitReason) -> None:
        mint = position.mint
        total = self._realized.pop(mint, 0.0)
        cash_at_entry = self._cash_at_entry.pop(mint, 0.0)
        self._unexecuted = {key for key in self._unexecuted if key[0] != mint}
        if total >= 0:
            return
        budget = cash_at_entry * self.settings.risk_per_trade_pct / 100
        over_budget = -total > budget + _BUDGET_TOLERANCE_USD
        lesson = lessons.derive_lesson(position, fill, self.settings)
        if lesson is not None:
            stored = self.lessons.add(lesson)
            if stored is lesson:
                self.lessons_added.append(stored)
            lesson = stored
        loss = {
            "ts": now,
            "mint": mint,
            "symbol": position.symbol,
            "strategy": position.strategy.value,
            "exit_reason": reason.value,
            "entry_ts": position.entry_ts,
            "entry_price": position.entry_price,
            "exit_price": fill.price,
            "pnl_usd": total,
            "cash_at_entry_usd": cash_at_entry,
            "loss_pct_of_cash": (-total / cash_at_entry * 100) if cash_at_entry > 0 else None,
            "budget_usd": budget,
            "over_budget": over_budget,
            "lesson": lesson.check if lesson is not None else None,
        }
        self.losses.append(loss)
        if over_budget:
            self.violations.append(
                {
                    "ts": now,
                    "rule": "loss_exceeded_risk_budget",
                    "mint": mint,
                    "symbol": position.symbol,
                    "loss_usd": -total,
                    "budget_usd": budget,
                    "detail": (
                        f"the source's standard is a loss of at most {self.settings.risk_per_trade_pct}% "
                        "of cash; costs and the fill price took this one past it"
                    ),
                }
            )

    def _skip(self, now: int, snap: TokenSnapshot, stage: str, code: str, detail: str) -> None:
        key = (stage, code)
        if self._last_skip.get(snap.mint) == key:
            return
        self._last_skip[snap.mint] = key
        self.skips.append(Skip(now, snap.mint, snap.symbol, stage, code, detail))

    def _alert(
        self, now: int, position: Position, code: str, detail: str, raised: set[str], key: str = ""
    ) -> None:
        """Record an alert on a held coin when it starts, not on every tick it lasts."""
        mark = f"{code}:{key}"
        raised.add(mark)
        if mark in self._alerting.get(position.mint, ()):
            return
        self.alerts.append(f"{now} {code} {position.mint} {position.symbol}: {detail}")

    def _next_id(self, now: int) -> str:
        self._seq += 1
        return f"{now}-{self._seq:04d}"

    # ----------------------------------------------------------------- report

    def night_report(self) -> dict[str, Any]:
        """Everything the morning report needs, as plain data."""
        equity = self.ledger.equity_usd(self._prices)
        by_reason: dict[str, int] = {}
        for skip in self.skips:
            key = f"{skip.stage}:{skip.reason_code}"
            by_reason[key] = by_reason.get(key, 0) + 1
        verification = {v.value: 0 for v in Verification}
        for fill in self.ledger.fills:
            verification[fill.verification.value] += 1
        buys = sum(1 for f in self.ledger.fills if f.side is Side.BUY)
        return {
            "executor": self.executor.kind.value,
            "ticks": self._ticks,
            "snapshots_seen": self._snapshots_seen,
            "coins_seen": len(self._snap_ts),
            "first_ts": self._first_ts,
            "last_ts": self._last_ts,
            # One reading per coin per tick, so the recheck had no second reading.
            "recheck_source": "same_snapshot",
            "starting_cash_usd": self.night_start_equity_usd,
            "ending_cash_usd": self.ledger.cash_usd,
            "ending_equity_usd": equity,
            "night_pnl_usd": equity - self.night_start_equity_usd,
            "realized_pnl_usd": self.ledger.realized_pnl_usd,
            "fees_usd": self.ledger.fees_usd,
            "buys": buys,
            "sells": len(self.ledger.fills) - buys,
            "open_positions": [
                {
                    "mint": p.mint,
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "cost_usd": p.cost_usd,
                    "stop_price": p.stop_price,
                    "last_price": self._prices.get(p.mint),
                    "last_reading_ts": self._snap_ts.get(p.mint),
                }
                for p in (self.ledger.positions[m] for m in sorted(self.ledger.positions))
            ],
            "fills": [
                {
                    "order_id": f.order_id,
                    "ts": f.ts,
                    "mint": f.mint,
                    "symbol": f.symbol,
                    "side": f.side.value,
                    "qty": f.qty,
                    "price": f.price,
                    "gross_usd": f.gross_usd,
                    "fees_usd": f.fees_usd,
                    "cash_delta_usd": f.cash_delta_usd,
                    "verification": f.verification.value,
                    "exit_reason": f.exit_reason.value if f.exit_reason else None,
                }
                for f in self.ledger.fills
            ],
            "skips_by_reason": dict(sorted(by_reason.items())),
            "skips": [
                {
                    "ts": s.ts,
                    "mint": s.mint,
                    "symbol": s.symbol,
                    "stage": s.stage,
                    "reason_code": s.reason_code,
                    "detail": s.detail,
                }
                for s in self.skips
            ],
            "losses": list(self.losses),
            "violations": list(self.violations),
            "alerts": list(self.alerts),
            "verification": verification,
            "real_orders_sent": verification["verified"] + verification["unverified"],
            "mode_log": list(self.mode_log),
            "lessons": self.lessons.to_json(),
            "lessons_added_tonight": [lesson.check for lesson in self.lessons_added],
            "live_gate_blockers": list(
                live_gate_blockers(
                    paper_nights_completed=0,
                    acceptance_tests_passed=False,
                    owner_typed_live=False,
                    live_executor_exists=False,
                    per_order_approval_exists=self._approve is not None,
                    settings=self.settings,
                )
            ),
        }


class _Mark:
    """Where the desk's running lists stood when a tick began."""

    def __init__(self, desk: Desk) -> None:
        self.skips = len(desk.skips)
        self.alerts = len(desk.alerts)
        self.lessons = len(desk.lessons_added)
