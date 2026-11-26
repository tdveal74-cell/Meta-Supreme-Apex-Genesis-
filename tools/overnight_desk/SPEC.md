# Overnight Desk paper engine: the contract

This file is the contract every module is built and tested against. "Source"
means the attached prompt, "Claude Overnight Desk 3.0", 96 lines. "Source line
N" is a line of that file.

The source is a third party's published prompt and is not copied into this
repository. Its SHA-256 is
`56761759790db188df6c293bf7f0bae3d364a5772958d452ae8426c67a0a4a62`. Anyone
holding the file can check a line reference against it. Nothing in the
repository can, and no test claims to.

Three labels run through this document:

- DOC: the source states it. The line is given.
- INVENTED: the source names it and does not define it, or its words allow
  more than one reading and this build picked one. The definition here was
  written for this build and waits on the owner's review.
- OWNER: a risk or cost number the source never states. It has no default.

## Scope

Built: the five bots' rules as pure functions, the market mode, a paper
executor with an explicit cost model, a ledger, the lessons loop, and a replay
over recorded snapshots.

The desk has no source of data. Nothing in this build produces a snapshot. It
runs on a timeline someone hands it, and the only timeline in the repository
is a synthetic one written to exercise the rules. No real night has been
recorded or replayed.

Not built, on purpose:

- Any code that reads from or acts on FOMO. No browser lane, no session token,
  no private interface. On 2026-11-26 the owner picked the card option "Build
  toward the full desk". That option's own text said the session token lane
  would not be built and the click lane would come back to him on a card of
  its own. He has not ruled on either lane beyond that.
- A producer of snapshots: the read-only adapter for public market data
  (STEPS.md, step 14). It waits on a ruling about data sources.
- NEWS, COPY, WAVE and TREND entry rules (source lines 69, 70, 72, 74). NEWS
  needs a judgment about a "real source story". COPY needs the venue's
  leaderboard. WAVE and TREND give no thresholds. `entry_signal` answers
  `strategy_not_built` for all four.
- The "sold the news" exit (source line 63). It has no definition.
- Narrative tagging (source line 42).
- The social check by X search (source line 54). `social_score` is a field a
  timeline may carry. Nothing here fetches or computes it.
- Detection of a copycat name and of a dangerous delegation (source lines 42
  and 53). `copycat_of` and `dangerous_delegation` are fields a timeline may
  carry. Nothing here works them out.
- The cap of $25 a ticket on the first three live nights (source line 80).
  There is no live path, so there is nothing to cap, and no setting for it.
- Order verification three ways (source line 83). No real order is sent.
- The venue web lessons file (source line 86).
- The weekly review that proposes setting changes (source line 89).
  `lessons.apply_review` applies changes a person approved. Nothing proposes
  them.
- Any live executor. Nothing constructs one.

Built although nothing uses it yet, so the owner knows it is there:
`ExecutorKind.LIVE`, the `Executor` protocol the desk accepts, the `approve`
callback, and `live_gate.py`. They exist so the per-order approval gate and
the live gate can be tested. STEPS.md proposes the steps the source leaves
undefined.

General rules for every module:

- Python 3.11, standard library only. No network, no clock, no randomness.
  The time is always `snapshot.ts` or an argument.
- No module mutates its inputs. Dataclasses are frozen.
- Every refusal carries a `reason_code` from this file, spelled exactly.
- An unknown (`None`) never passes a safety check. "When in doubt, no trade"
  (source line 92).
- Comparisons are plain floating point comparisons with no tolerance. A value
  within one rounding step of a threshold can land on either side of it. The
  one exception is the loss budget, where the desk decides once and the
  report reads that verdict.
- No em dashes or en dashes in any file.

## Readings of the source where it contradicts itself

R1. RED mode. Source lines 4 and 57 say RED means no new buys. Lines 60, 73
and 77 describe RED as a half-size trading mode. This build takes the stricter
reading: in RED the brain skips every buy. The RED figures at lines 60 and 73
(take at 1.5 times, 20% trail, 90 minute time stop) govern positions that are
already open. RED is a market mode here and is not a Strategy.

R2. A sale that does not happen. Source line 63 says the desk "sells 100% at
-25%". Lines 60 and 83 say an unverified order is never retried. No real order
is sent in this build, so nothing is ever unverified and that conflict does
not arise. It must be ruled on before any live executor exists.

A paper sale can still fail to happen, in two ways: the model cannot price it
(the pool's liquidity or the price is unknown), or an executor that is not the
paper one has no approval for it. INVENTED: the desk then leaves the position
as it was, records the alert `exit_not_executed` and the rule violation
`exit_not_executed`, and tries again on the next tick's reading. No order was
sent, so trying again is not a retry of an unverified order. The night's
fourth morning check fails. See "engine.py".

R3. Withdraw. Out of scope. Nothing here touches funds.

R4. The night stop (source line 73, listed under RED). This build applies it
in every mode: once the night's loss reaches `night_stop_pct` of the equity the
night started with, the brain skips every buy. Open positions keep their own
exits. INVENTED: the basis (starting equity) and the scope (all modes). The
night's loss is measured inside the tick, after that tick's prices are in and
after that tick's sells.

R5. The blocking proof. Source line 37 says "No PAPER night until"
getProgramAccounts succeeds on both token programs. This build runs no paper
night. A paper night, here, means a full night of real recorded readings
replayed through the desk (STEPS.md, step 14), and none exists. The synthetic
replay is a test of the rules. The proof at line 37 has not been met and is
not claimed.

R6. RED and the trail. Source line 77 says RED "tightens takes and trails".
Line 73 gives RED a 20% trail. The source gives GREEN no trail figure at all.
For line 77 to mean anything GREEN's trail has to be wider than 20, so
`trail_green_pct` defaults to 25 (INVENTED) and `Settings` refuses a RED trail
or a RED take that is not below GREEN's.

R7. The top 10 share at exactly 25%. The scanner kills above
`top10_max_pct` (source line 42, "top 10 > 25%"). Layer 4 passes only below
it (source line 49, "Top 10 < 25%"). One setting serves both, so a coin at
exactly 25 survives the scanner and stops at layer 4. That follows both lines
as written.

## Definitions this build chose

Each of these is INVENTED in the sense above: the source uses the word and
this build had to decide what it means.

- "Liquidity" is the value of both sides of the pool. The source says "$20k"
  and "2% of pool liquidity" and does not say one side or both. Under this
  reading a $20,000 pool holds $10,000 a side. A one-sided reading would make
  the floor and the 2% cap twice as strict.
- The scanner's ten minute watch starts when the desk first sees the coin, not
  when the coin graduated.
- A coin unseen for longer than `scanner_max_gap_s` starts its watch again.
- GRAD has no upper age limit. The source says "fresh" and gives no number.
- DIP is any pullback inside its age window. The source says "first clean
  pullback after the initial impulse"; "first", "clean" and "initial impulse"
  are not modelled, apart from the rule that a coin is traded once a night.
- The desk tries GRAD before DIP.
- Missing market data blocks every buy.
- "Pulled liquidity" is liquidity under the floor, or a fall of
  `liquidity_pull_drop_pct` from the liquidity at entry.
- "Dev dumping" is the creator having sold since entry.
- A venue warning is any non-empty warning text.
- "Dead money (3h under +5%)" is tested at the three hour mark and after: the
  gain then, not the gain throughout.
- The RED time stop counts from entry, whatever the mode was at entry.
- The order in which exits are checked.
- A reading older than `max_snapshot_age_s` is never bought on.

## Settings

`settings.py` is written. `Settings.from_dict` refuses unknown names, missing
OWNER values and anything outside its range. Tests use `Settings.for_tests()`,
whose OWNER values are placeholders and no recommendation.

Cross checks, each a `SettingsError`: `score_full` at or above `score_pass`;
`dip_age_max_s` above `dip_age_min_s`; `score_flush_full_max_pct` above
`score_flush_full_min_pct`; `max_ticket_usd` at or above `min_ticket_usd`;
`trail_red_pct` below `trail_green_pct` and `take_multiple_red` below
`take_multiple_green` (R6); `score_antichase_full_below_pct` below
`pump_1h_kill_pct`, so a coin at the kill level cannot earn full anti-chase
points.

Every setting is read by some module. A test fails when one is not, because a
setting nothing reads looks like a rule that is enforced.

## Data

`model.py` is written. Read it before writing any module. `positions.py` is
written: `open_position`, `realized_pnl`, `apply_exit_fill`.

### What a snapshot's fields mean

No producer of snapshots exists in this build, so nothing here computes these.
This is the definition a producer would have to meet. Every field but `ts`,
`mint` and `symbol` may be `None`, which means unknown.

| field | meaning |
|---|---|
| `ts` | when the reading was taken, in whole seconds |
| `pool_created_ts` | when the pool was created |
| `liquidity_usd` | value of both sides of the pool, in dollars |
| `price_usd` | spot price of one token |
| `high_10m_usd` | highest price in the ten minutes up to `ts` |
| `change_1h_pct` | price change over the hour up to `ts`, in percent |
| `buys_5m`, `sells_5m` | number of buys and of sells in the five minutes up to `ts` |
| `sell_volume_5m_usd` | dollars sold in the five minutes up to `ts` |
| `sell_volume_prev_5m_usd` | dollars sold in the five minutes before those |
| `holders` | holders at `ts` |
| `holders_prev` | holders at the reading before this one |
| `top10_pct`, `dev_pct`, `insiders_pct` | share of supply held by the ten largest holders, by the creator, by insiders |
| `dev_has_sold` | whether the creator has sold any tokens |
| `lp_locked_or_burned_pct` | share of the pool's own tokens locked or burned |
| `bundled_wallets` | number of wallets that bought together at launch |
| `copycat_of` | the name of an older coin this one copies, or empty |
| `social_score` | points from a social check. Trusted as given, and capped at `social_max_bonus` |
| `venue_warning`, `trading_disabled` | what the trading venue says about the coin |

`social_score` can lift a coin over the pass line and nothing here audits it.
A producer that sets it carries that weight.

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
- `blocks_new_buys` is true when the mode is RED or QUIET (source line 57,
  and R1), or when `data_ok` is false. The second half is INVENTED: the source
  does not say what to do with missing market data, and "when in doubt, no
  trade" (line 92) is the reason for blocking. One missing input, the
  graduation count for example, blocks every buy in an otherwise GREEN market.
- `reasons` names each trip and each missing input in plain words, for example
  `btc_1h -3.10 <= -2.50` and `fear_greed missing`.
- When `market` is `None` the mode is GREEN, `data_ok` is false,
  `blocks_new_buys` is true and `reasons` is `("market snapshot missing",)`.
- The missing-input reasons are `btc_1h missing`, `sol_1h missing`,
  `fear_greed missing` and `graduations missing`. A QUIET result adds a reason
  of the form `graduations 3 <= 5`. In RED a known graduation count adds no
  reason, because it did not set the mode.

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
- INVENTED: when the time since the last observation of a mint is strictly
  greater than `scanner_max_gap_s`, the watch starts again and `first_seen_ts`
  becomes `snap.ts`. A gap exactly equal to the setting does not restart it.
  The kill rules still run on that reading. With no kill, the reading that
  restarts the watch is WATCHING with `reason_code` `watching` and a detail
  that starts `watch restarted after a gap of`. A killed coin stays killed
  whatever the gap. Without this rule a coin unseen for hours would pass on
  its first reading back, with no kill test run on anything in between. The
  default equals the watch period; a real feed should set it near its own
  polling interval.
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
- PASSED carries `reason_code` `passed`. It is recomputed on every observation:
  a passed coin whose liquidity, top 10 share or 1 hour change later reads
  `None` goes back to WATCHING with `waiting_for_data`.
- An unknown value never trips a kill. It holds the coin at `waiting_for_data`
  once the watch is over.
- The `detail` text of a result is free wording and no part of the contract.

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

GRAD has no liquidity floor of its own in `entry_signal`. The scanner's kill
and the pre-trade recheck both apply the floor before any order.

Two simplifications, both listed under "Definitions this build chose": GRAD
has no upper age limit, and DIP does not model "first", "clean" or "initial
impulse".

### pre_trade_recheck

DOC, source line 60: the executor re-checks liquidity, price, cash and venue
warnings right before acting. Returns every reason to abort, in this order,
and an empty tuple when there is none.

In this build the desk calls it with the same snapshot as `decision` and as
`fresh`, because it has one reading per coin per tick. So `stale_snapshot` and
`price_drifted` cannot fire inside the desk, and `insufficient_cash` cannot
either, because the brain already capped the ticket at free cash. The function
is tested with two different snapshots. The desk's own guard against an old
reading is `max_snapshot_age_s` (see "engine.py"). Price drift between the
decision and the order is not guarded until a producer supplies a second
reading, and the morning report says so on every night.

- `stale_snapshot`: `fresh.ts < decision.ts`.
- `liquidity_unknown`, or `liquidity_below_floor`.
- `ticket_exceeds_liquidity_cap`: the ticket is above `pool_liquidity_cap_pct`
  percent of `fresh.liquidity_usd`.
  Skipped when that liquidity is `None`, since `liquidity_unknown` already
  reports it.
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

- `ValueError` when `snap.mint` differs from `position.mint`.
- When `snap.price_usd is None`, the exits that need no price still run, in
  the order below: venue warning (2), dev sold (3), liquidity pulled (4) and
  the RED time stop (6). Stop or trail (1), the first take (5) and dead money
  (7) need a price and are skipped. The position comes back exactly as it was
  passed in, peak and stop untouched, with or without a decision. A missing
  price must not hide a drained pool.
- `peak_price = max(peak_price, price)`.
- When `took_first_take` is true, the stop trails: `stop_price` becomes the
  larger of itself and `peak_price * (1 - trail / 100)`, where `trail` is
  `trail_red_pct` in RED and `trail_green_pct` otherwise (the green figure is
  INVENTED).
- The stop never moves down. The returned `stop_price` is never below the one
  passed in.
- Exit check 1 below uses the stop after this update. On the call that returns
  TAKE the stop is not trailed. Trailing starts on the next call.
- "Held" time is `snap.ts - position.entry_ts`. Every threshold is read from
  `settings`, never from a constant.

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

The figures above are the source's. Several of the readings are this build's
and are listed under "Definitions this build chose": what counts as pulled
liquidity, as dev dumping and as a venue warning, when dead money is tested,
where the RED time stop counts from, and the order of the seven checks.

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
  The three parts are separated by whitespace. The number is ASCII digits with
  an optional sign, decimal point and exponent. `nan`, `inf`, an underscore, or
  a digit from another script is refused.
- `check_hits` is true when the condition holds. It is also true when the
  field's value is unknown, because an unknown never passes.
  A value of `None` or NaN is unknown. A `Check` built by hand with an
  operator outside the four raises `LessonError`.
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
  It also returns `None` unless the exit fill itself lost money, that is
  `positions.realized_pnl(position, exit_fill) < 0`. A value that is not
  finite is left out like an unknown one. The number in the check is written
  with `repr(float(value))`, so the derived text always parses.

  How far this rule reaches, which the owner should see before ruling on it.
  A typical losing coin's closest field is its liquidity. A loss on a coin
  that entered with $40,000 of liquidity writes `liquidity_usd <= 40000.0`.
  That check then blocks every later coin at or under $40,000, and every coin
  whose liquidity is unknown, for as long as the lesson book lives. With the
  floor at $20,000, one loss can close most of the range the desk trades in.
  The lesson says "be pickier than the last loser". It does not say what went
  wrong. The fixture night shows it: the second coin is blocked by the first
  loser's lesson.

  A departure from the source: lines 63 and 88 say every loss writes a lesson.
  Here a loss can end with none, when no candidate field qualifies or when the
  last fill on its own did not lose. The morning report counts those losses.
  The second morning check does not fail on them.
- `apply_review`: source line 89. Raises `LessonError` when `approval` is
  `None`, when it names no person (`approved_by` must be text with a visible
  character) or carries no time (`approved_ts` must be a whole number above
  0), and then when `changes` has more than 3 entries, in that order. The
  approval's `order_id` is not checked, because a review is not an order.
  Otherwise returns `Settings.from_dict` of the current values with the
  changes applied, so the range checks run.
  An unknown setting name or a value outside its range therefore raises
  `SettingsError`.
- `LessonBook.from_json` raises `LessonError` for a row that lacks
  `lesson_id`, `created_ts`, `source_mint` or `check`, or that has a key it
  does not know. `why` may be left out. Two lessons are the same when their
  check text is equal character for character.

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
Zero and NaN count as not positive. A BUY given `qty`, a SELL given `usd`, a
fee setting that is `None`, and an order so small it would return no tokens
are each a `PaperError` too.

One exception, INVENTED: a SELL into a drained pool. When the side is SELL and
`snap.liquidity_usd` is known and exactly 0, the quote is a total loss:
`qty` is the amount offered, `fill_price`, `gross_usd` and all three fees are
0.0, `price_impact_pct` is -100.0, and `spot_price` is the snapshot's price
when that is above 0 and 0.0 otherwise. This path needs no price. The
argument checks above still run first. A pool with nothing in it pays
nothing, and the model charges no fee on a swap that returns nothing. A real
venue might still charge a network fee; the model does not guess one.
Liquidity that is `None`, negative or NaN is still refused on both sides, and
so is a BUY into a drained pool.

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

For any `kind` but PAPER it raises `ApprovalRequired`, checking in this
order: `approval` is `None`; its `order_id` differs from the intent's; it
names no person (`approved_by` must be text with a visible character); it
carries no time (`approved_ts` must be a whole number above 0). This is the
per-order human gate. It is the default for anything live and is not a
setting.

What the gate is and is not. It checks that an approval naming someone, for
this one order, was handed over. It cannot check that a person stands behind
the name: any code can build a `HumanApproval`. Proving that is the job of
whatever supplies the approval, and nothing in this build does.

### PaperExecutor.execute

`PaperExecutor(settings)` is the constructor. `PaperError` when
`snapshot.mint` differs from `intent.mint`. `Fill.ts` is `snapshot.ts`, and
the mint and symbol come from the intent.

Calls `require_approval` with its own kind, then `model_quote`. A BUY needs
`intent.usd`, a SELL needs `intent.qty`; `PaperError` otherwise. The Fill has
`verification = Verification.PAPER`, `price = quote.fill_price`,
`gross_usd = quote.gross_usd`, `fees_usd = quote.fees_usd`, and carries the
intent's `exit_reason`. `cash_delta_usd` is `-usd` for a BUY and
`gross_usd - venue_fee_usd - fixed_fee_usd` for a SELL, never below zero.

For a BUY, `gross_usd` is the amount sent to the pool, pool fee included, and
`fees_usd` lists the pool fee as well, so the two add up to more than `usd`.
`cash_delta_usd` is the only figure that moves cash.

### Ledger

- `record_buy`: `PaperError` when the fill is not a BUY, when a position in
  that mint is already open (source line 60, never average down), or when the
  cost is above `cash_usd`. Also when `position.mint` differs from
  `fill.mint`. Otherwise cash falls by the cost, the position is
  stored, fees are added and the fill is appended.
- `record_sell`: `PaperError` when there is no position in that mint. Uses
  `positions.realized_pnl` and `positions.apply_exit_fill`. Cash rises by
  `cash_delta_usd`. A closed position is removed. Returns the realized pnl and
  adds it to `realized_pnl_usd`.
- `exposure_usd`: the sum of `cost_usd` over open positions.
- `equity_usd`: cash plus, for each open position, `qty` times the price given
  for its mint, or its `cost_usd` when no price is given.
  A price of 0.0 is a price: it values the position at zero.
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

Each of the four booleans must be exactly `True` to clear its blocker. `None`
or any other value leaves the blocker in place. "Always present" describes
this build, where nothing passes `live_executor_exists=True`; the function
itself follows its argument.

## engine.py

```python
class Desk:
    def __init__(self, settings, starting_cash_usd, executor=None, lesson_book=None,
                 strategies=(Strategy.GRAD, Strategy.DIP), approve=None) -> None
    def tick(self, now: int, market: MarketSnapshot | None,
             snapshots: Sequence[TokenSnapshot]) -> TickReport
    def night_report(self) -> dict
```

One Desk is one night. With no executor given it uses the paper executor.
`starting_cash_usd` must be a positive, finite number, or the constructor
raises `ValueError`.

`tick` raises `ValueError` when `now` is earlier than the last tick, when two
snapshots share a mint, when a snapshot's `ts` is after `now`, or when a
snapshot is older than the last one the desk saw for that coin. A snapshot
stamped exactly at `now`, or at the same time as the coin's last one, is
accepted. Every one of those checks runs before anything is changed, so a
refused tick leaves the desk exactly as it was.

After those checks `tick` does not raise on a well formed tick. An order that
is not filled is recorded and the tick carries on, so trouble with one
position never stops the next position's stop from being checked. The one
thing still raised is a fill the ledger cannot record, which would be a bug
in an executor.

A price of 0.0 is a reading. It is kept as the coin's last price and values a
held coin at nothing.

Then, in this order:

1. Market mode: `market_mode.assess`.
2. Risk pass, before any buy (DOC, source line 63, "sells jump the click
   queue"). Open positions are visited in mint order.
   - A position with no snapshot this tick gets the alert
     `no_reading_for_position` and is left alone.
   - INVENTED: a snapshot older than `max_snapshot_age_s` gets the alert
     `stale_reading_for_position`. Risk still acts on it, because an old
     reading is better than none for an exit.
   - `risk.evaluate` runs. With no decision and no price, the alert is
     `no_price_for_position`.
   - An exit decision becomes a SELL intent for `qty * fraction`.
   - INVENTED (R2): when that sell is not filled, the position is left exactly
     as it was (same quantity, same stop, a first take not marked as taken),
     the alert `exit_not_executed` is recorded, and so is a rule violation
     `exit_not_executed`, once per position and exit reason however many
     ticks it lasts. The next tick tries again on its own reading.
3. Scan pass: every snapshot goes to the scanner, in mint order. A coin that
   is held is not considered for a buy. A coin that is not PASSED is skipped
   at stage `scanner` with the scanner's reason code.
4. Buy pass, for PASSED coins not held:
   - INVENTED: a coin bought once tonight is skipped at stage `desk` with
     `already_traded_tonight`. This also means no averaging down (DOC, source
     line 60).
   - `analyst.analyse`. A failed audit is skipped at stage `analyst` with
     `layer_<n>_red` or `layer_<n>_unknown`.
   - INVENTED: survivors are tried best total score first, ties by mint.
   - `brain.size_ticket`, given the first blocking lesson if any. A skip is
     recorded at stage `brain` with the brain's reason code.
   - `entry.entry_signal` for each strategy in order (GRAD, then DIP, unless
     the caller says otherwise). The first that fires names the position's
     strategy. When none fires the skip is `no_entry_signal` at stage
     `executor`, and its detail lists each strategy's reason.
   - INVENTED: a snapshot older than `max_snapshot_age_s` is skipped at stage
     `executor` with `stale_snapshot`. One exactly at the limit is allowed.
   - `entry.pre_trade_recheck`, called with the same snapshot twice (see
     "entry.py"). Any reason is a skip at stage `executor` with the first
     reason as its code.
   - A BUY intent for the ticket. When it is not filled the skip is at stage
     `executor`, with `approval_missing` when the human gate refused it and
     `order_refused` when the executor did (for example a ticket no larger
     than the flat fee). A refused buy does not use up the coin's one trade
     for the night.
   - Otherwise `positions.open_position` and `Ledger.record_buy`. The
     portfolio view is rebuilt before each candidate, so a second buy in one
     tick sees the cash the first one spent.

Every intent goes through `_execute`, which calls `paper.require_approval`
with the executor's kind before the executor runs. For a kind other than
PAPER it first asks the `approve` callback for a `HumanApproval`. With no
callback, an approval for another order, or one that names no person or
carries no time, nothing is executed. This gate is in the desk itself, so an
executor cannot skip it. It covers sells as well as buys. `_execute` returns
the fill, or the code `approval_missing` or `order_refused` with the reason.
An executor refuses an order by raising `paper.PaperError`.

What that means for a live run, and why it must be ruled on: a stop on an
executor that is not the paper one needs a person's approval for that one
sell. Without it the stop is not carried out, and the desk reports a
violation. An unattended stop and a per-order human approval cannot both
hold.

A skip is recorded when a coin's (stage, reason) pair changes, and is not
repeated on every tick (INVENTED). An alert on a held coin is recorded when
it starts and again only after it has cleared (INVENTED). So the counts in
the report are changes, not ticks.

When a position closes at a net loss across all of its fills:

- `lessons.derive_lesson` runs and the lesson is added to the book. A lesson
  the book already holds is not counted as added tonight.
- The loss is recorded with its exit reason, its size in dollars and as a
  share of the free cash held when that position was opened, and
  `over_budget`.
- `over_budget` is true when the loss is larger than `risk_per_trade_pct` of
  that cash by more than a billionth of a dollar. A violation
  `loss_exceeded_risk_budget` is recorded then. The source's own standard at
  line 94 is that no loss exceeds 3% of cash. The desk cannot guarantee that:
  a price that gaps through the stop, or a drained pool, takes the whole
  ticket. It reports every time it fails.

`night_report` returns plain JSON-ready data: how many ticks ran, how many
readings and different coins were seen, the first and last tick, the account,
every fill, every skip with its reason and a count by reason, losses with
autopsies, violations, alerts, the mode log, lessons, a count of fills by
verification kind, the number of real orders sent (verified and unverified
both count), each open position with its last price and the time of its last
reading, the live gate's blockers, and `recheck_source`, which is
`same_snapshot` in this build.

## report.py

```python
def morning_checks(report: dict, risk_per_trade_pct: float) -> list[dict]
def render_morning(report: dict, risk_per_trade_pct: float) -> str
```

DOC, source line 94. `morning_checks` answers the four tests of that line from
the night's data: a reason for every skip, every loss within the risk budget
with an autopsy, zero unverified orders, zero rule violations. A paper fill is
never counted as a verified order.

INVENTED: each check's `ok` is `True`, `False` or `None`, printed `pass`,
`FAIL` and `n/a`. `None` means the night gave the check nothing to test:

- "a reason for every skip" is `None` when no coin was seen.
- "every loss within the budget" is `None` when no position closed at a loss.
- "zero unverified orders" is `None` when no real order was sent, which is
  every paper night.
- "zero rule violations" is `None` when no tick ran.

A night that tested nothing therefore prints four `n/a` lines and no `pass`.

The autopsy is the loss record itself: exit reason, entry and exit price, and
the loss in dollars and as a share of the cash held at entry. A loss with no
exit reason fails the second check. So does a loss the desk marked
`over_budget`, or one whose share of cash was not measured. The report reads
the desk's `over_budget` verdict and does not work the comparison out again,
so the check and the violation list cannot disagree. A loss that produced no
lesson does not fail the check; the evidence line counts those.

`render_morning` also prints what the desk saw (ticks, readings, coins, first
and last tick), with a line in capitals when no coin was seen, and a section
"Not tested by this night" that names order verification on a paper night
and price drift between the decision and the order.

Coin symbols and names are text a stranger chose. Every piece of free text is
escaped before it is printed: a character that is not printable is written as
a backslash, `u` and its code. A symbol cannot add a line to the report.

## replay.py

```python
def parse_frame(obj, where="frame") -> Frame
def load_timeline(path) -> list[Frame]
def run(frames, settings, starting_cash_usd) -> dict
def main(argv=None) -> int
```

Reads a JSON Lines timeline and a settings file from disk, runs a fresh paper
Desk over the frames and prints the morning report. An unknown key or field
name is a `TimelineError`, so a typo cannot pass as a missing reading.

Every value is checked against the type of its field in `model.py`. A number
field takes a JSON number and never a string or a boolean. A whole-number
field refuses a fraction. `NaN`, `Infinity` and a number too large to be
finite are refused. A null is accepted only where the field may be unknown.
So a wrongly typed reading is refused at the door and can never reach a
comparison.

INVENTED bounds. A number, the tick time included, must lie between minus and
plus `MAX_NUMBER` (1e15). A piece of text must be printable and at most
`MAX_TEXT` (200) characters, and a list of tags holds at most `MAX_TAGS` (32).
A value outside them is refused and never repaired: a changed name or number
is worse than no run. A recorder that writes timelines has to clean its own
text first.

`main` returns 0 on success and 2 on a refused input, with one line starting
`refused:` on standard error and no traceback. Refused inputs include a cash
amount that is not positive and finite, a malformed timeline, a number too
large to work with, ticks out of order, a snapshot older than the coin's last
one, and two snapshots for one coin in a tick. It opens no connection.
