# Overnight Desk: the paper engine, built on Tee's ruling

Status record for the `claude/new-session-1eccpt` branch, pull request #495.
First written 2026-11-26 at 0632Z, the stamp in its name, and revised the
same day at 0654Z after a third verification round, at 0712Z after the
fourth, at 0733Z after a verification-only pass and at 1930Z after a bounded
fix round, each with its own section below. Supersedes nothing.
It follows no earlier doc on this topic. The nearest relative is
`SYS_OPS_hypergrok-trading-desk_v1_2026-09-24-0206.md`, the other trading
desk on record, whose line 16 reads "Standing approval for a protective stop:
no".

## What arrived

Tee attached one file, "Claude Overnight Desk 3.0", with the
`/workflow-authoring` command and no other words. The file is a published
prompt of 96 lines, SHA-256
`56761759790db188df6c293bf7f0bae3d364a5772958d452ae8426c67a0a4a62`. It asks
an AI agent to build a private desk of five bots that trades newly graduated
pump.fun coins on a FOMO account by clicking Buy and Sell in Chrome, with a
paper mode first and live trading after three paper nights. It is a third
party's text and is not copied into this repository.

The session read the attachment as a request to audit the prompt before
acting on it.

## The audit

A workflow ran five lenses over the prompt (platform, market, risk, runtime,
estate), each a finder followed by a separate verifier that was given the
claim and the evidence and never the finder's reasoning. The verifiers
confirmed 41 findings, left 3 unverified and refuted 2. These held on every
pass:

- FOMO's terms prohibit the desk as written. https://fomo.family/terms,
  headed "Last updated: October 26, 2026", section 16, lists as prohibited:
  "Use automated scripts, bots, software, or any other automated means to
  create accounts, send messages, post content, execute trades, or otherwise
  control or interact with account activity on the Services, except through
  functionality we expressly authorize". The same section forbids giving a
  session token to a script and adds: "These restrictions apply even when
  credentials are valid and were issued to a genuine user." Section 4 lets the
  operator disable sessions and suspend the account without notice.
- The prompt gates live trading on "all STEP 15 tests" at line 80 and defines
  steps 1 to 3 only. Steps 4 to 15 do not exist in the file.
- Every stop in the prompt is one process watching a price and clicking a
  button. A FOMO help page says a severe token warning puts a risk checkbox
  in front of Sell, and the prompt's own cursor rules forbid clicking any
  checkbox. So the stop cannot be promised in the case it exists for.
- The prompt states no fee anywhere.
- The link at line 22 has the form of a referral link. It was not opened and
  is not passed on.
- The blocking proof at line 37, getProgramAccounts, returned HTTP 403 "Your
  IP or provider is blocked from this endpoint" on three calls from this
  session's container to the two public Solana endpoint names. That says the
  public endpoints cannot be used from here and nothing about a keyed one.

The long written report of that audit went through the gauntlet three times
and failed each time, with mean scores of 3.18, 3.64 and 3.27 against a floor
of 4.0 and a security score of 4 against a required 5. The critics found that
it withheld the option to build, over-called some blockers and stated two
inferences as fact. It was quarantined and exists only in the session's
scratch space. The findings above are the ones no critic disputed.

## The ruling, and the objection logged once

The recommendation was to leave the prompt unbuilt as written. The decision
went to Tee on a card at 04:54Z. At 05:10Z he picked "Build toward the full
desk". That option's own text said the session token lane would not be built,
and that the click lane would come back to him on a card of its own.

The objection, stated once and not repeated: the venue's terms prohibit the
click lane and the token lane as written, the prompt's stop cannot be
promised, and Tee's capital-guardrails skill, line 117, says no automation may
carry out an irreversible capital decision without an explicit human
confirmation step. Whether a memecoin buy counts as irreversible under that
line is his reading to give. From here the work is done at full quality.

## What was built

`tools/overnight_desk/`, sixteen Python files and 3,070 lines, standard
library only. It is everything in the prompt that can be built and tested
without an account, a browser or an order: settings with an origin and a
range for every number, the market mode, the scanner, the eight layer analyst
and its score, the brain, the entry rule for the DIP and GRAD strategies, the
risk exits, the lessons loop, a paper executor with an explicit cost model, a
ledger, a live gate that stays shut, the desk that runs them in order, a
morning report and a replay over a recorded timeline.

Seven test files at the repository root hold 1,013 tests: base 86, brain
and entry 141, engine 193, mode and lessons 231, paper and gate 120, risk
102, scanner and analyst 140. All seven are in the standalone job of `ci.yml`
and in the matching list in `CLAUDE.md`.

What it is not. The desk has no source of data. Nothing produces a snapshot,
and the only timeline in the repository is synthetic. No real night has been
recorded or replayed, so nothing it prints is about a real market. It cannot
trade: the one executor fills on paper. It reads nothing from FOMO.

Six numbers the prompt never states have no default: the largest ticket, the
most open positions, the most total exposure, and three fee rates. The desk
checks its settings when it is built and refuses to start until Tee sets
them.

## What had to be invented

Every one of these is labelled INVENTED in `SPEC.md`. They are what the code
runs on today, in any replay. Tee has not ruled on any of them. The first
writing of this doc said none was in force until he ruled, and that was
wrong: only the step 15 acceptance list is a proposal that gates nothing.

- Steps 4 to 15, proposed in `STEPS.md`, with a nine line acceptance list
  for the step 15 the prompt gates live trading on.
- The score formula. The prompt names five parts and defines none.
- The cost model: a constant-product pool with a venue fee, a pool fee and a
  flat fee. A sale into a pool with nothing left pays nothing.
- The rule that turns a loss into a lesson. Its reach is wide: a loss on a
  coin with $40,000 of liquidity blocks every later coin at or under $40,000.
- Ten readings where the prompt contradicts itself or leaves a gap (R1 to
  R10 in `SPEC.md`), and twenty definitions the build had to choose, among
  them that "liquidity" means both sides of the pool and that a scanner kill
  lasts the whole night.
- The per-order approval gate on any executor that is not the paper one. The
  prompt asks for no such thing. It comes from Tee's own capital-guardrails
  rule, and it cannot hold together with the prompt's unattended stop.
- Fourteen settings marked invented, each with the reason in its note.

## How it was verified

Editors worked in their own worktrees, one module group each. Verifiers were
separate agents that re-ran the checks and mutated the source to see whether
the tests noticed. The main session read only what survived.

Round 1. Five editors built the modules from the contract and five verifiers
attacked them. The verifiers tried 265 mutations: 25 survived and no defect in
behaviour was found. A fix round killed all 25 and four more it was given,
29 of 29. A verifier on the engine, report and replay found four defects, two
of medium weight (a wrongly typed value in a timeline crashed the replay, and
an infinite starting cash printed passing checks), and all four were fixed.

Round 2, on commit `dd91720`. Four agents.

- Engine re-attack: every round 1 defect fixed and every listed mutant dead.
  Of 72 new mutations 55 were killed and 17 survived, four of them equivalent.
- Fuzz: 300 seeded nights, 11,870 ticks, 512 buys, 451 sells. Thirteen money
  and safety invariants held with no violation. The fourteenth, that no
  exception escapes a well formed tick, failed in 5 seeds.
- Code critic: 17 findings, one high and nine medium. Scores of 2 for
  correctness and 2 for failure handling, 4 for security, flagship floor
  missed.
- Fidelity critic: 19 findings, nine medium. Scores of 3 on all three of its
  dimensions.

The high finding and the fuzz failures were one defect. A risk exit on a coin
whose liquidity read zero or unknown raised an error inside the tick, so a
drained pool, the case the exits exist for, stopped the night and its report
instead of being recorded as a loss. A ticket smaller than the flat fee did
the same. The contract said the paper executor could not fail, and that was
false.

What round 2 changed:

- An order that is not filled is recorded and the tick carries on. A refused
  buy is a skip. An exit that cannot be carried out is an alert and a rule
  violation, the position is left as it was, and the next tick tries again.
- A sale into a drained pool is a total loss on paper. A missing price no
  longer hides a drained pool, a creator sale or a venue warning.
- A snapshot older than the coin's last one is refused before anything
  changes. A coin unseen for too long starts its watch again. A reading older
  than a set age is never bought on.
- The morning checks read pass, FAIL or n/a. A paper night no longer prints
  "pass" for order verification it never exercised, and an empty night prints
  four n/a lines.
- Coin symbols are escaped in the report and refused in a timeline when they
  are not printable, so a symbol cannot forge a report line.
- Two settings that no module read were removed. The GREEN trail default went
  from 20 to 25 so that the prompt's line 77, RED tightens trails, does
  something.
- An approval must name a person and carry a time. The documents now say it
  is a record and proves nothing about who built it.
- Labels were corrected where a choice of this build had been filed as the
  prompt's, and the "not built" list gained seven items.

Four editors made the module changes and four verifiers checked them. Two
verdicts were confirmed outright. Two were refuted on test strength alone,
with every contract item holding, and the main session closed those gaps: the
scan for a live executor had six holes and now has a test for each.

Round 3, on commit `43cddaa`. Four agents.

- Engine re-attack: all seven round 2 defects fixed and all 23 listed mutants
  dead. Of 45 new mutations, 7 survived with an effect that could be
  observed. One new defect: a price of infinity handed straight to the desk
  produced a paper take worth thousands of dollars. The replay already
  refused such a number, so only a direct caller could reach it.
- Fuzz: 1,500 seeded nights, 59,732 ticks, 2,313 buys, 2,373 sells, and 1,762
  ticks in which a held coin read liquidity zero or unknown. Sixteen of
  seventeen invariants held on every tick. The seventeenth, that no exception
  escapes a tick, held on that run and failed 33 times in a second run that
  pushed prices near 1e-300, where the quote overflowed to an infinite
  quantity at a price of zero.
- Code critic: 13 findings, two medium and none high. Scores of 3 for
  correctness, failure handling and observability, 4 for security,
  reversibility, completeness and maintainability, 5 for re-run safety.
  Flagship floor met.
- Fidelity critic: 11 findings, four medium. Scores of 4, 3 and 3.5.

Across the eleven scored dimensions the mean was 3.68, against a gate of 4.0,
and security was 4 against a required 5. Round 2's mean was 3.18 with the
floor missed.

What round 3 changed:

- A reading that holds a number that is not finite is refused before anything
  changes. The paper model refuses a quote that is not a usable number, so a
  price too small to work with is a skip or an exit not carried out, and
  never a crash.
- The desk checks its settings when it is built. Before, only the loaders
  did, and "refuses to start" was true of them and not of the desk.
- A fill that does not match its order is raised before the ledger is
  touched.
- An open position past the loss limit fails the loss check before it is
  closed, and the report prints its result so far.
- The text report prints the first detail under each kind of skip. The
  evidence lines for the first and fourth checks now say what they count: the
  first guards the record and cannot fail on the desk's own output, and the
  fourth counts two kinds of violation and no others.
- A refusal for a new cause and a watch that starts again are recorded.
- The replay escapes and cuts what it echoes, and refuses a line nested too
  deeply to read.
- Labels. The per-order approval gate had been filed under source line 80 and
  is this build's own. The scanner's kill order, the brain's skip order and
  minimum ticket, and the lesson grammar are now marked invented. Three
  readings were added. A false sentence, that WAVE and TREND give no
  thresholds, was corrected.
- Written down for the first time: the prompt sizes a ticket so a stop at
  exactly 25% loses exactly 3% of cash before costs, so with any fee a
  stop-out at full size loses a little more than 3% and the desk reports a
  violation.
- Each of the seven surviving mutations got a test.

Local runs after those fixes: the 990 desk tests passed, the CI standalone
list returned 7,062 passed, `ruff check .` returned no finding, and the
replay of the fixture night exited 0. The full
PostgreSQL suite ran on `43cddaa`, before those fixes, and returned 11,039
passed and 2 skipped.

The last pass, on commit `08b1502`. Three agents. This was the third scored
cycle, and the gauntlet allows three.

- Engine re-attack with extreme inputs: all six round 3 defects fixed, 19 of
  21 listed mutants dead, and 63 new mutations tried, of which one survived
  the whole suite with an effect that could be shown. A fuzz of 400 seeded
  nights and 12,121 ticks at the edges of every range found no failure, and a
  second of 11,904 ticks found none.
- Code critic: 10 findings, two medium and none high. Scores of 4 on seven
  dimensions and 5 on re-run safety. Flagship floor met.
- Fidelity critic: 14 findings, two medium. Scores of 4 for scope, 3 for
  traceability, 4 for verification coverage.

Across the eleven dimensions the mean was 4.00, at the gate of 4.0. No
dimension was under 3. Security was 4 against a required 5, so the verdict is
PASS-WITH-CONDITIONS and not PASS.

The security finding: the desk trusted an executor's own claim to be the
paper one. An executor that only called itself paper skipped the approval
gate, and the report would have said no money moved. No such executor exists,
so nothing could reach it today.

Changed after the last pass, in commit `d679a45`. No scored pass has seen
these. A verification-only pass did, and its results follow the two lists
below:

- Paper is now a fact about the executor's class. Only the desk's own
  `PaperExecutor` skips the approval gate. Anything else is gated, its night
  is not reported as a paper night, and a fill it labels paper counts as
  unverified. Five tests pin it.
- The report says when no reading carried the venue checks, and that open
  positions are valued before the cost of selling them.
- False statements corrected: "an unknown never passes a safety check" was
  not true of four scanner and venue inputs, and the contract now lists the
  exceptions. The live gate's docstring said nothing in it was invented. The
  engine's claim that one position's trouble never stops the next is now
  limited to the paper executor and to refusals.
- Five more definitions were labelled, among them that a scanner kill lasts
  the whole night and what "cash" means in the 3% rule.

Left open from the last pass, all rated low:

- An executor that fails after sending an order stops the tick part way. What
  a live desk should do then is undecided and belongs with reading R2.
- The lesson is derived from the last fill and its closeness measure favours
  liquidity.
- On a refused exit the refreshed peak is dropped for that tick.
- A market reading may carry its own time, which nothing checks.
- "Fees paid" adds a sell's pool fee, which is already inside the price.
- `apply_review`, `LessonBook.from_json` and `Settings.describe` are called by
  nothing in the package.
- The tests add `tools/` to the import path for the whole test run.
- A handful of tests are weaker than their names, and two listed mutants
  survive at an exact boundary.

A verification-only pass on `d679a45`, 07:20Z to 07:30Z. Three verifiers in
their own checkouts. Nothing was revised after it, because the three scored
cycles the gauntlet allows were spent, so the verdict above stands and was
not rescored. This session then reproduced every finding below with its own
scripts: the two gate findings by a probe, the ten surviving mutants one at a
time against all seven test files, and a control mutant that the tests
killed.

- Gate attack, 60 probes. Five hostile executors were handed to the desk in
  the ordinary way: a subclass of the paper executor, a subclass that
  overrides `execute`, an unrelated class that calls itself paper, an object
  whose `__class__` lies, and a class whose metaclass lies. None received an
  order without a valid approval, for a buy or for a sell. Each night was
  reported as "not the paper executor, though it calls itself paper" and each
  fill as unverified. Ten malformed approvals opened nothing.
- Mutation of the changed lines and of the gate: 91 mutants, 81 killed, 10
  survived. All 12 mutants of `require_approval` were killed, and so was
  every mutant of the class check but one that needs a lying metaclass.
- Truth of the changed statements: no false statement found. The counts
  matched a recount: 999 tests in seven files, 16 Python files and 3,038
  lines, 49 settings of which 14 are invented and 6 are the owner's, and
  7,071 passed on the CI standalone list.

Left open from that pass:

- Low, in the gate. Whether an executor is the paper one is decided once,
  when the desk is built. Code that assigns `desk.executor` afterwards hands
  orders to the new executor with no approval, and the report still reads as
  a paper night with no real order sent (`engine.py:128` and `engine.py:393`).
  No executor passed to the constructor gets through. Nothing in the package
  assigns that attribute. The repair is to fix the executor at build time and
  pin it with a test.
- Low. An approval callback that raises stops the tick part way. No order is
  sent (`engine.py:390`).
- Medium, in the tests only. No test reads the verification counts or the
  executor label of a night on a live executor that returns verified fills,
  so a mutant of each line survives (`engine.py:500`, `engine.py:523`). The
  code gives the right answer today: verified 1, executor "live".
- Low, in the tests only. Eight more survivors: the class check written with
  `==` (`engine.py:128`), the label for a kind outside the enum
  (`engine.py:526`), four at the edges of the sell fill bound
  (`engine.py:403`), and two in the report's venue line (`report.py:149`,
  `report.py:151`).
- Low, in the documents. The README's list of what the base guard test fails
  on is a subset of what the test bans. "Liquidity usually wins" in `SPEC.md`
  states a frequency that no real night here supports.

Local runs on `d679a45`: the 999 desk tests passed, the CI standalone
list returned 7,071 passed, `ruff check .` returned no finding, and
the replay of the fixture night exited 0. The full PostgreSQL suite last ran
on `43cddaa`, two fix commits earlier, and returned 11,039 passed and 2
skipped. CI runs it on the final commit.

A bounded fix round, 19:13Z to 19:24Z. Tee ruled it on a card answered by
19:11Z: one round past the cap of three, with no rescoring. Three editors
worked in sequence, each on one fix in its own checkout, and three verifiers
then checked the result. The three commits sit directly on the branch head
and were fast-forwarded onto it unchanged, so the commits on the branch are
the ones the verifiers checked.

- `968a3a4`, the gate. `desk.executor` is a read-only property. The paper
  decision is no longer stored: it is read from the held executor each time.
  `_execute` reads the executor once and uses that one object for the paper
  decision, the approval callback, the gate and the call. The probe that had
  printed two unapproved calls and executor "paper" now stops at the
  assignment with `AttributeError`.
- `1a3b65d`, tests only. Eight of the ten surviving mutants are now killed.
  The other two differ from the real code only outside the contract: an
  executor kind that is not a member of `ExecutorKind`, and a sell order with
  no quantity, which the desk never builds. One more test pins what happens
  today when the approval callback raises.
- `e05c1c8`, documents. The README's guard bullet lists everything the base
  test bans. The "usually" sentence in `SPEC.md` is replaced by the mechanism
  and by what the one synthetic night shows. The gate sections of both
  documents describe the code as it now is, and name what the gate does not
  stop.

What the verifiers found on `e05c1c8`:

- Gate attack, 42 probes. Assigning `desk.executor`, `desk._is_paper` or
  `desk._gate_kind` raises. An executor put into the desk's private
  attribute is still gated. No executor passed to the constructor received
  an order without a valid approval, for a buy or for a sell.
- Mutation. The eight mutants inside the contract are killed. Of 56 fresh
  mutants of the changed lines, 49 were killed and 7 survived.
- Truth. No false statement in the changed text. The round changed four
  files: the engine, its test file, the README and the SPEC. No test was
  removed or loosened. The replay of the fixture night prints byte for byte
  what it printed before the round.

Left open after the round. These were found by its verifiers and not fixed,
because the round Tee ruled was one round:

- Medium, in the tests only. One surviving mutant can be told from the real
  code. In `_execute`, the gate kind is read once at the top and passed to
  `require_approval` (`engine.py:424`). If that line read the kind afresh, an
  approval callback that reassigns the executor object's class to the paper
  class and returns no approval would get its order through. The real code
  refuses that order. No test pins it.
- Low, in the gate. The gate tests the executor's class and nothing else. An
  exact `PaperExecutor` object whose `execute` has been replaced on the
  instance is treated as paper, receives orders with no approval, and its
  night reads as a paper night. The README names replaced functions in the
  paper module as outside the gate. It does not name this case.
- Low. Rebinding `paper.PaperExecutor` in the module changes what counts as
  paper. Replacing `Desk._is_paper` on the class makes the report say paper
  while the gate still refuses the order.
- Low, in the tests only. Three survivors differ only for a subclass of
  `Desk` that overrides the `executor` property. Three more are equivalent.
- Still open from the earlier pass: what the desk should do when the
  approval callback raises. Today the error leaves the tick and nothing is
  sent, and a test now pins that.

Local runs on `e05c1c8`: the 1,013 desk tests passed, the CI standalone
list, regenerated from `ci.yml` at 65 files, returned 7,085 passed, and
`ruff check .` returned no finding.

## The data question for step 14

A second workflow surveyed keyless public sources for the readings the desk
needs. Its verifiers confirmed 28 findings and corrected 2. What bears on the
next ruling:

- No keyless source surveyed returns a count of bundled wallets or says
  whether the creator has sold. Layers 3 and 7 would read unknown, so on free
  public data the desk would pass no coin.
- For one pump.fun graduate, three keyless sources disagreed on the top 10
  holder share (29.05% RugCheck, 13.65% Jupiter, 29.72% GeckoTerminal), on the
  developer address and on the holder count (9,450, 3,728 and 3,951).
- No keyless source returns graduations per hour, and none offers a feed of
  new PumpSwap pools only.
- The Fear and Greed index read 11 on 2026-11-26, which is RED under the
  prompt's own rule.
- Terms differ by source. DexScreener's allow commercial use and forbid
  competing products. GeckoTerminal calls its public API unsuited to
  scheduled polling. Jupiter's licence forbids combining its data with data
  obtained outside its API. Birdeye needs a key and its terms bar storing
  data by automated means. Helius's free plan bars personal use. pump.fun's
  terms forbid bots on its platform.
- DexScreener's liquidity figure is both sides of the pool, the reading this
  build chose. pump.fun's fee page sets a PumpSwap pool's fee at 1.25% at the
  low end of market cap.

## One incident on the pull request

The Vercel web preview read failed on commit `dd91720`: `next build` threw
"TypeError: T is not a function" while prerendering `/_not-found`. The pull
request changes no web file, and the next commit, which changed one Markdown
file, built from the same cache and completed. The cause was not found. One
comment on the pull request records it.

## Open, in the order it blocks

Tee ruled four things on one card on 2026-11-26, answered by 19:11Z: one
bounded fix round, recorded above; pull request #495 held as a draft;
nothing more built until he has reviewed the invented parts; and this
record's receipt filed to the thread log. That ruling sets the order.

1. Tee's review of the invented parts: `SPEC.md` readings R1 to R10, the
   definitions list, the score formula, the cost model, the lesson rule and
   `STEPS.md`. Two questions inside that review came out of round 3: whether
   to size a ticket net of costs, and whether open positions should be
   managed on the tighter RED figures when market data is missing. Nothing
   more is built until this is done.
2. The data source for step 14. Without it the desk has nothing to read.
3. His six numbers.
4. Before any lane that touches FOMO: the reach of his compliance rule, his
   reading of capital-guardrails line 117, a written answer from FOMO on
   automation, and the question that per-order approval and an unattended
   stop cannot both hold.

Blocking nothing: the items left open after the bounded fix round, listed
in its section above. A further round on them is Tee's to rule.

## DEVON RECEIPT

```text
AREA: Money
TYPE: SYS_OPS
ARTIFACT: Overnight Desk paper engine, tools/overnight_desk, pull request #495
DATE: 2026-11-26
DECISIONS: build toward the full desk, picked on a card over a recommendation to leave the prompt unbuilt (Tee, 2026-11-26); the session token lane is not built under any ruling short of written authorization from the venue, and the click lane returns on its own card, both carried in the text of the option he picked; build the paper engine first, with no venue access; on a second card the same day, one bounded fix round past the cap of three revision cycles, pull request #495 held as a draft, building paused until he has reviewed the invented parts, and this receipt filed to the thread log (Tee, 2026-11-26); every definition the prompt lacks is labelled INVENTED and waits on his review; the six risk and fee numbers the prompt never states have no default
FINDINGS: FOMO terms section 16, last updated October 26 2026, prohibit automated trade execution and giving a session token to a script; the prompt gates live trading on STEP 15 tests it never defines; its stop is a price watch and a click and cannot be promised; it states no fee; the audit's long report failed the gauntlet three times and was quarantined; round 2 verification found that a risk exit on a drained pool stopped the night, fixed by recording an unfilled order and carrying on; round 3 found no high finding and the flagship floor met, with a mean score of 3.68 against a gate of 4.0 and security 4 against 5; the last pass scored a mean of 4.00 with security still 4, so the verdict is PASS-WITH-CONDITIONS; its security finding, that an executor could call itself paper and skip the approval gate, was closed afterwards in d679a45; a verification-only pass on d679a45 ran 60 gate probes and no executor passed to the constructor got an order without a valid approval; the same pass found one low way around the gate, by assigning the desk's executor after it is built, and 10 surviving mutants out of 91, two of them medium gaps in the tests with the code right today; all of it was reproduced by this session and left open because the three revision cycles were spent; the bounded fix round then made the desk's executor read only and the paper decision uncached in 968a3a4, added tests that kill eight of the ten surviving mutants in 1a3b65d and corrected three statements in the documents in e05c1c8; its verifiers ran 42 gate probes with no order reaching an executor passed to the constructor without a valid approval, and found one medium gap in the tests and three low ways around the gate that need a write to the executor object, the paper module or the Desk class; 1013 desk tests and 7085 on the CI standalone list pass locally on e05c1c8; the full API suite returned 11039 passed on 43cddaa; no keyless public source gives bundled wallet counts or creator sales, so on free data the desk would pass no coin; three keyless sources disagreed on one coin's top 10 share, developer address and holder count
OPEN: data source ruling for step 14; Tee's review of readings R1 to R10, the definitions list, the score formula, the cost model, the lesson rule and STEPS.md; his six numbers; before any FOMO lane, the reach of his compliance rule, his reading of capital-guardrails line 117 and the conflict between per-order approval and an unattended stop; whether to size net of costs; how to manage open positions when market data is missing; what a live desk does when an executor fails after sending an order; what the desk does when the approval callback raises; a test for the gate kind read once in _execute; whether the gate should also test that a paper executor's execute has not been replaced
STATUS: built and tested on the branch, four verification rounds, one verification-only pass and one bounded fix round run; gauntlet verdict PASS-WITH-CONDITIONS on the third scored cycle, not rescored after the fixes that followed it; pull request #495 held as a draft and building paused for Tee's review, both on his ruling; the invented rules are active in any replay and unruled; paper only, no data source, no venue access; not merged
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
