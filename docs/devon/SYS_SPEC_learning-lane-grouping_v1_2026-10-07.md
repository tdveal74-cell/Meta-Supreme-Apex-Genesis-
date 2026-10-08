---
title: Build 12 Learning Lane, Grouping Completed Jobs into Declared Lessons
type: SYS_SPEC
version: 1
date: 2026-10-07
area: Systems
status: proposed, not built
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base_commit: 67694be
owner: DEVON
decides: Tee
---

# Build 12 Learning Lane: Grouping Completed Jobs into Declared Lessons, v1

## This is a spec, and nothing in it has been built

No workflow, data table, repo file, Pinecone index or service was changed to
produce this document. Everything below is a proposal for Tee to approve or
reject, phase by phase. Every phase ships as its own draft PR and merges only on
his explicit authorization.

The facts in it come from reads made on 2026-10-07: the repo at `67694be`, the
live n8n workflows and data tables, and the Build 12 reference files on Drive.
Nothing was executed, published or POSTed for it, and `approval_queue` was not
read.

Re-read by the session that filed it, at 22:00Z on 2026-10-07, before
committing: the ledger `QZvdxllOjWevb3Vo` in full (9 rows, last written
2026-09-16T06:00:58.772Z), the feed log `U0PqQWiq4nadKFlm` in full (12 rows),
the gate `VzJsSlDswkIJ9wok` at `17f51ee2` and the Soul Committer
`drP96ernQvbrvzIZ` at `5e149077` (both with `activeVersionId` equal to
`versionId` and `sameAsDraft` true), every repo line reference below, and the
ULID regex in node against the two smoke ids and the real id. Each matched what
is written here. The other reads were the panel's and were not repeated.

Labels used throughout:

| Label | Meaning |
|---|---|
| [V] | verified by a direct read on 2026-10-07 |
| [I] | inferred from reads, not observed |
| [U] | not checked |
| [E] | an estimate |

## Summary

Today a completed job can never become a lesson. The Ledger Feeder posts each job to the Learning Gate alone, with one source id. The gate needs two independent sources to PROMOTE, and a HOLD writes nothing. So all ten real feeds ever made ended at HOLD or REQUIRES_HUMAN, and no job at all has been filed in the 21 days since 2026-09-16. This spec changes three things. First, a lesson exists only when Tee declares it, as a registry entry holding his claim text, an Area, a scope and a minimum of two sources. Second, the feeder groups completed, human-verified jobs declared for that lesson, registers the group durably under a learning intent id, and posts it once. Third, the gate stops trusting the caller: before it spends a conflict search, it checks every posted id against the live ledger and the group against the feeder's registration, and it refuses anything undeclared. No model groups jobs or writes a claim. A PROMOTE still writes only devon-subconscious, and only Tee's tap on one Soul Committer card per lesson writes devon-soul. At today's volume (one eligible completed job, none filed in 21 days) it will produce zero promotions and will report that as a count. Phase 1 on its own closes two live holes whatever happens to the rest: two made-up ids can no longer reach PROMOTE, and a failed subconscious write can no longer answer 200 PROMOTE.

## The problem as measured

### The four measurements that decide it

1. **The feeder sends one id per post.**
   - `n8n/devon/ledger-feeder/select_unfed_jobs.js` line 28 reads
     `source_intent_ids: [j.intent_id]`, and the feeder sends one HTTP POST per
     job [V].
   - Lines 18 to 22 build the claim as "Completed job experience: <summary>.
     Area: X. Executor: Y. Outcome: Z." [V]. That records an event. It does not
     state a lesson.
2. **The gate needs two.** The live Learning Gate on `VzJsSlDswkIJ9wok`, version
   `17f51ee2`, answers HOLD_SUBCONSCIOUS when there are fewer than 2 source ids
   [V].
3. **HOLD writes nothing.** HOLD and REQUIRES_HUMAN both route to Skip Write,
   which is a no-op [V]. A held candidate survives only as its row in the feed
   log `U0PqQWiq4nadKFlm`.
4. **Nothing is arriving.** The VPS ledger `QZvdxllOjWevb3Vo` holds 9 rows [V]:
   - 8 CANCELLED test jobs created 2026-08-24;
   - 1 COMPLETED job, `01M2KT8WM4RPZ90BCTZPVXH6HK`, the VPS cutover proof of
     2026-09-16.

   The table was last written at 2026-09-16T06:00:58Z [V], so no job has been
   filed in the 21 days to 2026-10-07. The 2026-10-07 brief records that the
   Face chat has never been used on the VPS. This session did not re-read that.

What that produced in the feed log (all 12 rows read [V]):

| Decision | Rows | Note |
|---|---|---|
| HOLD_SUBCONSCIOUS | 3 to 8, 12 | one id each, so the count can never reach two |
| REQUIRES_HUMAN | 1, 9 to 11 | stopped at the conflict search, before the count was checked |
| PROMOTE | 2 | an injected smoke on 2026-08-25, `webhook_status 0`, reverted |

None of the 12 claims states a lesson [V]. Rows 3 to 11 have no row in the VPS
ledger. Their feed rows were copied at the 2026-09-16 cutover, but their ledger
rows were not [V].

The 2026-08-26 handoff said "the feeder, gate, and committer need no further
changes" (`docs/devon/SYS_OPS_devon-improvements-handoff_v1_2026-08-26.md`) [V].
The measurement above shows that was wrong. With one id per feed, no feed can
ever reach two.

### Holes found along the way

Each of these is live in the current versions [V unless marked]. None has done
harm yet, because no genuine PROMOTE has ever run [I].

- **"Independent" means only "distinct strings".** Candidate Former accepts any
  id string of 10 or more characters after trimming and upper-casing, and never
  looks the id up in the ledger. A holder of the shared `x-devon-key` can post
  two made-up ids. If the claim clears the conflict search, the gate promotes it.
- **The evidence is fabricated.** Candidate Former builds `evidence` as
  `{intent_id, state: "COMPLETED"}` and `observed_outcomes` as the literal
  strings "independent observation N".
- **A failed subconscious write still answers 200 PROMOTE.**
  - Pinecone Upsert runs with `neverError`, and Write Result reports `ok:false`
    without throwing.
  - The feeder reads only the decision (`log_or_alert.js` line 17), so it would
    log PROMOTE.
  - The committer would then raise a card for a record that was never written.
- **The subconscious write has no idempotency.** Its `_id` is a fresh random
  `candidate_id` on every call.
- **The committed soul record loses its sources.**
  - Its only provenance is one string, `source_note: "Build 12 learning gate
    PROMOTE; source intent <id>; approval <request id>"`. It has no
    `source_intent_ids` and no `status`.
  - The 2026-08-24 ruling expects Soul to be searchable by source id. This
    record shape does not allow that.
- **Recall ignores status.** `GET /api/v1/soul/recall` (`deploy/soul/main.py`
  line 518) never calls `_is_active` (line 202). The conflict search does call
  it, at line 655. The 2026-08-24 ruling makes this filter a precondition of the
  first promotion.
- **REQUIRES_HUMAN goes nowhere.** The spec says "a requires_human result routes
  to Tee". In the live estate it routes to Skip Write, and the committer reads
  only PROMOTE rows.

### What the binding documents meant

All five are on Drive in `_Devon Core` [V].

- **The 2026-08-23 Build 12 spec.**
  - "One occurrence may be stored in subconscious but does not become Soul by
    default."
  - The minimum for automatic promotion is two independent observations,
    "unless Tee explicitly approves promotion".
- **The 2026-08-24 Candidate Former spec.**
  - "Claim must be a single reusable operational lesson, not a description of
    one job."
  - "Never invent evidence."
- **The Python reference gate.**
  - It never defined independence more strongly than distinct real ULIDs, taken
    from the ledger rows passed in.
  - It rejected secrets before anything else.
- **The binding ruling of 2026-08-24.**
  - "A promotion never writes to its source jobs."
  - `parent_intent_id` stays empty for a learning intent.
  - `source_intent_ids` are carried on the Soul record.
  - Recall filters on `status: active` before the first promotion.
- **The 2026-08-26 assessment** (as quoted in the brief): "PROMOTE will NOT be
  manufactured. A synthetic pair of same-theme jobs would ... defeat the word
  genuine."

## Why this design

Three designs were written. Two independent judges scored each one out of 25,
on posture, honesty at low volume, buildability, failure safety and provider
resilience.

| Design | Judge 1 | Judge 2 | Why it lost, or won |
|---|---|---|---|
| A, declared lessons | 22 | 22 | Tee writes the claim, membership is declared, no model is used anywhere, and an undeclared candidate cannot PROMOTE. |
| B, semantic clustering | 12 | 14 | Nothing ties the claim to the ids at the gate, so a key holder can attach any claim to real jobs. It also depends on Cerebras and on a Pinecone `/embed` call this estate has never made. |
| C, reflection-cited lessons | 15 | 17.5 | Its fingerprint includes the model-written brief, so one act can count twice. It admits auto-verified jobs, and the session that writes the claims can also write the table the gate trusts. |

This spec takes A as the spine. It grafts in the ideas both judges named from B
and C:

- the registration check before any search;
- a STUCK exit after repeated failures;
- refusals returned as data, not thrown;
- sentinel id slots;
- an execution-identity rule;
- an act fingerprint built from structural fields only;
- refusing the whole group when any member is bad;
- a claim validator for session drafts;
- each member's own ledger wording printed on the card.

## The design

### Flow

1. **DECLARE (Tee).**
   - A session may draft a registry entry in a draft PR to the new module
     `services/devon/lesson_registry.py`. An entry holds:
     - `lesson_key`, a slug;
     - `claim`, 40 to 600 characters: one reusable operational rule, never a
       description of a job;
     - `area`, one of the 9 Areas in `n8n/devon/intake-former/form_job.js` line 7
       [V];
     - `scope`, one of project, system or global, as in the reference gate;
     - `min_sources`, from 2 to 5;
     - `status: active`;
     - `evidence_ids`, an optional list of ULIDs;
     - `declared_on` and `ruling_ref`.
   - Before the PR goes to Tee, `scripts/lesson_registry_seed.py --preview`
     prints two things into it:
     - the result of the claim validator (see "Who writes the lesson claim");
     - a read-only conflict-search receipt for the claim. A claim that would stop
       at REQUIRES_HUMAN is then found before any job is spent on it.
   - Tee authorizes the merge on an inline card.
   - `--seed` runs only on his ruling. It inserts the entry and reads it back,
     following the existing `scripts/show_registry_seed.py` pattern [V, the file
     exists].
2. **ATTACH (Tee).**
   - Retro: Tee lists the ids of work already done in the entry's
     `evidence_ids`, in the same kind of PR. This is the only route by which
     today's one eligible job could ever count.
   - Forward: a job filed with `intent.payload.lesson_key`. This is deferred to
     an optional Phase 4, and whether to build it is a decision for Tee.
3. **GROUP (feeder, daily, no model).**
   - A new branch of the Ledger Feeder `GEbNoDMBdGqDfZJ2` reads:
     - the registry;
     - the COMPLETED ledger rows;
     - its new group log;
     - the feed log;
     - the commit log, read only.
   - It works through every active key that is neither adopted nor blocked:
     - The candidates are the jobs declared for that key.
     - It filters them by eligibility rules E1 to E6 below, recording a reason
       for every excluded id.
     - It picks members oldest `verified_at` first under independence rules I1
       to I7, up to 5.
   - If fewer than `min_sources` qualify, it writes nothing and adds "key k: n
     of m members" to the existing Stamp Run note.
   - Otherwise, BEFORE any POST, it upserts one FORMED row in the group log:
     - `group_key` is key + ":" + the sorted member ids;
     - `learning_intent_id` is a ULID, minted once from `crypto.getRandomValues`
       and stored.
   - If a `group_key` already exists in any state, the group is skipped.
   - This keeps the estate's invariant: the intent is committed durably before
     the adapter runs.
4. **FEED.**
   - The feeder POSTs
     `{kind: "lesson", lesson_key, learning_intent_id, source_intent_ids}` to
     `devon-build12-upstream`, with no claim and no count.
   - It sends one group per request, using credential Devon Capture Key with
     `neverError`, `fullResponse` and a 30 second timeout.
5. **PREFLIGHT AT THE GATE, with no spend.**
   - In order, the gate:
     - checks the shape;
     - scans for secrets;
     - matches the registration;
     - reads the registry;
     - reads the ledger rows;
     - runs the shared rule block.
   - Any refusal answers HTTP 200 with `gate.decision` set, `receipt: null`,
     and a verdict for each id. No conflict search is spent.
6. **SEARCH AND DECIDE.**
   - Only a group that is registered, has a declared key and has every member
     verified reaches the conflict-search issuer. The claim it sends is the
     registry's.
   - The issuer and Assemble Result are unchanged: a non-2xx answer or an
     incomplete receipt throws.
   - Then comes REJECT_CONFLICT, REQUIRES_HUMAN or PROMOTE, under the existing
     policy b12.1: below 0.35 is weak, below 0.60 is adjacent, and 0.60 or above
     is strong (`deploy/soul/main.py` lines 242 to 243) [V].
7. **PROMOTE WRITE.**
   - The gate upserts one devon-subconscious record whose `_id` is
     `learning_intent_id`, so a retry rewrites the same record.
   - A non-2xx upsert now throws instead of answering 200 PROMOTE.
8. **LOG (feeder).** The feeder reads the status code back.
   - **On a 2xx answer,** the group row becomes FED and stores the decision, the
     receipt id, the conflict status and the top match.
   - **On PROMOTE,** it also writes one feed log row keyed on
     `learning_intent_id`. The row carries the claim, the area, `lesson_key`,
     `source_intent_ids` and an `evidence_note`. That row is the committer's
     existing intake. If a group row says PROMOTE but has no feed log row, the
     next run repairs it without a second POST.
   - **On a non-2xx answer,** the row becomes FAILED, `attempts` goes up by one,
     and the next run retries under the same `learning_intent_id`. At 5
     attempts the row becomes STUCK, one email goes out, and it is never posted
     again.
   - **REQUIRES_HUMAN or REJECT_CONFLICT blocks the KEY, not just the group,**
     because the search depends only on the claim. The block lifts when Tee
     rules, or when he rewords the claim, which gives it a new `claim_sha`.
   - The activity email goes out only when something happened. It names the
     matched record and its score.
9. **CARD (Soul Committer `drP96ernQvbrvzIZ`).** There is one card per
   learning intent.
   - Its `what_happens` carries:
     - the full claim, byte for byte;
     - the lesson key;
     - for each member, its id, its verify card id, its verified date, and a
       verbatim excerpt of its own ledger `receipt.summary` and verification
       evidence;
     - the receipt id;
     - the top match and its score.
   - The evidence field starts `intent <learning_intent_id>;`, so the
     committer's existing adoption logic is unchanged.
10. **COMMIT (Tee).**
    - Approval writes ONE devon-soul record carrying `source_intent_ids`,
      `lesson_key`, `learning_intent_id`, `status: active` and `kind: lesson`.
    - A rejection, or the 72 hour expiry, closes the card forever [V, expiry].
11. **RECALL.** `GET /api/v1/soul/recall` gains the `_is_active` filter. It must
    be live before step 10 runs for the first time.

### The independence rule

The gate checks each rule against the live ledger row at the time it decides,
never against the caller's payload. The feeder runs the same rule code first,
so it never posts a group the gate will refuse. That code lives once, in
`n8n/devon/learning/lesson_evidence.js`, and a repo test pins the two live
copies byte for byte.

**Eligibility of each member**

- **E1.** After trimming and upper-casing, the id matches the reference regex
  `^[0-9A-HJKMNP-TV-Z]{26}$`.
  - This replaces today's "any string of 10 or more characters".
  - Run in node, the regex rejects both live smoke ids and the 08-25
    placeholder, and accepts the real id in either case [V].
- **E2.** A ledger row with that `intent_id` exists in `QZvdxllOjWevb3Vo`, and
  it has:
  - state COMPLETED;
  - terminal true;
  - `receipt_outcome` completed;
  - an envelope `intent_id` equal to the id.

  The one COMPLETED row has exactly these values [V]. The other
  `receipt_outcome` values are [U], so excluding them fails closed.
- **E3.** A human verified it:
  - `verification_state` is passed;
  - `verification_method` is `human_watch`;
  - `human_watched` is true;
  - the verification evidence holds "verify_card <REQ> approved by Tee".

  A job completed as `auto_no_artifact` never counts.
- **E4.** Its membership was declared:
  - either the envelope's `intent.payload.lesson_key` equals the key;
  - or the registry entry for the key lists the id in `evidence_ids`.

  Nothing else makes a job a member: not a keyword match, the same Area, the
  same executor, the same action, or a similar summary.
- **E5.** The key is active in the registry, and the job was not filed with
  `auto_verify`.
- **E6.** The id is not a member of any other group row, unless that row was
  refused at preflight.
  - A preflight refusal is REJECT_MALFORMED, REJECT_SECRET, REJECT_UNREGISTERED
    or REJECT_UNVERIFIED_SOURCE.
  - A group that reached the conflict search was a proposal, and a job backs at
    most one proposal, ever.
  - A group refused before the search never was a proposal, so its members stay
    free for a different key.
  - A HOLD_SUBCONSCIOUS answered before the search (steps 5 and 7) still holds
    its members. The gate answers HOLD_SUBCONSCIOUS after the search too, and
    the decision string alone cannot tell the two apart, so a HOLD holds.
    Freeing a pre-search HOLD would need the group log's receipt id, which is a
    ruling for Tee. Added 2026-10-08 after the Phase 1 critic.

**Independence between members.** A pair of members counts as two observations
only if all of these hold:

- **I1.** The two `intent_id` values are distinct after normalisation.
- **I2.** The two `idempotency_key` values are distinct. The same key means the
  same job, retried.
- **I3.** The two jobs have distinct lineage:
  - neither is the other's `parent_intent_id`;
  - they do not share a non-empty parent;
  - their walked parent chains do not meet.

  `parent_intent_id` is empty on every ledger row today [V].

  A chain is read only while its rows are in hand. A chain that reaches a
  parent whose row was not read, loops, or runs past twenty hops cannot prove
  two jobs unrelated, so the pair is refused. At the gate the rows in hand are
  the members' own, so today any member with a parent is refused; Phase 3 may
  fetch ancestors instead. Added 2026-10-08 after the Phase 1 critic found the
  walk stopped after one hop and passed a grandparent and a cousin.
- **I4.** They share no artifact `uri`, `record_id` or `drive_file_id`. Two
  jobs pointing at one doc or row are one observation. A Zapier artifact
  carries only the first URL its tool answered, which can be empty, so two
  Zapier jobs on one external object can still count twice; URLs are not
  normalised to close that, because some tools name the object in the query.
- **I5.** Their structural act fingerprints differ.
  - The fingerprint is a deterministic hash of the structural acts only: the
    action, the Airtable table and fields, the Zapier tool and arguments, and
    the EditForge block.
  - It leaves out every free-text field: summary, note, brief and `lesson_key`.
    So neither model output nor a reworded summary can split one act into two.
  - The cost, which fails closed: two jobs whose only structural field is the
    same action count once.
  - Which payload fields a `drive.draft` job carries was not read [U]. A real
    envelope of that kind goes into the T1 fixtures before this rule is fixed.
- **I6.** They were verified on different UTC dates. This is on by default, and
  it is Tee's call. It stops a filer from making a pair in one sitting.
- **I7.** They have a distinct (`workflow_id`, `execution_id`) pair. Both columns
  are in the ledger schema [V].

The feeder picks members oldest `verified_at` first. It skips any candidate that
fails a pair rule against a member it has already chosen.

The gate does not pick. If any posted member fails E1 to E6, or any posted pair
fails I1 to I7, the gate refuses the WHOLE group as REJECT_UNVERIFIED_SOURCE,
with a verdict for each id and each pair.

- A group is never trimmed down to its good members, so padding a group cannot
  help.
- The feeder runs the same code, so a gate refusal of a registered group means
  the two copies have drifted. The email says so.

The independent count is the size of the verified member set. The gate never
uses the length of the id list, or any count the caller sends.

**What never counts**

| Case | Rule that stops it |
|---|---|
| The same id twice in different letter case | refused as malformed at the gate; collapses to one under I1 at the feeder |
| A parent and child, or two siblings | I3 |
| A retry under one key | I2 |
| The same act filed twice under two keys, or with a different brief | I5 |
| Two jobs writing the same row or doc | I4 |
| Smoke ids `SMOKETEST0FEEDER0000000000` and `SMOKE-COMMITTER-V2-20260825` | E1 [V] |
| The 8 CANCELLED test jobs | E2 [V] |
| The 9 historical feed rows 3 to 11 | E2: they have no VPS ledger row [V] |
| An auto-verified job Tee never saw | E3 |
| Two made-up ULIDs | E2, and at the gate REJECT_UNREGISTERED first |
| A candidate with no declared key, however many ids it has | it never PROMOTEs |

### Who writes the lesson claim

Tee writes it, or adopts a session's draft wording verbatim. Nothing downstream
may change it.

**Where the claim lives and how it gets there**

- The claim lives in the registry entry: one fixed text per key, 40 to 600
  characters.
- The 600 cap keeps it far under the conflict search's 2000 character limit
  (`deploy/soul/main.py` line 574) [V]. So the "422 forever" case cannot arise.
- The claim enters only through a PR whose merge Tee authorizes. The data table
  is seeded only on his ruling.

**The check on a session's draft**

- A session may draft a claim from named `evidence_ids`. Before that draft goes
  to Tee, it must pass a deterministic validator.
- The validator requires every digit run, and every quoted fragment, to appear
  verbatim in the ledger text of the named jobs: `intent_summary`,
  `receipt.summary` or the verification evidence.
- This closes off, at the source, the fabricated-number failure CLAUDE.md
  records.
- Tee's own wording is not checked. It is his.

**No model writes, edits or summarises a claim**

- The feeder composes no claim. It posts the key and the ids.
- The gate refuses a lesson-shaped POST that carries a claim. It fetches the
  claim from the registry by key.
- The committer commits the feed log claim it was handed, which is the registry
  claim.

**Where Tee sees the exact text before anything reaches devon-soul**

1. On the card for the registry PR, beside the read-only conflict preview.
2. On the approval card and verify card of each forward-keyed member, if Phase 4
   is built.
3. On the Soul Committer card. The text shown there is the text committed.

Only approving the third card writes devon-soul.

**An optional extra, needing Tee's ruling.** The daily reflection may PROPOSE
candidate registry entries in its own text, and report the eligible-member
count, so that "dormant" is a number. It never posts to the gate and never
writes a table. The model suggests and Tee declares.

### The ledger check the gate gains

These are new nodes on gate `VzJsSlDswkIJ9wok`, placed between Candidate Former
and the Conflict-Search Issuer. Each one reads a data table in id mode, with
`executeOnce`, and with `alwaysOutputData` paired with a code guard that skips
the synthetic empty item.

| Node | Reads | Purpose |
|---|---|---|
| Fetch Group Log | the feeder's group log, filter `learning_intent_id eq` | registration match |
| Fetch Registry | `devon_lesson_registry`, filter `lesson_key eq` | the key's status, claim, area, scope, `min_sources` and `evidence_ids` |
| Fetch Source Rows | ledger `QZvdxllOjWevb3Vo`, `anyCondition` over five `intent_id eq` slots | the members' own rows |
| Evidence Verifier | the three reads above | runs E1 to E6 and I1 to I7, computes the verified count, sets `search_needed` |
| Preflight Passed (IF) | the verifier's output | true goes to the issuer; false goes to Refuse Before Search |
| Refuse Before Search | the verifier's output | emits the normal response shape, with `gate.decision` set and `receipt: null` |

Fetch Source Rows has two safeguards:

- An empty slot resolves to the sentinel `__none__`, so a mis-wired slot matches
  nothing rather than everything.
- It has 5 slots, which is why a group has at most 5 members.

The feeder parses `b.decision || b.gate_decision || b.gate.decision`
(`log_or_alert.js` line 17) [V], so every refusal must keep `gate.decision`.

- Refusals are returned as data, never thrown. Hostile input therefore cannot
  trip the OS Error Handler, and cannot spend a search.
- Throws stay reserved for infrastructure faults: a non-2xx answer from the
  issuer, an incomplete receipt, or a failed upsert.

**Decision order.** Steps 1 to 7 spend no search, and every one of them answers
HTTP 200.

1. **REJECT_MALFORMED.** The gate refuses any of these:
   - an unknown `kind`;
   - `kind: job` with anything other than exactly one ULID id;
   - `kind: lesson` carrying a `claim` field;
   - a `learning_intent_id` that is not a ULID;
   - fewer than 2 or more than 5 ids;
   - any id that is not a ULID;
   - a duplicate id after normalisation.

   `kind` defaults to `job` when absent, so the feeder needs no change in
   Phase 1.
2. **REJECT_SECRET.** This is a port of the reference's `likely_secret`. It
   fires when any string in the body matches one of these:
   - `pcsk_`, `sk-` or `sk-ant-`;
   - `Bearer `;
   - an `x-devon-key` value;
   - a private key block;
   - a base64 or hex run of 32 or more characters.
3. **The single-job path (`kind: job`).**
   - A missing claim, or one under 12 characters, gives REJECT_WEAK_EVIDENCE, as
     today.
   - Otherwise the answer is HOLD_SUBCONSCIOUS, with the reason "a single job
     never promotes" and the job's ledger verdict.
4. **REJECT_UNREGISTERED.** A lesson must match a group log row byte for byte:
   - the same `learning_intent_id`;
   - state FORMED or FAILED;
   - the same `lesson_key`;
   - the same sorted id list.

   This shuts out a key holder who posts a declared member set before the feeder
   does.
5. **HOLD_SUBCONSCIOUS for a key that is not usable.** This covers a key that is
   unknown or not active ("undeclared candidates never promote"), and a scope
   outside project, system and global.
6. **REJECT_UNVERIFIED_SOURCE.** Any member or pair fails. The whole group is
   refused, with a verdict for each id and each pair.
7. **HOLD_SUBCONSCIOUS for too few members.** The verified count is below
   `min_sources`. This cannot happen while the feeder and gate agree. It is
   kept as a guard.
8. **The issuer.** It is called with the registry claim. A non-2xx answer or an
   incomplete receipt throws, as today.
9. **The final decision.** REJECT_CONFLICT, then REQUIRES_HUMAN, then PROMOTE.

### Gate changes, complete list

The live version is `17f51ee2` [V]. The gate's code lives only in n8n today [V].
So Phase 0 first copies the live code nodes into `n8n/devon/learning-gate/`,
and every later edit is made in the repo first.

- **Candidate Former.**
  - Reads the two shapes, `kind: job` and `kind: lesson`.
  - Applies the ULID regex and the secret scan.
  - Drops any `evidence`, `observed_outcomes`, `independent_evidence_count` or
    receipt the caller supplies.
  - Stops fabricating evidence.
  - Carries a constant, `LESSON_PATH_ENABLED`. It is false in Phase 1, when every
    lesson POST answers REJECT_UNREGISTERED with the reason "lesson path not
    enabled". It is switched on in Phase 3, once the tables exist.
- **New nodes.** Fetch Group Log, Fetch Registry, Fetch Source Rows, Evidence
  Verifier, Preflight Passed and Refuse Before Search.
- **Conflict-Search Issuer.** The claim now comes from the registry. The body,
  the 25 second timeout, the credential and the throws are unchanged.
- **Learning Gate.**
  - Follows the decision order above.
  - Uses the verified count.
  - Allows PROMOTE only for `kind: lesson`.
- **Build Record.**
  - `_id` becomes `learning_intent_id`.
  - The record adds `status: active`, `kind: lesson`, `lesson_key`, `area`,
    `scope`, `conflict_check_receipt_id` and `learning_intent_id`.
  - `source_intent_ids` holds the verified members only.
- **Write Result.**
  - Throws on a non-2xx upsert, naming the `learning_intent_id` in a message
    whose reason text has no colon.
  - The webhook should then answer 500. That is reasoned, not observed [U].
- **Response.**
  - Adds a verdict for each id and each pair.
  - Adds a receipt summary: `receipt_id`, `conflict_status`, and the top
    match's id and score.
  - Gate executions are not saved (`saveDataSuccessExecution: none`) [V]. So
    this answer is the only record of a receipt, and the feeder stores it.
- **Unchanged.**
  - The webhook path and the `x-devon-key` header auth.
  - The issuer host and its credential.
  - No write path to tee-soul-layer.
  - `saveDataSuccessExecution: none`.
  - Error workflow `GbeNilHQzjmoWDz3`.

The effect on the single-job path: legacy single feeds now always HOLD without
spending a conflict search, so REQUIRES_HUMAN no longer appears on that path.

### Feeder changes

These are to `GEbNoDMBdGqDfZJ2`, live version `f94723cd` [V]. It runs Daily
02:00 America/New_York, which is 06:00Z now and will be 07:00Z after 2026-11-01
[V].

- **A new lesson branch** comes off Fetch Feed Log, placed above Stamp Run. Its
  nodes, in order:
  1. Fetch Lesson Registry
  2. Fetch Group Log
  3. Fetch Commit Log (read only)
  4. Form Lesson Groups (the shared rule block)
  5. Record Formed Groups
  6. Feed Lesson Group
  7. Log Group Outcome
  8. Update Group Log
  9. Record Lesson Feed Row
  10. Notify Lessons (activity only)
- **Stamp Run's note** gains the lesson counts, for example "lessons: 1 active
  key; key k 1 of 2 members; 0 groups formed".
- **Select Unfed Jobs, Log Or Alert and the Build 18 branch are unchanged.**
  - A lesson feed row is keyed on a `learning_intent_id` that matches no ledger
    job, so Build 18 skips it.
  - Build 18 only marks ledger rows it finds in Fetch Completed Jobs
    (`select_unmarked_jobs.js` lines 38 to 40) [V].
- **No second row goes into `devon_feeder_run_log`.** The Pulse takes
  `max(ran_at)` across every row without filtering by feeder (`compose_pulse.js`
  lines 145 to 149) [V]. A lesson stamp there could hide a dead main branch.

### Soul Committer changes

These are to `drP96ernQvbrvzIZ`, live version `5e149077` [V].

- **Select Next Proposal.**
  - Writes the lesson card text described in flow step 9.
  - Refuses, and closes, any group whose member already appears in a commit log
    row.
- **Insert Commit Rows.** Writes the new `lesson_key` and `source_intent_ids`
  columns.
- **Resolve Approved.** The record carries a `source_intent_ids` array,
  `lesson_key`, `learning_intent_id`, `status: active` and `kind: lesson`.
- **`SoulWriteCandidate.to_record`** in `services/intelligence/soul.py` is
  updated to match, in both byte-identical copies.

### Other changes

- **`deploy/soul/main.py`.** `soul_recall` applies `_is_active`, with tests.
  `test_deploy_soul.py` must still pin conflict-search as the only non-GET
  route.
- **Heartbeat Pulse `EEDrp2jLlw2Ssd5b`, required in Phase 3.**
  - `compose_pulse.js` splits its feed log decision counts by `lesson_key`.
    Today it counts every `gate_decision` (line 107) [V], so lesson rows would
    otherwise mix into the job counts.
  - Optional: a `lesson_stuck` finding, for a group that is STUCK or has sat
    FORMED or FAILED for more than 48 hours.
  - Optional: a line of lesson counts (eligible, blocked).
- **New repo files.**
  - `services/devon/lesson_registry.py`, with a byte-identical copy under
    `deploy/soul/services/devon/`, as the CLAUDE.md module rule requires.
  - `scripts/lesson_registry_seed.py`, with `--preview`, `--seed` and `--check`.
  - `n8n/devon/learning/lesson_evidence.js` and the `n8n/devon/learning-gate/`
    directory.
- **Edits to existing repo files.**
  - A `--check` step in `.github/workflows/registry-check.yml`. That file has one
    job [V], and adding a step adds no job, so the CI count stays at thirteen.
  - `services/devon/vault.py` entries for the two new tables.
- **Optional Phase 4: the forward key.**
  - Intake Former `TciVQhWJA0y92x9P` gains Fetch Registry. Form Job accepts
    `payload.lesson_key` and validates it.
  - Today an unknown payload key is dropped, because `form_job.js` rebuilds the
    payload from a whitelist from line 35 on [V].
  - In Job Driver `MfJCYeJqVjBLFrCu`, `decide.js` `cardBody` prints this line on
    the approval card and the verify card: "Filed as evidence for lesson <key>:
    <claim>. Approving this verification records that you watched this job's
    output; it does not approve the lesson."

### New tables and fields

**New data table `devon_lesson_registry`**

- In project `qbrcjkbIoorbwot6`, and addressed by id only.
- Columns: `lesson_key`, `claim`, `claim_sha`, `area`, `scope`, `min_sources`,
  `status`, `evidence_ids`, `declared_on`, `ruling_ref`.
- The repo module is its source of truth.
- It is seeded only on Tee's ruling and checked daily.

**New data table `devon_lesson_group_log`**

- The feeder's own idempotency table.
- Columns: `group_key` (unique), `lesson_key`, `claim_sha`, `learning_intent_id`,
  `source_intent_ids`, `state` (FORMED, FED, FAILED or STUCK), `gate_decision`,
  `webhook_status`, `attempts`, `receipt_id`, `conflict_status`, `top_match`,
  `formed_at`, `fed_at`, `note`.

**Before either table is created**

- `scripts/n8n_table_collision_check.py` [V, it exists] runs first.
- No table with "lesson" in its name exists today [V, from design C's table
  listing].

**New columns on existing tables**

- Feed log `U0PqQWiq4nadKFlm`:
  - `lesson_key`, `source_intent_ids` and `evidence_note`.
  - `evidence_note` is capped at 1000 characters, and any cut is marked.
  - Lesson rows also fill the existing `area` column, which is null on every
    real row today [V].
- Commit log `x8U4QqvXTVgINg3h`: `lesson_key` and `source_intent_ids`.

**New record fields**

- devon-subconscious record: `status`, `kind`, `lesson_key`, `area`, `scope`,
  `conflict_check_receipt_id` and `learning_intent_id`, with
  `_id = learning_intent_id`.
- devon-soul record: a `source_intent_ids` array, `lesson_key`,
  `learning_intent_id` and `status: active`.

**Phase 4 only: the envelope field `intent.payload.lesson_key`**

- It is never placed under `envelope.learning`.
- That is because Build 18 replaces that object wholesale
  (`select_unmarked_jobs.js` line 51) [V].

**No new ledger column**

- The members' declared key is read from the envelope JSON.
- So Build 02's 34-column upsert is untouched.

## At today's near-zero volume

**What it will produce.** Zero groups, zero PROMOTEs and zero cards on day one,
and very likely for weeks [I]. What the pool holds today:

- **The one eligible job.** The only COMPLETED VPS job is
  `01M2KT8WM4RPZ90BCTZPVXH6HK`.
  - Its approval was decided by tee, and its evidence reads "verify_card
    REQ-20260916-J1ApUy approved by Tee" [V]. So it passes E1 to E3.
  - It carries no key, so it counts only if Tee lists it in `evidence_ids`.
  - It is a cutover proof (`actor_source vps-cutover-verification`). Whether a
    proof may count at all is his call.
- **Jobs that can never count.**
  - The 8 CANCELLED jobs fail E2 [V].
  - The 9 historical real feed rows fail E2, because they have no VPS ledger row
    [V]. That includes the closest same-shape pairs: rows 5 and 8 (TQO
    outlines) and rows 10 and 11 (Inbox Captures rows).
- **The registry.** It stays empty until Tee merges a first entry.

**What the first possible PROMOTE needs.**

1. One registry entry merged and seeded.
2. Phases 1 to 3 live, with the recall filter deployed.
3. Two eligible members verified on different UTC dates. Either Tee lists the
   2026-09-16 job and files one new verified job, or he files two new ones.
4. A clear conflict search on the claim.

Every step is one Tee takes or approves. So the promotion rate equals the rate
at which he declares lessons and files verified work. The design adds nothing on
its own.

**What it does every day meanwhile.**

- It adds three id-mode table reads to the daily feeder run [E].
- It spends no conflict searches. That is a saving, because single feeds stop
  spending one each.
- It writes one line in the Stamp Run note, so a quiet day shows as a count, not
  silence.
- It sends no email unless a group was fed, a key was blocked, a group went
  STUCK or a write failed.

**What it will not do.** It will not:

- manufacture a pair;
- admit a Cloud-era orphan;
- treat an auto-verified job as evidence;
- let a model decide that two jobs taught the same thing.

## Failure modes

| Failure | What happens | How it fails closed |
|---|---|---|
| A key holder posts two made-up ids as a single job | REJECT_MALFORMED: `kind: job` carries exactly one id | Refused as data, before any search |
| A key holder posts a lesson-shaped group, made-up or real | REJECT_UNREGISTERED: no matching group log row | The gate only reads that table, and only the feeder writes it [I] |
| A registry row is hand-edited in the n8n editor | The gate trusts the table until `registry-check` goes red. That takes about 24h, plus the usual 20 to 90 minutes of scheduled lateness [E]. | It cannot reach devon-soul without Tee's tap, and the card shows the full claim. The tighter fix is an inline copy pinned by a repo test, at the cost of one publish per lesson. |
| A filer puts a real key on a job that did not show the lesson | The data rules pass it | Tee's card prints each member's own ledger wording, so he can reject. A rejection burns those members, which is correct but costly at this volume. |
| A forged member: a fake job walked to COMPLETED with a forged "verify_card ... approved by Tee" string | The verifier trusts the ledger row | Build 02's `Guard Transition` (`hDmTRI5VAZ3a8sTn`, version `4e469fa1`) checks only that each state move is legal, and `Flatten Envelope` checks only the ids, so a holder of `x-devon-key` can post a fabricated job through the legal states to COMPLETED carrying any verification text. Read in the code by the filing session, not executed. This is why decision 11 matters: the stronger check is reading `approval_queue`, which is Tee's call. |
| The conflict search answers `requires_human` | The key is blocked, and the email names the match and its score | Nothing is written. The preview at seed time exists to catch this before any job is spent. |
| The issuer is down or its receipt is incomplete (Vercel, Pinecone inference, `CONSOLE_TOKEN`) | Assemble Result throws, and the webhook should answer 500 [U] | The group goes FAILED, retries daily under the same id, and becomes STUCK at 5 attempts with one email. Nothing is logged as PROMOTE. |
| The subconscious upsert fails | Write Result throws | No 200 PROMOTE, no feed log row and no card. The retry rewrites the same `_id`. |
| The response is lost after a PROMOTE | The feeder marks the group FAILED and retries. The gate searches again and upserts the same `_id` again. | No duplicate record. If the second search disagrees, the first record stays in the subconscious as an orphan. It carries `learning_intent_id` and `status`, so it can be found and purged [I]. |
| The feed log write fails after a PROMOTE | No card yet | The next run writes the missing row from the group row, without a second POST |
| The group row write fails before the POST | Nothing is posted | A FORMED row is a precondition of the POST |
| The feeder and gate rule copies drift, through a hand edit to a live node | The gate refuses the group with REJECT_UNVERIFIED_SOURCE, and the email says the copies disagree | `group_key` dedupes, so the same member set is never re-posted. The repo byte-identity test cannot see drift in a live node, but the estate-reconcile skill can. |
| The Soul Committer card expires after 72h | It counts as a rejection [V] | The group closes and its members are burned. At this volume that can cost the only pair for weeks, which is a decision for Tee. |
| Monitors mislead | Lesson rows would inflate the Heartbeat's job counts | Phase 3 splits the counts by `lesson_key` and adds no second feeder run log row |
| Behaviour change on the single-job path | Single feeds always HOLD, and REQUIRES_HUMAN disappears from that path | Other readers of `gate_decision` among the 45 active workflows were not counted [U]. The Phase 1 status doc must list them. |
| The secret pattern fires on a harmless long hex run | REJECT_SECRET | A refusal, never a write. The registry module test runs the same patterns when a lesson is declared. |
| The clocks change on 2026-11-01 | The feeder runs at 07:00Z | Nothing depends on the hour. A check scheduled against 06:00Z would be an hour off. |
| The forward key is lost in transit (Phase 4) | A keyed job arrives without its key | Whether executors strip unknown payload keys is [U]. A dry run must prove the key survives before anyone relies on it. |
| The card text is too long | The approval queue's own length limits were not read [U] | `evidence_note` is capped at 1000 characters with the cut marked, and the full list stays in the group log |

## Provider exposure

**No model touches grouping or claims.** Membership is a declared key plus
ledger fields, and the claim is Tee's text. A refusing provider cannot form a
group, change a claim or fake a member.

**Direct dependencies.** All of these exist today:

- the devon-soul service on Vercel, for the conflict search;
- Pinecone-hosted `llama-text-embed-v2`, which embeds the claim for that search.
  Whether it is available on this account is [U];
- Pinecone upserts to devon-subconscious (on PROMOTE) and to devon-soul (on
  approval);
- n8n data tables;
- SMTP credential `AgSGuaA2pnZsrZcJ`, for activity and STUCK emails.

A failure in any of these makes the receipt incomplete or the upsert fail. The
gate then throws, the group retries under the same id, and it ends STUCK after
5 attempts.

On the SMTP credential specifically:

- CLAUDE.md records it, as counted on 2026-09-22, as the one credential behind
  every alerting node in the estate.
- An SMTP outage silences the emails, but not the group log.

**Cerebras touches the lane only through the supply of jobs.** The provider is
`gpt-oss-120b` on credential `ENoUSqySnkK0NVsl`, and it answered HTTP 402 for
much of September. It feeds the lane through four paths:

- **Free-text intake tagging.** During an outage, a keyed job must be filed
  through the structured POST, which carries its own Area [V, `form_job.js`].
- **The intake brief.** It is advisory and never blocks a job.
- **Filing through the Face chat.**
- **Executors that do their work with Cerebras,** such as `drive.draft`.

Fewer jobs complete during an outage. That starves the pool rather than
corrupting it: a missing brief cannot change I5, because I5 ignores free text.

**What the provider watchdog does and does not cover.**

- It reads provider refusals, not this lane. A quiet lesson count during an
  outage says nothing about the provider.
- Pausing content triggers to quiet an outage is still wrong, as CLAUDE.md says.

## Test plan

No test ever writes to devon-soul or devon-subconscious, and no test ever reads
`approval_queue`.

**T0. Base.**

- Every session starts with `git rev-parse --short HEAD`.
- It sets `PYTHONPATH` to absolute worktree paths.
- A critic runs in an isolated worktree checked out at the named SHA.
- The full suite never runs at the same time as the standalone job.

**T1. The rule block, with no network.**

`n8n/devon/learning/lesson_evidence.js` gets node fixture tests, one case per
rule:

- each smoke id fails E1;
- an id missing from the ledger;
- a CANCELLED id;
- `auto_no_artifact`;
- `human_watch` without the verify card string;
- the same `idempotency_key`;
- a parent and child, and two siblings;
- a shared artifact `uri`;
- the same structural act with a different brief and summary, which counts once;
- the same (`workflow_id`, `execution_id`) pair;
- the same UTC verify date, with I6 on and with it off;
- a member reused in a group that reached the search, and in a group refused at
  preflight;
- a retired key and an unknown key;
- mixed-case duplicates;
- two valid members, which count as 2;
- three members, one of them dependent.

Two more requirements for T1:

- A real `drive.draft` envelope goes into the fixtures before I5 is fixed.
- A test pins the feeder copy and the gate copy byte for byte, the same way
  `test_deploy_soul.py` line 74 already pins the vendored soul modules [V]. That
  test sees only the repo copies. Drift in a live node is found by the
  estate-reconcile skill.

**T2. The registry and the seed script.**

- Registry module tests cover:
  - claim length of 40 to 600;
  - the Area and scope enums;
  - `min_sources` from 2 to 5;
  - `evidence_ids` that are ULIDs;
  - keys that are slugs;
  - secret patterns;
  - the dash ban, which `test_devon_integrity.py` applies automatically.
- The claim validator refuses a fabricated number, and a quoted fragment that is
  absent from the evidence.
- The module is copied with `cp` to `deploy/soul/services/devon/`, and
  `test_deploy_soul.py` is re-run.
- The seed script gets diff and refusal tests modelled on
  `test_show_registry_seed.py`.
- The new test files are added to the standalone list in `ci.yml`.

**T3. The recall filter.**

- Fixture records carry status active, status superseded, and no status.
- Recall returns active records and records with no status, and never a
  superseded one. That matches `_is_active`.
- Conflict-search stays the only non-GET route.

**T4. The gate's guarded path, on a throwaway copy.**

- Setup:
  - Pinecone Upsert is replaced by an echo stub.
  - A grep of the exported JSON shows no `pinecone.io` host.
  - The fixture rows are pinned, modelled on the real 2026-09-16 row.
  - It runs through `test_workflow`, with no webhook call and no activation.
- Refusal cases. Every refusal from T1, end to end, plus:
  - `kind: job` with two ids gives REJECT_MALFORMED, with no issuer call;
  - a lesson with no registration gives REJECT_UNREGISTERED;
  - a declared set posted before the feeder gives REJECT_UNREGISTERED;
  - a secret gives REJECT_SECRET before any read.
- PRESENCE, not only absence.
  - A registered two-member group whose ledger read RETURNS rows reaches the
    REAL issuer, with a read-only POST.
  - It then PROMOTEs into the stub. The test asserts `_id` equals
    `learning_intent_id` and checks the record fields.
  - It runs once with 2 slots filled and 3 sentinel slots, and once with all 5
    slots filled.
- Failure cases:
  - an injected non-2xx from the stub makes Write Result throw;
  - every refusal body parses through `log_or_alert.js`'s decision expression.
- Afterwards, archive the copy and record the execution ids.
- Before it runs, Tee rules it consistent with the 2026-08-26 assessment. It
  uses fixture rows in a stubbed copy, and nothing reaches any store.

**T5. The feeder, on a throwaway copy.**

- Setup:
  - The gate URL is pinned to the T4 copy.
  - It writes to throwaway tables, created only after the collision check
    passes.
- It must prove:
  - the FORMED row is written before the POST and is visible to the gate's
    read, which stays [I] until this test shows it;
  - a 500 leaves the group FAILED, with the same `learning_intent_id`;
  - 5 failures give STUCK and exactly one email;
  - PROMOTE writes the feed log row;
  - a missing feed log row is repaired without a re-POST;
  - reused members are excluded;
  - a blocked key is not re-posted, and a new `claim_sha` unblocks it;
  - the Stamp Run note carries the counts;
  - the single-job path is unchanged;
  - no second run log row is written.

**T6. The committer, on a throwaway copy.**

- Setup:
  - Fetch Open Requests and Fetch Decisions are pinned to fixtures, so nothing
    reads `approval_queue`.
  - Raise Approval Request and Commit To devon-soul are replaced by echo stubs
    with no host.
- It asserts:
  - the card holds the claim byte for byte, every member's ledger excerpt, the
    receipt, and the `intent <id>;` prefix;
  - the ndjson record carries the `source_intent_ids` array and
    `status: active`;
  - a group with an already-committed member is closed with no card.

**T7. The Pulse.** `compose_pulse.test.mjs` gets cases for the `lesson_key`
split and for `lesson_stuck`.

**T8. Production adversarial.** This runs only after T4 passes, and only on
Tee's OK. It POSTs to the real gate with the real header:

- two made-up ULIDs, in both shapes;
- two CANCELLED ids;
- the 2026-09-16 id twice, in different letter case.

Each must answer 200 with a refusal and spend no issuer call. Record each body
verbatim, because the gate saves no successful executions.

**T9. Re-measure.**

- After every publish, read back that `activeVersionId` equals `versionId` and
  that `activeVersion.sameAsDraft` is true.
- Then wait for the first unattended feeder run. A manual run proves the path,
  not the schedule.
- Read that run's `devon_feeder_run_log` row, and confirm its lesson counts match
  a hand count from the ledger and the registry.

**T10. Phase 4 only.**

- Test `decide.js` `cardBody` with fixture envelopes, with a key and without.
- Read the intake workflow to confirm that `dry_run` writes no ledger row [U]
  before using it.
- Then trace one keyed job through to each executor's acceptance.

## Build size

This is a large build overall, but it splits into phases that each work on their
own. The order matters: nothing may be able to PROMOTE before everything
downstream of it is ready. All session counts are estimates.

**Phase 0: repo only.** About 1 session [E]. No live changes.

- the registry module and its copy;
- the seed script and the CI step;
- the rule block and its tests;
- the gate's code copied into the repo;
- the recall filter and its tests;
- the `vault.py` entries.

**Phase 1: gate preflight.** About 1 session, plus a critic [E]. One live
workflow changes.

- the two kind shapes, the ULID check and the secret scan;
- refusals returned as data;
- single feeds stop spending a search;
- the `_id` change and the Write Result throw;
- the lesson path switched off.

**Phase 2: committer and recall.** About 1 session [E]. One live workflow
changes, plus one Vercel deploy.

- the committer card and the record shape, with `to_record`;
- the recall filter deployed;
- load `deploy-readback` before calling the deploy live. Whether a merge deploys
  devon-soul automatically is [U].

**Phase 3: grouping.** About 1 to 2 sessions [E]. Two live workflows change,
plus one gate flag.

- two new tables and five new columns;
- the feeder's lesson branch;
- the Pulse split;
- the lesson path switched on.

**Phase 4, optional: the forward key.** About 1 session [E]. Two live workflows
change.

- the intake field;
- the driver card line.

**In total:**

- 4 live workflows edited, or 6 with Phase 4, and no new workflow;
- 2 new data tables, plus 5 new columns on 2 existing tables;
- 1 new `services/devon` module and its deployed copy;
- 1 script;
- 1 CI step and no new CI job;
- 1 soul service change.

After Phase 1 alone, no caller can PROMOTE until Phase 3 lands. That is the safe
direction.

## Decisions for Tee

Each item puts the recommended answer first.

1. **Approve this spec, and build Phase 1 now?**
   - Recommended: yes. It closes the made-up-ids hole and the false-PROMOTE hole,
     and single feeds stop spending searches.
   - Cost: REQUIRES_HUMAN disappears from single feeds, and the Heartbeat wording
     has to be updated to match.
2. **May a human-watched proof job back a lesson?** The 2026-09-16 cutover job is
   the only eligible COMPLETED job.
   - Recommended: only when you list it yourself.
   - Cost of saying no: nothing can promote until two new verified jobs
     complete.
3. **Allow retro declaration through `evidence_ids`?**
   - Recommended: yes. It is the only near-term path, and it relies on your
     memory of what a past job showed.
   - Should the retired Cloud ledger ever make the 9 orphan rows admissible?
     Recommended: no. Whether that ledger is still readable is [U].
4. **Should I6 require members verified on different UTC days?**
   - Recommended: on.
   - Cost: two real jobs from the same day wait a day.
5. **What happens to a lesson that comes back REQUIRES_HUMAN?**
   - Recommended: an email, and the key stays blocked until you rule or reword
     the claim.
   - Alternative: a card where your approval is the ruling. That changes what the
     committer's intake means.
6. **What happens after a rejected or expired Soul Committer card?**
   - Recommended: close the group, burn its members, and keep the key open for
     fresh members.
   - Cost: a 72 hour expiry while you are away burns the only pair.
7. **May a job back at most one lesson proposal, ever?**
   - Recommended: yes. The alternative lets one observation count toward several
     lessons.
8. **Keep the learning intent out of the ledger, with the Soul Committer card as
   its approval?**
   - Recommended: accept this for v1.
   - It departs from the 2026-08-24 ruling's expectation that a learning intent
     is an ordinary ledger job carded by the Job Driver.
   - Filing it in the ledger instead costs a second card per lesson.
9. **Build the reference's `tee_approved` single-source bypass?**
   - Recommended: no. The bar stays at two.
10. **Keep Build 18's LEARNING_CAPTURED stamp on fed jobs?** It rewrote
    `event_id` and `ledger_written_at` on the 2026-09-16 row [V].
    - Recommended: keep it. It marks feeding, not promotion, and the group path
      writes nothing to source jobs.
    - Cost: if you read the ruling as covering any write to a source job, this
      conflicts with it.
11. **What is the trust boundary for E3?**
    - Recommended: the ledger row.
    - Alternative: also read `approval_queue` to confirm each verify card. That
      adds a third reader of the token table.
12. **Build the forward key, Phase 4, now?**
    - Recommended: no. Build it when you first want to file a keyed job.
13. **May the daily reflection propose registry entries in its own text?** It
    would never post or write a table.
    - Recommended: yes, after Phase 3.
    - This is a prompt change to a Routine you own.
14. **May T4 run on a stubbed copy with fixture rows, and may T8 post refusals to
    the live gate?**
    - Recommended: yes. Neither can write to any store.

## Not verified for this spec

- **The Pinecone indexes.** Their current contents were not read. Earlier records
  say devon-subconscious was purged empty on 2026-08-26 and devon-soul holds no
  real record, but this session re-read neither.
- **The issuer receipts for the 12 feed rows.** Gate executions are not saved.
- **The gate's webhook.** Whether it answers 500 when a node throws.
- **The Build 02 guard, settled when filed.** It permits it: the guard checks
  state transitions and ULIDs only, never the verification fields. That was
  read in the code and not executed, and no test job was posted to prove it.
- **The `drive.draft` payload.** Which fields a `drive.draft` job carries.
- **The approval queue.** Its length limits on the title and `what_happens`.
- **Other readers of `gate_decision`** among the 45 active workflows.
- **The retired Cloud ledger.** Whether it is still readable.
- **Deployment.** Whether a merge to `main` deploys devon-soul, and whether
  `SOUL_DEVON_HOST` is set in production.
- **Executors and intake.** Whether executors strip unknown payload keys, and
  whether an intake `dry_run` writes no ledger row.
- **Table visibility.** Whether a data table upsert in the feeder is visible to
  the gate's read straight away.
- **`receipt_outcome`.** What values it can take other than completed.

## Seen in passing, not in scope

- `services/devon/vault.py` line 592 named the Cloud ledger
  `VYyno7pDWmY6uxBz` [V]. Fixed in the same PR that files this spec: both
  copies now name the VPS ledger `QZvdxllOjWevb3Vo`, the only table called
  `devon_state_ledger` on the instance.
- The gate's Pinecone Upsert sends `X-Pinecone-Api-Version 2025-01` on
  credential `YL4Q4rZ4yFssfQVy`. The committer sends `2025-04` on
  `5vCUF12UaOsgSqMF` [V].
- `select_unfed_jobs.js` line 17 compares against `VERIFIED`, while the ledger
  value is `passed`. Confidence is therefore always 0.6, which changes no
  decision [V].
- The live Stamp Run node has no copy in the repo [V].
- The live envelope's `learning` object does not match schema v1. Build 18
  writes a state value outside the schema's enum, and adds extra keys [V].

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_SPEC
ARTIFACT: docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md
DATE: 2026-10-07
DECISIONS: Tee ruled on 2026-10-07 to group related jobs, spec first for his approval. No decision in this spec is taken; fourteen are put to him, each with a recommended answer.
FINDINGS: A feeder job can never PROMOTE, because it sends one id per post against a two source bar and HOLD writes nothing. Independence means only distinct strings, and the evidence is fabricated. A failed subconscious upsert answers 200 PROMOTE. The committed soul record drops source_intent_ids and status. Recall ignores status. No job has been filed for 21 days.
OPEN: Every phase. The unverified items listed above.
STATUS: proposed, not built. Filed on PR #317.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
