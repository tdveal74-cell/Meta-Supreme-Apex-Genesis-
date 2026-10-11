# Learning lane grouping: Phase 2 built, criticised and fixed

This closes Phase 2 of
`docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md`. Tee ruled on
four cards on 2026-10-11:

1. One card per lesson, and the Soul Committer card is the lesson's approval
   (spec decision 8).
2. A rejected card and an expired card both close the lesson for good and
   burn its member jobs; the lesson key stays open (decision 6).
3. The committer reads the member jobs' ledger rows and the lesson's group
   log row itself, so every excerpt on the card is verbatim and uncut, rather
   than the feeder packing them into a note of up to 1000 characters.
4. The app's three soul recall readers gain the status filter in Phase 2,
   not in a later PR.

Nothing in this arc wrote to devon-soul, devon-subconscious or
tee-soul-layer, read `approval_queue`, or opened an execution of the
committer, the queue or the Drive reader. No lesson is declared, so no group
can form and nothing can be carded until Phase 3.

## What is live

The Soul Committer `drP96ernQvbrvzIZ` runs version `69829bd0`, read back
through the n8n API: `active` true, `versionId` equal to `activeVersionId`,
the active nodes and connections equal to the draft, all fourteen Code bodies
byte for byte equal to `n8n/devon/soul-committer/`, execution saving still
`none` for success and error and off for manual runs, and the error workflow
still `bqcnIS0Qv4RkTCU1`. It got there in three publishes on the same day:

- `e98bda27`, Phase 2, replacing `5e149077`. Two reads added before Select
  Next Proposal (Fetch Lesson Groups on the group log, filter gate_decision
  PROMOTE; Fetch Member Jobs on the ledger, filters COMPLETED, passed,
  human_watch; both executeOnce and alwaysOutputData), two Code nodes added
  for the refusal path, two columns added to Insert Commit Rows, seven bodies
  edited, the sticky note rewritten.
- `3f4fdc36`, the critic's code fixes below, four bodies edited.
- `69829bd0`, the sticky note made to describe those fixes. Nothing else
  changed against `3f4fdc36`.

Tables, in project `qbrcjkbIoorbwot6`:

- `devon_lesson_group_log` `3zmclyNLggMdRG2g` was created with the spec's
  fifteen columns after the collision check passed on 68 names. It holds 0
  rows. The spec had it in Phase 3; ruling 3 needs it to exist for the
  committer to read.
- The commit log `x8U4QqvXTVgINg3h` gained `lesson_key` and
  `source_intent_ids`. Its one row, the REVERTED smoke row, reads null in both.

T6 ran on a throwaway copy, `ujNCbaYsTdiINpdr`, with every store and host
stubbed: the queue reads and the two HTTP nodes replaced by Code stubs with no
host, the three mail nodes by stubs, and four throwaway tables in place of the
real ones. A grep of its definition found no real table id, no queue id, no
Pinecone host and no credential. Five executions:

- 2674: a card quoting both members uncut, a refusal with no group, a commit
  whose record carries `status: active` and the lesson fields, and an update
  that kept `lesson_key` and `source_intent_ids`.
- 2675: a refusal for a reused member, and a REJECTED closure that kept both
  columns. This settled the open question of whether a defineBelow update
  keeps the columns it does not name. It does.
- 2676: an idle run that wrote nothing.
- 2681 and 2682, with the critic's fixes: a lesson whose member was already
  used refused (my fixture reused a burned job, and the runtime caught it), a
  junk member list refused, a refusal email naming the burned jobs, and a
  card whose multi-line summary is fenced, leaving exactly one Conflict check
  line.

The copy is archived and its four throwaway tables are deleted.

Since the first publish at 11:45:47Z, the DEVON Error Alarm shows no
execution; its newest is from 2026-10-05. The committer saves no executions,
so that absence is the only evidence about its unattended hourly runs, and a
run that did nothing and a run that never fired read the same. The schedule
on the new version is therefore unproven beyond "no crash was reported".

The app half was not live when this was first written. `services/intelligence/soul.py` and its
vendored copy change on merge, so the merge redeploys Railway `api`,
`scheduler-cron` (which runs the planning recall through `create_task`) and
the Vercel `devon-soul` project; `presence` rebuilds on `services/**` with no
behaviour change.

**Read back after PR #323 merged as `3dc1b55`, 2026-10-11.** Main's CI passed
all six checks on `3dc1b55` at 15:16:23Z. Then, each read off the deployment
record, not inferred:

| surface | deployment | state | commit |
|---|---|---|---|
| Railway `api` | `e233e122` | SUCCESS 15:17:15Z, held WAITING until CI passed; `/api/v1/health` 200 healthy at 15:24:09Z | `3dc1b55` |
| Railway `scheduler-cron` | `ef804ce5` | SUCCESS 15:15:59Z | `3dc1b55` |
| Railway `presence` | `67bb2875` | SUCCESS 15:10:42Z; `/health` 200, `livekit_configured` true and `audio_over_websocket` false, the working pair on a build carrying `livekit_publisher.py` | `3dc1b55` |
| Vercel `devon-soul` | `dpl_7F5N45RjWEXCKzwQAHfHG4nq5pZa` | READY, target production | `3dc1b55` |
| Vercel `meta-supreme-apex-genesis-web` | `dpl_J3Jj1jhRRwkULtVZjB3mmVUBTXdK` | CANCELED by its ignore rule, correctly: nothing under its paths changed since its production build on `21aab2c` | not rebuilt |

So the filtered code is what production serves. Whether recall itself is
switched on there, `SOUL_RECALL_ENABLED` and a key on `api` and
`scheduler-cron`, is not something these tools can read: Railway returns
variable names only. That stays unverified, and Tee can check it in the
Railway dashboard.

## What is in the repo

- `n8n/devon/soul-committer/`: the twelve live bodies of `5e149077`, copied
  verbatim first in their own commit, then edited, plus
  `only_refused_items.js` and `refusal_notice.js`. Its test,
  `committer.test.mjs`, 37 checks, runs in the standalone job, drives the
  real bodies over the real 2026-09-16 ledger row, and applies the live
  nodes' own filters unless a check asks for raw rows.
- `services/intelligence/soul.py` and its byte identical deploy copy:
  `is_active`, `SoulRecall.active_only` with a withheld count, and
  `to_record` writing `status: active` on every record and the lesson fields
  only when there is a lesson.
- The three app readers call `active_only`. A test walks every `.recall`
  attribute in `app/`, `apps/`, `services/` and `scripts/` and fails unless
  it is called and its result is the receiver of `.active_only()`.
- The full api suite passed at `9b3bfa8`, 3494 tests, run alone. CI passed
  all eight checks on that head.

## The critic

Five critics, one each on the committer's logic, what is live, the Python
side, the records and the safety contract, each in its own worktree checked
out at `9b3bfa8`, and one skeptic per dimension that tried to refute every
finding. 27 findings: 25 confirmed or plausible, 2 refuted. None was armed
against anything live today, and after verification none was above low.

Fixed in code, published as `3f4fdc36`:

1. **Adoption could skip every lesson check.** A queued card was adopted on
   its evidence prefix alone, before the lesson's reasons were read, so a
   card for an unsound lesson, or one this committer never wrote, could be
   approved and commit. Now a queued card is adopted only when this poll
   reads the lesson as sound and the queued text quotes the exact claim that
   would be committed. A queued card for an unsound lesson is refused with its
   request id on the REFUSED row, where the commit lane cannot reach it.
2. **A multi-line summary could print a line that read as the card's own**,
   for example a second Conflict check line. Every excerpt line after its
   first is now fenced; the text is still whole.
3. The refusal email said the burned jobs were listed and listed none.
4. A group member list holding junk was read leniently. It must now be an
   array of ULIDs and nothing else.
5. `seen` was keyed by the raw intent id, so a case variant could be carded
   again; the Area could be scraped out of Tee's claim; a group that did not
   read PROMOTE could burn members; the no-group reason said the feeder had
   formed nothing. All fixed.

Fixed in tests: eleven mutations survived the first suite. Most survived
because every fixture was shorter than the cuts that would truncate a claim, a
summary or an evidence list; the rest because three closure branches, the
verify card anchor and the oldest first commit order were never asserted. The
suite now carries a 600 character claim, a 2100 character multi-line summary,
a four line evidence list and five members, plus those branches, and each of
the eleven was re-run and now fails it.
The recall guard was statement level and passed a call in an if, for, while
or with header, an alias, `getattr` and a ternary; it now checks each call,
and all four shapes were reproduced against it. The equality test between
`is_active` and the service's `_is_active` gained six inputs.

Fixed in the records: a stuck approved row is named by the Pulse at 76 hours,
not 96, and its text does not say why; a refused row's own intent id counts
as used; recall shows a record with no status; the app half is live only once
its deploys are read back. Commit `649a2b4` misnames the fourth ruling as
"the record says status active"; the list at the top of this doc is the right
one, and the commit is pushed, so it is corrected here rather than rewritten.

Refuted: that the README's corrected workflow count miscounts, and that the
burn's consistency rests on an untested live filter (the filter is documented
and the body now burns nothing for a non-PROMOTE group either way).

## Phase 3 contract, added by the critic

Written into `ids-and-contracts.md` and the spec where each applies:

1. The feeder writes the group row FED before the feed log row, because the
   committer refuses for good a PROMOTE whose group row is not yet FED.
2. The feed row's claim is copied from the gate's answer. The repair path
   that writes a missing feed row writes it only when the registry's current
   `claim_sha` equals the group row's, else marks the group STUCK. Until
   Phase 3, nothing binds the carded claim to the searched one except this
   rule (findings F1 and CS2, graded low because Tee approves the very text
   committed, and only the receipt would be stale).
3. The gate gets its own Fetch Commit Log, because the rule block refuses
   every member when that list was not read.
4. Form Lesson Groups appends each group it forms before it picks for the
   next key, so two keys declaring one job cannot both take it in one run.

## Where this departs from the spec

- The group log table and the two commit log columns were created in Phase 2,
  not Phase 3, because ruling 3 has the committer read the group log.
- The card's member excerpts come from the ledger and the group log, not from
  a feed log `evidence_note`. The feed log's three new columns stay Phase 3.
- REFUSED is a new commit log state. The spec said "refuses, and closes" and
  named no state.
- The committer is lesson only: a PROMOTE row with no group row is refused
  for good, including a hand corrected single job PROMOTE, whose job then
  counts as used. The runbook says so.
- The devon-soul record `_id` stays `devon-<date>-<request id>`. The spec is
  silent on it; `learning_intent_id` is carried as a field.

## Open

- The app's recall filter is deployed on all three surfaces, read back
  above. Whether recall is switched on in production is unverified.
- The carded claim is bound to the searched claim only by the Phase 3 rule
  above.
- The Pulse's text for a stuck approved row still says "still need your
  decision" from 48 hours and blames the 96 hour window at 76 hours. The
  committer fails closed; only the wording misleads. A Heartbeat change, not
  made here.
- `is_active` and `_is_active` differ on a non-Mapping metadata value; no
  real record can carry one.
- Carried from Phase 0 and 1: the `_is_active` empty status edge, the Build
  02 guard's forgeable verification text (decision 11), 52 active workflows
  counted against 45 in CLAUDE.md, the Heartbeat sticky's old SMTP id, two
  unpublished drafts, `vault.py`'s stale Cloud ids, and the gated second
  Python writer of devon-soul.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_learning-lane-grouping-phase-2_v1_2026-10-11-1250.md
DATE: 2026-10-11
DECISIONS: Tee ruled on four cards on 2026-10-11: one card per lesson, the committer card being the lesson's approval; rejection and expiry both close it for good and burn its members; the committer reads the ledger rows and the group log row itself; the app's recall readers are filtered in Phase 2. Earlier the same day: Phase 2 goes ahead, and the second job comes from real work.
FINDINGS: Committer live as 69829bd0 after e98bda27 and 3f4fdc36, read back byte for byte, saving still off. Group log 3zmclyNLggMdRG2g created empty, commit log columns added. T6 on a stubbed copy, executions 2674 to 2676, 2681 and 2682, then archived and its tables deleted. 27 critic findings, 25 confirmed or plausible, 2 refuted, none armed; the worst, adoption skipping every lesson check, is fixed and re-measured, and every surviving mutation now fails the suite.
OPEN: App recall filter deployed on api, scheduler-cron and devon-soul at 3dc1b55, read back; whether SOUL_RECALL_ENABLED is set in production unverified; claim to receipt binding rests on the Phase 3 contract; Pulse wording for a stuck approved row; is_active non-Mapping divergence; items carried from Phase 0 and 1.
STATUS: Soul Committer drP96ernQvbrvzIZ active 69829bd0, lessons only; nothing can be carded until Phase 3 declares a lesson and the feeder forms a group. PR #323 merged as 3dc1b55 on Tee's card ruling, and its deploys read back the same day.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
