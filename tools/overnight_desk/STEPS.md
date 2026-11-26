# Steps 1 to 15: what the source gives and what is proposed

The source prompt defines STEP 1, STEP 2 and STEP 3. It then makes LIVE depend
on "all STEP 15 tests" (source line 80) and never says what STEP 4 to STEP 15
are. Everything below from STEP 4 on is INVENTED for this build and waits on
Tee's review. Nothing here is in force until he rules on it.

## The three steps the source defines

| step | source lines | status |
|---|---|---|
| 1. Venue account | 21-22 | Not built. Tee's own action, on his own card. The link at line 22 has the form of a referral link and is not passed on by this build. |
| 2. Browser and cursor rules | 24-32 | Not built. The venue's terms prohibit automated trading. Returns on its own card. |
| 3. Read-only venue interface and layer 8 | 34-37 | Not built. The session-token lane is not built by this agent under any ruling. The blocking proof at line 37 failed from this environment on the public endpoint. |

## Proposed steps 4 to 15

| step | what | proof | status |
|---|---|---|---|
| 4 | Settings with an origin and a range for every number; owner-only limits with no default | `test_overnight_desk_base.py` | built |
| 5 | Market mode | `test_overnight_desk_mode_lessons.py` | built |
| 6 | Scanner | `test_overnight_desk_scanner_analyst.py` | built |
| 7 | Analyst: eight layers and the score | `test_overnight_desk_scanner_analyst.py` | built; the score formula is invented |
| 8 | Brain: sizing and the owner's limits | `test_overnight_desk_brain_entry.py` | built |
| 9 | Entry rule and pre-trade recheck | `test_overnight_desk_brain_entry.py` | built for DIP and GRAD only |
| 10 | Risk: stop, take, trail and the other exits | `test_overnight_desk_risk.py` | built; "sold the news" is not |
| 11 | Lessons loop | `test_overnight_desk_mode_lessons.py` | built; the rule that derives a lesson is invented |
| 12 | Paper executor, cost model, ledger, live gate | `test_overnight_desk_paper_gate.py` | built; the cost model is invented |
| 13 | Desk, morning report, replay | `test_overnight_desk_engine.py` | built |
| 14 | A read-only adapter for public market data, and recorded paper nights | recorded timelines replayed through STEP 13 | not built; needs a ruling on data sources |
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
6. The owner has ruled on each reading in SPEC.md marked R1 to R4 and on each
   INVENTED definition.
7. A live executor exists, and each lane it uses was ruled on separately.
8. Per-order human approval is demonstrated end to end on that executor.
9. The owner types LIVE.

Lines 7 and 8 cannot be true in this build. No live executor exists.
