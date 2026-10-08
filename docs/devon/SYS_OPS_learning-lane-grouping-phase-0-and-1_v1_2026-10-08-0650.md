# Learning lane grouping: Phase 0 and Phase 1 built, criticised and fixed

This closes the first two phases of
`docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md`. Tee ruled on
cards on 2026-10-08: build Phase 0 and Phase 1; prove Phase 1 on a stub copy
first, then post three refusal cases to the live gate with the real header.
Nothing can PROMOTE until Phase 3, and nothing in this arc wrote to
devon-subconscious, devon-soul or tee-soul-layer.

## What is live

The Learning Gate `VzJsSlDswkIJ9wok` runs version `dc307024`, read back
through the n8n API: `active` true, `versionId` equal to `activeVersionId`,
and all seven Code nodes of the active version byte for byte equal to
`n8n/devon/learning-gate/`. It got there in two publishes on the same day.

- `e4da9aed`, Phase 1. Proven first on a throwaway copy, `UdvRmK15HpSkyunO`,
  executions 2412 to 2423 with Pinecone stubbed, then archived. Published,
  read back, and probed through the real door with the real header by a
  prober that used the credential by id, `XXH2IPdKo3OgCImm`, execution 2424,
  4 of 4 cases passing, then archived.
- `dc307024`, the critic's fixes below. The draft ran twice in manual mode,
  executions 2430 and 2431: a body nested past the scan bound answered
  REJECT_MALFORMED as data in 11 ms on the false branch, and the feeder's own
  POST shape over the real 2026-09-16 job answered HOLD_SUBCONSCIOUS. The
  diff against `e4da9aed` touched Candidate Former, Learning Gate and Build
  Record only, with no connection changed.

What the gate does now: a preflight decides before any conflict search is
spent. Every refusal is data, an HTTP 200 with `gate.decision` set and
`gate.search_spent: false`. A single job answers HOLD_SUBCONSCIOUS without a
search, because one job is one source and the bar is two. Every lesson
answers REJECT_UNREGISTERED until Phase 3 opens the lesson path. A failed
subconscious write now throws instead of answering 200 PROMOTE.

Since the second publish, as of this writing: the gate shows only those two
manual executions, the OS Error Handler `GbeNilHQzjmoWDz3` shows none, and the
Ledger Feeder `GEbNoDMBdGqDfZJ2` last ran at 06:00:53Z, before the publish.
The first production POST to `dc307024` will come from the feeder's next
daily run.

## What is in the repo

Phase 0, repo only: the rule block `n8n/devon/learning/lesson_evidence.js`,
which the feeder and the gate will both paste in Phase 3; the lesson registry
`services/devon/lesson_registry.py`, empty on purpose because Tee has
declared no lesson; and the recall filter in `deploy/soul/main.py`, which
withholds a record whose status is not active, as conflict-search already
did. Phase 1: the gate's seven Code nodes and `gate.test.mjs`.

## The critic

Three critics mutated the real source in their own worktrees, one each on the
rule block, the gate and the registry, and a skeptic re-ran every finding.
All 32 findings were confirmed real. None was a blocker. Four were armed
against something live or about to be:

1. **The live gate could still be made to throw.** A 6 MB run after a key
   prefix overflowed the regex engine's stack, and 100 KB of `eyJ-` held the
   preflight for seven seconds, both reproduced here. A throw is a 500 and an
   error email for what should be a refusal, against the node's own claim.
   The scan is now bounded before any pattern runs, at 8 levels, 2000 strings
   and 16384 characters, and a body it cannot read whole is refused. The
   feeder's largest possible body is about 2,500 characters. The token shape
   now opens on a lookbehind, so it is linear. Worst case under the bound
   measured under 2 ms.
2. **Recall called a withheld window a measured empty.** A window of
   superseded records answered "That is a measured empty, not a guess",
   though an active record could rank below them unfetched. The reply now
   says how many were withheld and that it is not a measured empty. The
   response keys are unchanged.
3. **The draft claim check did not refuse the failure it claimed to refuse.**
   "120 [dash] 30%" stitched into "120-30%" passed, because each number was
   found on its own, and 20 passed because 2026 contains it. Numbers are now
   read whole and found with digit boundaries, and every quotation form is
   checked. The recorded case is now a test with its own source sentence in
   the evidence.
4. **No declared lesson could ever have formed.** The registry writes
   `evidence_ids` as a JSON string and the rule block read only arrays, so E4
   would have refused every declared member. Every id list is now read
   whatever shape it arrives in.

The rest, all fixed: I3 fails closed when a parent chain leaves the rows in
hand, since at the gate it stopped after one hop; E6 excludes its own group
by normalised id and refuses an unread group log or commit list; invisible
characters, number versus string and empty keys can no longer split one act;
the gate counts verified members only when each is a distinct ULID; the
registry's field checks use full matches and real dates and compile ASCII
like the gate; the parity pin between the two shape lists fails instead of
skipping and counts every entry. A lint error in the Phase 0 commit, B905,
would have turned CI red on push and is fixed.

Every mutation the critics found surviving was re-run against the new tests
and is caught: the gate critic's 21, the 49 covering every survivor the rule
critic listed, and the registry critic's 24. Seven more were written against
the new gate code and six are caught by the gate test; the seventh, the token
shape put back to a word boundary, passes it because the size bound already
makes that harmless, and the registry's parity pin catches it. Tests went from 21 to 31 checks for the gate, 32 to 42 for the
rule block and 52 to 87 for the registry.

## Where this departs from the spec

- The generic secret rule, any hex or base64 run of 32 characters, was
  measured and left out. It refused Drive ids and commit hashes, ordinary in
  job summaries. Nine more shapes than the spec named were added instead,
  plus the reference gate's rule on fields named like a credential.
- Three shapes refuse some ordinary prose: "x-devon-key: accepted", "bearer
  authentication" followed by a long word, and a receipt TOKEN line. They are
  kept. On the job path a false REJECT_SECRET changes a feed log label and
  nothing else, and a lesson carries no free text.
- Moved to Phase 3 with the tables they need: the registry seed script, the
  `--check` step in `registry-check.yml`, and the `vault.py` entries.
- REJECT_CONFLICT and REQUIRES_HUMAN no longer appear on the job path,
  because a job never searches. REJECT_WEAK_EVIDENCE is now data where it
  was a throw.
- The Test Route node existed only on the stub copy. The live T8 probe went
  through a prober workflow using the credential by id, not over HTTP from
  this session.
- A pre-search HOLD_SUBCONSCIOUS holds its members, because the decision
  string cannot tell it from a post-search HOLD. The spec now says so.
- The spec overstates the reference gate in two places, that it scans for
  secrets before anything else and that it requires distinct real ULIDs.
  Left as written; this doc is the correction.

## Who else reads the decision

The spec asks this doc to name them. Read in the repo on 2026-10-08:
`ledger-feeder/log_or_alert.js` logs any 200 as fed and terminal;
`heartbeat/compose_pulse.js` counts decisions and flags only an empty one;
`ledger-feeder/select_unmarked_jobs.js` and `mark_receipts.js` mirror the
decision onto the
Build 18 envelope; the Soul Committer filters `eq PROMOTE`. None branches on
any other value, so the new decisions cannot change their behaviour. The
feeder's email footer still says the gate rules "PROMOTE or REQUIRES_HUMAN";
it is incomplete rather than false and was left alone.

## Open

- Platform-side recall readers do not apply the status filter:
  `app/api/v1/soul.py`, `knowledge_loop.py` and `agent_runtime/runtime.py`.
- A withheld record still spends a recall slot. The reply discloses it; it
  does not over-fetch.
- `_is_active` drops a status of `""` or `"ACTIVE "`. In conflict-search that
  means a ruling with an empty status cannot block a lesson. Whether no tee
  ruling carries one is unverified, because Pinecone was out of bounds.
- I3 now refuses any member with a parent, because at the gate no ancestor
  row is in hand. No writer sets a parent today. Phase 3 may fetch
  ancestors instead.
- Two Zapier jobs that touched one external object can still count twice
  under I4.
- The Build 02 guard allows forged verification text, spec decision 11.
- 52 active workflows were counted where CLAUDE.md says 45. The Heartbeat's
  sticky note names an old SMTP id. Two workflows hold unpublished drafts,
  `MmFNWeewHEuG5x8T` and `wXl6p7hKN74lKH0e`.
- Whether `devon-soul` deploys on merge, which decides when the recall fix
  is live, is unverified.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_learning-lane-grouping-phase-0-and-1_v1_2026-10-08-0650.md
DATE: 2026-10-08
DECISIONS: Tee ruled on cards: build Phase 0 and Phase 1; prove Phase 1 on a stub copy, then post three refusal cases to the live gate with the real header; merge PR #317; merge PR #318.
FINDINGS: Phase 1 live as e4da9aed, then dc307024 after the critic, read back byte for byte. 32 critic findings, all confirmed, none a blocker; four armed: the live preflight could throw on hostile input, recall called a withheld window a measured empty, the draft claim check passed the recorded 120-30% rewrite, and the rule block would have refused every declared lesson member. All fixed and re-measured; every surviving mutation is now caught.
OPEN: Platform recall readers unfiltered; withheld records spend recall slots; _is_active edge cases; I3 refuses any member with a parent until Phase 3 fetches ancestors; Zapier I4 limit; Build 02 guard forgery; 52 active workflows against 45; Heartbeat sticky; two unpublished drafts; devon-soul deploy on merge unverified.
STATUS: Gate VzJsSlDswkIJ9wok active dc307024; no lesson declared, so no group can form and nothing can PROMOTE until Phase 3. Repo work on claude/devon-build12-conflict-policy-tuiypu, not yet merged at the time of writing.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
