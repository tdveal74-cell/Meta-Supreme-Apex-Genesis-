# Overnight Desk: the paper engine, built on Tee's ruling

Status record for the `claude/new-session-1eccpt` branch, pull request #495.
First written 2026-11-26 at 0632Z, the stamp in its name. Supersedes nothing.
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

`tools/overnight_desk/`, sixteen Python files and 2,910 lines, standard
library only. It is everything in the prompt that can be built and tested
without an account, a browser or an order: settings with an origin and a
range for every number, the market mode, the scanner, the eight layer analyst
and its score, the brain, the entry rule for the DIP and GRAD strategies, the
risk exits, the lessons loop, a paper executor with an explicit cost model, a
ledger, a live gate that stays shut, the desk that runs them in order, a
morning report and a replay over a recorded timeline.

Seven test files at the repository root hold 956 tests: base 85, brain and
entry 141, engine 140, mode and lessons 231, paper and gate 117, risk 102,
scanner and analyst 140. All seven are in the standalone job of `ci.yml`
and in the matching list in `CLAUDE.md`.

What it is not. The desk has no source of data. Nothing produces a snapshot,
and the only timeline in the repository is synthetic. No real night has been
recorded or replayed, so nothing it prints is about a real market. It cannot
trade: the one executor fills on paper. It reads nothing from FOMO.

Six numbers the prompt never states have no default and block startup until
Tee sets them: the largest ticket, the most open positions, the most total
exposure, and three fee rates.

## What had to be invented

Every one of these is labelled INVENTED in `SPEC.md` and waits on Tee's
review. None is in force until he rules.

- Steps 4 to 15, proposed in `STEPS.md`, with a nine line acceptance list
  for the step 15 the prompt gates live trading on.
- The score formula. The prompt names five parts and defines none.
- The cost model: a constant-product pool with a venue fee, a pool fee and a
  flat fee. A sale into a pool with nothing left pays nothing.
- The rule that turns a loss into a lesson. Its reach is wide: a loss on a
  coin with $40,000 of liquidity blocks every later coin at or under $40,000.
- Seven readings where the prompt contradicts itself or leaves a gap (R1 to
  R7 in `SPEC.md`), and fourteen definitions the build had to choose, among
  them that "liquidity" means both sides of the pool.
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

Round 3 had not run when this was first written. Its result is recorded in
the pull request description and in a revision of this doc.

Local runs on the fix commit: the 956 desk tests passed, `ruff check .`
returned no finding, and the replay of the fixture night exited 0.

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

1. The data source for step 14. Without it the desk has nothing to read.
2. Tee's review of the invented parts: `SPEC.md` readings R1 to R7, the
   definitions list, the score formula, the cost model, the lesson rule and
   `STEPS.md`.
3. His six numbers.
4. Before any lane that touches FOMO: the reach of his compliance rule, his
   reading of capital-guardrails line 117, a written answer from FOMO on
   automation, and the question that per-order approval and an unattended
   stop cannot both hold.

## DEVON RECEIPT

```text
AREA: Money
TYPE: SYS_OPS
ARTIFACT: Overnight Desk paper engine, tools/overnight_desk, pull request #495
DATE: 2026-11-26
DECISIONS: build toward the full desk, picked on a card over a recommendation to leave the prompt unbuilt (Tee, 2026-11-26); the session token lane is not built under any ruling short of written authorization from the venue, and the click lane returns on its own card, both carried in the text of the option he picked; build the paper engine first, with no venue access; every definition the prompt lacks is labelled INVENTED and waits on his review; the six risk and fee numbers the prompt never states have no default
FINDINGS: FOMO terms section 16, last updated October 26 2026, prohibit automated trade execution and giving a session token to a script; the prompt gates live trading on STEP 15 tests it never defines; its stop is a price watch and a click and cannot be promised; it states no fee; the audit's long report failed the gauntlet three times and was quarantined; round 2 verification found that a risk exit on a drained pool stopped the night, fixed by recording an unfilled order and carrying on; 956 desk tests pass locally on the fix commit; no keyless public source gives bundled wallet counts or creator sales, so on free data the desk would pass no coin; three keyless sources disagreed on one coin's top 10 share, developer address and holder count
OPEN: data source ruling for step 14; Tee's review of readings R1 to R7, the definitions list, the score formula, the cost model, the lesson rule and STEPS.md; his six numbers; before any FOMO lane, the reach of his compliance rule, his reading of capital-guardrails line 117 and the conflict between per-order approval and an unattended stop; round 3 verification result to be recorded
STATUS: built and tested on the branch, two verification rounds run and their findings fixed, a third pending at first writing; paper only, no data source, no venue access; not merged
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
