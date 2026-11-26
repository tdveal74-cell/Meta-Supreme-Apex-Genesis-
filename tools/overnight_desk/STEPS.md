# Steps 1 to 15: what the source gives and what is proposed

The source prompt defines STEP 1, STEP 2 and STEP 3. It then makes LIVE depend
on "all STEP 15 tests" (source line 80) and never says what STEP 4 to STEP 15
are. Everything below from STEP 4 on is INVENTED for this build and waits on
Tee's review. The steps marked built are in the code today. The acceptance
list for step 15 is a proposal and gates nothing until he rules on it.

## The three steps the source defines

| step | source lines | status |
|---|---|---|
| 1. Venue account | 21-22 | Not built. Tee's own action. The link at line 22 has the form of a referral link and is not passed on by this build. |
| 2. Browser and cursor rules | 24-32 | Not built. See "Why steps 2 and 3 are not built". |
| 3. Read-only venue interface and layer 8 | 34-37 | Not built. See the same section. |

## Why steps 2 and 3 are not built

These are findings of the audit run in this session on 2026-11-26, before any
code was written. The package makes no network call and measured none of it.
The status record,
`docs/devon/SYS_OPS_overnight-desk-paper-engine_v1_2026-11-26-0632.md`,
carries the quotes.

- The venue's terms. https://fomo.family/terms, headed "Last updated: October
  26, 2026", section 16, lists as prohibited: "Use automated scripts, bots,
  software, or any other automated means to create accounts, send messages,
  post content, execute trades, or otherwise control or interact with account
  activity on the Services, except through functionality we expressly
  authorize". The same section forbids handing a session token to a script
  and adds: "These restrictions apply even when credentials are valid and
  were issued to a genuine user." Two agents read the page; the second read it
  without the first one's reasoning. Terms change, so read them again before
  relying on this.
- The click lane (step 2) is automated trading under that section as written.
  It comes back to Tee on a card of its own before any code is written.
- The session token lane (step 3, line 35) is not built by this agent under
  any ruling, unless the venue authorizes the access in writing.
- The blocking proof (line 37). The audit made the call the line names,
  getProgramAccounts on the Token program, from this session's container:
  three calls across two agents, to the two public Solana endpoint names. Each
  returned HTTP 403 with the message "Your IP or provider is blocked from this
  endpoint". That shows the public endpoints cannot be used from here. It says
  nothing about a private endpoint with a key, which the source does not
  name. The proof has not been met, and no paper night is claimed (SPEC.md,
  reading R5).

## Proposed steps 4 to 15

| step | what | proof | status |
|---|---|---|---|
| 4 | Settings with an origin and a range for every number; owner-only limits with no default | `test_overnight_desk_base.py` | built |
| 5 | Market mode | `test_overnight_desk_mode_lessons.py` | built |
| 6 | Scanner | `test_overnight_desk_scanner_analyst.py` | built as a rule engine over readings it is given; it fetches nothing |
| 7 | Analyst: eight layers and the score | `test_overnight_desk_scanner_analyst.py` | built; the score formula is invented |
| 8 | Brain: sizing and the owner's limits | `test_overnight_desk_brain_entry.py` | built |
| 9 | Entry rule and pre-trade recheck | `test_overnight_desk_brain_entry.py` | built for DIP and GRAD only; inside the desk the recheck has one reading to work with, so it cannot see price drift |
| 10 | Risk: stop, take, trail and the other exits | `test_overnight_desk_risk.py` | built; "sold the news" is not |
| 11 | Lessons loop | `test_overnight_desk_mode_lessons.py` | built; the rule that derives a lesson is invented |
| 12 | Paper executor, cost model, ledger, live gate | `test_overnight_desk_paper_gate.py` | built; the cost model is invented |
| 13 | Desk, morning report, replay | `test_overnight_desk_engine.py` | built |
| 14 | A read-only adapter for public market data, and recorded paper nights | recorded timelines replayed through STEP 13 | not built; needs a ruling on data sources. Until it exists the desk has no data and nothing it prints is about a real market |
| 15 | The acceptance tests that gate LIVE | see below | proposed |

## Proposed STEP 15

LIVE stays closed until every line below is true. This list is a proposal.

1. Every desk test passes in CI on the commit to be run.
2. A seeded fuzz run of the desk holds its money and safety invariants.
3. The owner's six limits are set in a settings file he wrote.
4. At least `paper_nights_required` full paper nights are recorded from real
   public data, and each one's morning report is read by the owner.
5. On those nights the four morning checks are reported honestly, and any
   FAIL has an owner's note beside it.
6. The owner has ruled on each reading in SPEC.md marked R1 to R10, on the
   list "Definitions this build chose" and on each INVENTED rule.
7. A live executor exists, and each lane it uses was ruled on separately.
8. Per-order human approval is demonstrated end to end on that executor.
9. The owner types LIVE.

Lines 7 and 8 cannot be true in this build. No live executor exists.

Line 8 carries a question that has to be ruled on first. With per-order
approval, a stop cannot fire while nobody is there to approve the sell. The
desk then reports the stop as not carried out. An unattended stop and a
per-order human approval cannot both hold.
