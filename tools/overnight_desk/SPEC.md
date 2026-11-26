# Overnight Desk paper engine: the contract

This file is the contract every module is built and tested against. "Source"
means the attached prompt, "Claude Overnight Desk 3.0", 96 lines. "Source line
N" is a line of that file.

Three labels run through this document:

- DOC: the source states it. The line is given.
- INVENTED: the source names it and does not define it. The definition here was
  written for this build and waits on the owner's review.
- OWNER: a risk or cost number the source never states. It has no default.

## Scope

Built: the five bots' rules as pure functions, the market mode, a paper
executor with an explicit cost model, a ledger, the lessons loop, and a replay
over recorded snapshots.

Not built, on purpose:

- Any code that reads from or acts on FOMO. No browser lane, no session token,
  no private interface. The owner ruled on 2026-11-26 that each such lane
  returns on its own card.
- NEWS, COPY, WAVE and TREND entry rules (source lines 69, 70, 72, 74). NEWS
  needs a judgment about a "real source story". COPY needs the venue's
  leaderboard. WAVE and TREND give no thresholds. `entry_signal` answers
  `strategy_not_built` for all four.
- The "sold the news" exit (source line 63). It has no definition.
- Narrative tagging (source line 42).
- Any live executor. `ExecutorKind.LIVE` exists so the approval guard can be
  tested. Nothing constructs one.

General rules for every module:

- Python 3.11, standard library only. No network, no clock, no randomness.
  The time is always `snapshot.ts` or an argument.
- No module mutates its inputs. Dataclasses are frozen.
- Every refusal carries a `reason_code` from this file, spelled exactly.
- An unknown (`None`) never passes a safety check. "When in doubt, no trade"
  (source line 92).
- No em dashes or en dashes in any file.

## Readings of the source where it contradicts itself

R1. RED mode. Source lines 4 and 57 say RED means no new buys. Lines 60, 73
and 77 describe RED as a half-size trading mode. This build takes the stricter
reading: in RED the brain skips every buy. The RED figures at lines 60 and 73
(take at 1.5 times, 20% trail, 90 minute time stop) govern positions that are
already open. RED is a market mode here and is not a Strategy.

R2. A failed sale. Source line 63 says a loser is always sold. Lines 60 and 83
say an unverified order is never retried. The paper executor cannot fail, so
the conflict does not arise in this build. It must be ruled on before any live
executor exists.

R3. Withdraw. Out of scope. Nothing here touches funds.

R4. The night stop (source line 73, listed under RED). This build applies it
in every mode: once the night's loss reaches `night_stop_pct` of the equity the
night started with, the brain skips every buy. Open positions keep their own
exits. INVENTED: the basis (starting equity) and the scope (all modes).

## Settings

`settings.py` is written. `Settings.from_dict` refuses unknown names, missing
OWNER values and anything outside its range. Tests use `Settings.for_tests()`,
whose OWNER values are placeholders and no recommendation.

## Data

`model.py` is written. Read it before writing any module. `positions.py` is
written: `open_position`, `realized_pnl`, `apply_exit_fill`.

## market_mode.py

```python
def assess(market: MarketSnapshot | None, settings: Settings) -> MarketState
```

DOC, source line 77.

- RED when any known input trips: `btc_change_1h_pct <= red_btc_1h_pct`, or
  `sol_change_1h_pct <= red_sol_1h_pct`, or `fear_greed <= red_fear_greed_max`.
- QUIET when not RED and `graduations_last_hour` is known and is at or below
  `quiet_max_graduations_per_hour` (INVENTED threshold).
- GREEN otherwise.
- `data_ok` is false when `market` is `None` or any of the four inputs is
  `None`.
- `blocks_new_buys` is true when the mode is RED or QUIET, or `data_ok` is
  false (source line 57, and R1).
- `reasons` names each trip and each missing input in plain words, for example
  `btc_1h -3.10 <= -2.50` and `fear_greed missing`.

## scanner.py

```python
class Scanner:
    def __init__(self, settings: Settings) -> None
    def observe(self, snap: TokenSnapshot) -> ScanResult
    def result(self, mint: str) -> ScanResult | None
```

DOC, source line 42. One Scanner holds the state of every coin it has seen.

- The first observation of a mint sets `first_seen_ts = snap.ts`.
- An observation older than the last one for that mint raises `ValueError`.
- Kills, checked in this order, first hit wins, and a kill is permanent:
  1. `liquidity_below_floor`: liquidity known and below `liquidity_floor_usd`.
  2. `top10_above_max`: `top10_pct > top10_max_pct`.
  3. `pumped_1h`: `change_1h_pct >= pump_1h_kill_pct`.
  4. `copycat_name`: `copycat_of` is a non-empty string.
  5. `trading_disabled`: `trading_disabled is True`.
  6. `holders_leaving` (INVENTED definition): both holder counts known,
     `holders_prev > 0`, and `holders < holders_prev * (1 - holders_drop_kill_pct / 100)`.
- PASSED when not killed, `snap.ts - first_seen_ts >= scanner_watch_s`, and
  `liquidity_usd`, `top10_pct` and `change_1h_pct` are all known.
- When the watch is over and one of those three is unknown, the state stays
  WATCHING with `reason_code` `waiting_for_data`.
- Before the watch is over the state is WATCHING with `reason_code` `watching`.
- A coin that PASSED can still be KILLED by a later observation.
- A killed coin stays KILLED with its first kill reason whatever comes later.

## analyst.py

```python
def audit(snap: TokenSnapshot, settings: Settings) -> AuditResult
def score(snap: TokenSnapshot, settings: Settings) -> ScoreBreakdown
def analyse(snap: TokenSnapshot, settings: Settings) -> tuple[AuditResult, ScoreBreakdown | None]
```

### audit

DOC, source lines 45-53. Eight layers in order. Evaluation stops at the first
layer that is not green, and `layers` ends there. `passed` is true only for
eight greens. `first_failure` is the layer that stopped it.

| n | name | green | red | unknown |
|---|---|---|---|---|
| 1 | `mint authority revoked` | `mint_authority_revoked is True` | `False` | `None` |
| 2 | `freeze authority revoked` | `freeze_authority_revoked is True` | `False` | `None` |
| 3 | `dev holds under limit and has not sold` | `dev_pct < dev_max_pct` and `dev_has_sold is False` | `dev_pct >= dev_max_pct`, or `dev_has_sold is True` | otherwise |
| 4 | `top 10 under limit` | `top10_pct < top10_max_pct` | `>=` | `None` |
| 5 | `LP locked or burned` | `lp_locked_or_burned_pct >= lp_locked_min_pct` | below | `None` |
| 6 | `pool age` | `snap.ts - pool_created_ts >= pool_age_min_s` | younger | `None` |
| 7 | `bundles and insiders` | `bundled_wallets < bundled_wallets_max` and `insiders_pct < insiders_max_pct` | either at or over its limit | otherwise |
| 8 | `no dangerous delegations` | `dangerous_delegation is False` | `True` | `None` |

A red in one half of layer 3 or layer 7 is red even when the other half is
unknown.

### score

INVENTED, formula v0. The source names five parts at line 54 and defines none.
Four parts are worth 0 to 25 each. Any input a part needs that is `None` makes
that part 0.

- `alive = 25 * min(1, (buys_5m + sells_5m) / score_alive_trades_full)`
- `organic = 25 * (1 - top10_pct / top10_max_pct)`, held to the range 0 to 25.
- `flush`, from the pullback `p = (high_10m_usd - price_usd) / high_10m_usd * 100`.
  Let `lo = score_flush_full_min_pct` and `hi = score_flush_full_max_pct`.
  `p <= 0` gives 0. From 0 to `lo` it rises in a straight line to 25. From `lo`
  to `hi` it is 25. From `hi` to `hi + (hi - lo)` it falls in a straight line
  to 0. Beyond that it is 0. `high_10m_usd <= 0` gives 0.
- `anti_chase`, from `g = change_1h_pct`. At or below
  `score_antichase_full_below_pct` it is 25. From there it falls in a straight
  line to 0 at `pump_1h_kill_pct`. At or above that it is 0.
- `social = min(social_max_bonus, max(0, social_score))`, and 0 when
  `social_score` is `None`. It can only raise the score (source line 54).
- `total = min(100, alive + organic + flush + anti_chase + social)`.
- `passed = total >= score_pass`. `size_tier` is `full` at or above
  `score_full`, `half` from `score_pass`, and `none` below (DOC, source lines
  54 and 57).

### analyse

Runs `audit`. Returns `(audit_result, None)` when it did not pass. Runs `score`
only for a coin with eight greens (source line 54).

## entry.py

```python
def entry_signal(snap: TokenSnapshot, strategy: Strategy, settings: Settings) -> EntrySignal
def pre_trade_recheck(
    decision: TokenSnapshot, fresh: TokenSnapshot, ticket_usd: float,
    free_cash_usd: float, settings: Settings, executor_kind: ExecutorKind,
) -> tuple[str, ...]
```

### entry_signal

Checks run in this order and the first failure sets `reason_code`.

1. `strategy_not_built` when the strategy is not in `BUILT_STRATEGIES`.
2. `dip_data_missing` when `price_usd`, `high_10m_usd`, `pool_created_ts`,
   `liquidity_usd`, `sell_volume_5m_usd` or `sell_volume_prev_5m_usd` is
   `None`, or `high_10m_usd <= 0`.
3. Strategy rules.
   - DIP (DOC, source line 68): `age_outside_window` unless the pool age is
     from `dip_age_min_s` to `dip_age_max_s` inclusive. `liquidity_below_floor`
     when liquidity is under `liquidity_floor_usd`.
   - GRAD (DOC, source line 71): `graduation_unknown` when
     `from_pumpfun_graduation is None`. `not_a_graduation` when it is `False`.
     `grad_wait` when the pool age is under `scanner_watch_s`.
4. `no_dip` unless the pullback from the 10 minute high is at least
   `dip_from_high_pct` (DOC, source line 60).
5. `sellers_not_drying_up` (INVENTED definition) unless
   `sell_volume_prev_5m_usd > 0` and
   `sell_volume_5m_usd <= sell_dryup_ratio * sell_volume_prev_5m_usd`.

When every check passes, `fires` is true and `reason_code` is `entry`.

### pre_trade_recheck

DOC, source line 60: the executor re-checks liquidity, price, cash and venue
warnings right before acting. Returns every reason to abort, in this order,
and an empty tuple when there is none.

- `stale_snapshot`: `fresh.ts < decision.ts`.
- `liquidity_unknown`, or `liquidity_below_floor`.
- `ticket_exceeds_liquidity_cap`: the ticket is above `pool_liquidity_cap_pct`
  percent of `fresh.liquidity_usd`.
- `price_unknown` (either price `None` or the decision price not positive), or
  `price_drifted` (INVENTED tolerance): the absolute move from the decision
  price is above `recheck_max_price_drift_pct` percent.
- `insufficient_cash`: the ticket is above `free_cash_usd`.
- `venue_warning`: `fresh.venue_warning` is a non-empty string.
- `trading_disabled`: `fresh.trading_disabled is True`.
- `venue_checks_missing`: only when `executor_kind` is LIVE, and
  `fresh.trading_disabled is None` or `fresh.venue_warning is None`. A paper
  run may proceed without venue checks. A live one may not.

## brain.py

```python
def size_ticket(
    score: ScoreBreakdown, snap: TokenSnapshot, portfolio: PortfolioView,
    market: MarketState, lesson: Lesson | None, settings: Settings,
) -> SizeDecision
```

DOC, source line 57, plus the OWNER limits. The brain sizes. It picks no coin
and executes nothing. Skips are checked in this order:

1. `market_blocks_buys` when `market.blocks_new_buys`.
2. `lesson_blocks` when `lesson` is not `None`.
3. `night_stop` when `night_start_equity_usd > 0` and
   `night_pnl_usd <= -night_stop_pct / 100 * night_start_equity_usd` (R4).
4. `score_below_pass` when `score.size_tier == "none"`.
5. `max_open_positions` when `open_positions >= max_open_positions`.
6. `liquidity_unknown` when `snap.liquidity_usd is None`.
7. `exposure_cap` when
   `max_total_exposure_pct / 100 * equity_usd - exposure_usd <= 0`.

Then `base = free_cash_usd * risk_per_trade_pct / stop_loss_pct`, halved for
the `half` tier. The ticket is the smallest of: `base`, `pool_liquidity_cap_pct`
percent of liquidity, `max_ticket_usd`, the exposure room from step 7, and
`free_cash_usd`.

8. `ticket_below_min` when the ticket is under `min_ticket_usd`.

A skip returns `ticket_usd = 0.0` with its `skip_reason_code`. A sized ticket
returns the amount with an empty `skip_reason_code`.

## risk.py

```python
def evaluate(
    position: Position, snap: TokenSnapshot, mode: Mode, settings: Settings,
) -> tuple[Position, ExitDecision | None]
```

DOC, source lines 60, 63 and 73. Returns the position with its peak and stop
brought up to date, and at most one exit decision.

- When `snap.price_usd is None`: return the position unchanged and no decision.
  The caller records an alert.
- `peak_price = max(peak_price, price)`.
- When `took_first_take` is true, the stop trails: `stop_price` becomes the
  larger of itself and `peak_price * (1 - trail / 100)`, where `trail` is
  `trail_red_pct` in RED and `trail_green_pct` otherwise (the green figure is
  INVENTED).
- The stop never moves down. The returned `stop_price` is never below the one
  passed in.

Exit decisions, first hit wins:

1. `price <= stop_price`: reason TRAIL when `took_first_take`, else STOP.
   Fraction 1.0.
2. VENUE_WARNING: `venue_warning` is a non-empty string. Fraction 1.0.
3. DEV_SOLD: `snap.dev_has_sold is True` and the entry snapshot's was not.
   Fraction 1.0.
4. LIQUIDITY_PULLED: liquidity known, and below `liquidity_floor_usd` or at or
   below `entry_liquidity_usd * (1 - liquidity_pull_drop_pct / 100)` when
   `entry_liquidity_usd > 0` (the drop figure is INVENTED). Fraction 1.0.
5. TAKE: `took_first_take` is false and
   `price >= entry_price * take_multiple`, with `take_multiple_red` in RED and
   `take_multiple_green` otherwise. Fraction `take_fraction`. The returned
   position has `took_first_take = True`.
6. RED_TIME_STOP: mode RED and `snap.ts - entry_ts >= red_time_stop_s`.
   Fraction 1.0.
7. DEAD_MONEY: `snap.ts - entry_ts >= dead_money_after_s` and
   `price < entry_price * (1 + dead_money_min_gain_pct / 100)`. Fraction 1.0.

`evaluate` never changes `qty` or `cost_usd`. The caller applies the fill with
`positions.apply_exit_fill`.

## lessons.py

```python
class LessonError(ValueError)
def parse_check(text: str) -> Check            # Check(field, op, value)
def check_hits(check: Check, snap: TokenSnapshot) -> bool
def derive_lesson(position: Position, exit_fill: Fill, settings: Settings) -> Lesson | None
def apply_review(settings: Settings, changes: dict, approval: HumanApproval | None) -> Settings

class LessonBook:
    def add(self, lesson: Lesson) -> Lesson
    def blocking(self, snap: TokenSnapshot) -> Lesson | None
    def to_json(self) -> list[dict]
    @classmethod
    def from_json(cls, rows: list[dict]) -> LessonBook
```

DOC, source lines 63 and 88-89. A lesson can only block.

- A check is `<field> <op> <number>`. Fields: `liquidity_usd`,
  `change_1h_pct`, `top10_pct`, `dev_pct`, `lp_locked_or_burned_pct`,
  `bundled_wallets`, `insiders_pct`, `holders`, `buys_5m`, `sells_5m`,
  `pool_age_s` (which is `snap.ts - pool_created_ts`). Operators: `>`, `>=`,
  `<`, `<=`. `parse_check` raises `LessonError` on anything else. It never
  calls `eval` or `exec`.
- `check_hits` is true when the condition holds. It is also true when the
  field's value is unknown, because an unknown never passes.
- `LessonBook.add` validates the check by parsing it. Adding a lesson whose
  check text matches an existing one returns the existing lesson. The book has
  no method that removes or weakens a lesson.
- `LessonBook.blocking` returns the first lesson, in the order added, whose
  check hits.
- `derive_lesson` (INVENTED rule). It looks at the entry snapshot of a losing
  position. Candidate fields and their limits: `top10_pct` against
  `top10_max_pct`, `dev_pct` against `dev_max_pct`, `insiders_pct` against
  `insiders_max_pct`, `bundled_wallets` against `bundled_wallets_max`, all
  "higher is worse", and `liquidity_usd` against `liquidity_floor_usd`, "lower
  is worse". Closeness is `value / limit` for the first four and
  `limit / value` for liquidity. Fields that are unknown, or whose limit or
  value is not positive, are left out. The closest field wins, ties going to
  the order listed. The check is `<field> >= <value>` for the first four and
  `liquidity_usd <= <value>` for liquidity. `lesson_id` is
  `L-<mint>-<exit_fill.ts>`. Returns `None` when no field qualifies.
- `apply_review`: source line 89. Raises `LessonError` when `approval` is
  `None` or when `changes` has more than 3 entries. Otherwise returns
  `Settings.from_dict` of the current values with the changes applied, so the
  range checks run.

## paper.py

```python
class PaperError(ValueError)
class ApprovalRequired(PermissionError)
def model_quote(side: Side, snap: TokenSnapshot, settings: Settings,
                usd: float | None = None, qty: float | None = None) -> Quote
def require_approval(intent: OrderIntent, kind: ExecutorKind, approval: HumanApproval | None) -> None
class PaperExecutor:            # kind = ExecutorKind.PAPER
    def execute(self, intent, snapshot, approval=None) -> Fill
class Ledger:
    def __init__(self, starting_cash_usd: float) -> None
    cash_usd: float
    positions: dict[str, Position]
    fills: list[Fill]
    realized_pnl_usd: float
    fees_usd: float
    def record_buy(self, fill: Fill, position: Position) -> None
    def record_sell(self, fill: Fill) -> float      # realized pnl of this fill
    def exposure_usd(self) -> float
    def equity_usd(self, prices: dict[str, float]) -> float
    def view(self, prices: dict[str, float], night_start_equity_usd: float) -> PortfolioView
```

The source says a PAPER fill is "taken from the quote" (line 80) and states no
cost anywhere. This build makes every cost explicit. The cost model is
INVENTED and its three rates are OWNER settings.

### model_quote

A constant-product pool. `L = snap.liquidity_usd` is the value of both sides,
so the dollar reserve is `Rq = L / 2` and the token reserve is
`Rt = Rq / snap.price_usd`. Let `v`, `p` and `f` be
`venue_fee_pct_per_side / 100`, `pool_fee_pct_per_side / 100` and
`fixed_fee_usd_per_side`.

Raises `PaperError` when liquidity or price is `None` or not positive, when
both or neither of `usd` and `qty` are given, or when the amount is not
positive. A BUY takes `usd`. A SELL takes `qty`.

BUY of `usd` dollars, all of which leaves the account:

- `venue_fee_usd = v * usd`, `fixed_fee_usd = f`.
- `to_pool = usd - venue_fee_usd - fixed_fee_usd`. `PaperError` when it is not
  positive.
- `pool_fee_usd = p * to_pool`. `effective = to_pool - pool_fee_usd`.
- `qty = Rt * effective / (Rq + effective)`.
- `gross_usd = to_pool`. `fill_price = to_pool / qty`.

SELL of `qty` tokens:

- `effective = qty * (1 - p)`.
- `gross_usd = Rq * effective / (Rt + effective)`.
- `pool_fee_usd = qty * p * snap.price_usd`, the pool's cut valued at spot.
- `venue_fee_usd = v * gross_usd`, `fixed_fee_usd = f`.
- `fill_price = gross_usd / qty`.

Both sides: `spot_price = snap.price_usd` and
`price_impact_pct = (fill_price / spot_price - 1) * 100`, which is positive
for a buy and negative for a sell.

### require_approval

Raises `ApprovalRequired` when `kind` is not PAPER and `approval` is `None` or
its `order_id` differs from the intent's. This is the per-order human gate. It
is the default for anything live and is not a setting.

### PaperExecutor.execute

Calls `require_approval` with its own kind, then `model_quote`. A BUY needs
`intent.usd`, a SELL needs `intent.qty`; `PaperError` otherwise. The Fill has
`verification = Verification.PAPER`, `price = quote.fill_price`,
`gross_usd = quote.gross_usd`, `fees_usd = quote.fees_usd`, and carries the
intent's `exit_reason`. `cash_delta_usd` is `-usd` for a BUY and
`gross_usd - venue_fee_usd - fixed_fee_usd` for a SELL, never below zero.

### Ledger

- `record_buy`: `PaperError` when the fill is not a BUY, when a position in
  that mint is already open (source line 60, never average down), or when the
  cost is above `cash_usd`. Otherwise cash falls by the cost, the position is
  stored, fees are added and the fill is appended.
- `record_sell`: `PaperError` when there is no position in that mint. Uses
  `positions.realized_pnl` and `positions.apply_exit_fill`. Cash rises by
  `cash_delta_usd`. A closed position is removed. Returns the realized pnl and
  adds it to `realized_pnl_usd`.
- `exposure_usd`: the sum of `cost_usd` over open positions.
- `equity_usd`: cash plus, for each open position, `qty` times the price given
  for its mint, or its `cost_usd` when no price is given.
- `view`: a `PortfolioView`, with
  `night_pnl_usd = equity_usd(prices) - night_start_equity_usd`.

## live_gate.py

```python
def live_gate_blockers(
    paper_nights_completed: int, acceptance_tests_passed: bool,
    owner_typed_live: bool, live_executor_exists: bool,
    per_order_approval_exists: bool, settings: Settings,
) -> tuple[str, ...]
```

DOC, source line 80, plus the per-order gate. Returns every blocker, in this
order: `paper_nights_short`, `acceptance_tests_not_passed`,
`owner_has_not_typed_live`, `no_live_executor`, `no_per_order_approval`. An
empty tuple means the gate is open. In this build `no_live_executor` is always
present, because none exists.

## engine.py, report.py, replay.py

Written after the modules above are merged. Their contract is added to this
file in that change.
