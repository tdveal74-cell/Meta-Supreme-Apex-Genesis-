---
name: estate-reconcile
description: Run the estate truth reconciler, check every record's claims against the live estate, and write back, dated, whatever drifted. Load when asked whether the records are true, before trusting vault.py or a spec sentence about live state, on any scheduled estate audit, after a migration or cutover, or the moment a session finds a record disagreeing with a live read. Compiled from 2026-08-31 to 2026-09-01, when five records were found stale and the first three were only caught by a session tripping over them.
---

# Estate truth reconciliation

The standing failure class of this estate is drift: an artifact is written,
reality moves, and nothing writes back. `scripts/estate_reconcile.py` turns
that class into a failing run. This skill is how to run it, how to read what
it says, and what the write-back owes the next reader when it fails.

## Rule zero: the live estate is the authority

A record is a claim about the estate, never the other way around. When they
disagree, either the record drifted or an unrecorded hand moved the estate,
and both endings are the same ending: the record gets corrected, dated, in
place, or the estate gets fixed through its gates. The one forbidden outcome
is leaving them disagreeing silently. A reconcile run that found drift and
ended without a write-back has not finished.

### The list of places is a claim too

Rule zero governs a record's values. It does not govern the record's own
inventory of what there is to check, and that inventory rots the same way.

Re-measuring every row a record has does not test whether the record has every
row. A block can be re-read end to end, be right about all of it, and still be
wrong, because a place existed that it never listed. Count the places from the
estate on every pass, not from the last version of the record.

Measured 2026-09-12, on the DEVON Area vocabulary. The canonical record listed
four places the vocabulary had to stay in sync across. The estate held five:
Airtable carried it in two fields, not one, and no version of the record had
ever named the second. The 2026-09-06 pass had re-measured all four rows
correctly six days earlier.

## The tool

    python3 scripts/estate_reconcile.py snapshot --out obs.json
    python3 scripts/estate_reconcile.py check [--observations obs.json] [--strict]

`check` exits nonzero on DRIFT. A source with no key reports UNVERIFIED and
does not fail the run unless `--strict` is set; scheduled runs that are
supposed to hold keys should always pass `--strict`, because an expired key
quietly turning every claim UNVERIFIED is itself the failure class.

Claims come from two places. `services/devon/vault.py` is imported, it is
data only, and every webhook auth mode, workflow state and the instance host
become claims. Documents cannot be imported, so `DOC_CLAIMS` in the script
pins each checkable sentence by exact quote: while the quote is in its doc
the claim is checked, an amended doc retires its claim, and the retired pin
stays as a tripwire so a resurrected sentence is checked again on the next
run, and the test suite pins the spec's corrected sentence unconditionally.

Prose rulings have no machine readable shadow. Every run ends by listing the
open rulings, and retiring one is human work: read it, check whether it still
describes reality, and amend the entry if it does not.

Env, all optional, all read only: `N8N_SOURCE_URL` and `N8N_SOURCE_KEY`
(same pair as `scripts/n8n_migrate.py`, key needs workflow:list and
workflow:read), `RAILWAY_API_TOKEN`, `RECONCILE_MAIN_HEAD` (defaults to
`git rev-parse origin/main`).

## Taking a snapshot without keys

A Claude session with the estate's connectors can build the observations file
from read-only MCP reads instead of env keys, which is how the first run was
done. Fan the reads out in parallel, never mutate anything, and assemble:

    {
      "read_at": "<ISO timestamp of the read>",
      "n8n": {
        "host": "<instance URL>",
        "workflows": {"<id>": {"name": "<name>", "active": true}},
        "webhooks": {"<workflow id>": [
          {"path": "<path>", "auth": "headerAuth|none", "method": "POST"}
        ]},
        "gates": {"<workflow id>": [
          {"name": "<node name>", "type": "n8n-nodes-base.code",
           "sha256": "<fingerprint>", "wired": true}
        ]}
      },
      "railway": {"deployments": [
        {"id": "...", "status": "SUCCESS", "commit_sha": "<full sha>",
         "created_at": "..."}
      ]},
      "repo": {"main_head": "<full sha of origin/main>"}
    }

`wired` is true only when every enabled door in that workflow (its webhook
triggers and public chat triggers) feeds the gate node and nothing else, read
from the workflow's `connections`. A trigger rewired past the gate leaves the
node byte identical, so the fingerprint alone would pass it; a snapshot that
lacks the key reports the gate UNVERIFIED rather than OK.

`workflows` must be the complete census, every workflow including inactive
ones, or the count claim checks a fiction. `webhooks` needs entries for the
workflows `vault.WEBHOOKS` names; read each workflow's detail and keep only
its Webhook trigger nodes, recording the `authentication` parameter as the
node carries it, absent meaning `none`. `gates` needs an entry for every
workflow whose vault entry pins a `body_gate`: list its enabled Code nodes by
name, and for each record `code_fingerprint(jsCode)` from the script, never
the code itself, so the snapshot does not become another copy of whatever
secrets the node holds. A snapshot without `gates` reports those claims
UNVERIFIED, which is the honest reading of an older file, and fails a
`--strict` run for the same reason a missing key does. Railway needs the
five most recent deployments of the API service with the commit each built
from.

## Reading a run

- `DRIFT` is work, today. See the write-back doctrine below.
- `UNVERIFIED` is honesty about reach, not a pass. If the run was supposed to
  hold that key, treat it as a failure and find out why the read died.
- `RETIRED` is a corrected doc sentence still pinned as a tripwire. Expected
  and quiet. If a RETIRED claim ever flips back to checked and failing, a doc
  edit resurrected a corrected sentence, and that edit is the drift.
- The open rulings list is not decoration. Read it every run.

## The write-back doctrine

A write-back never attributes a decision to Tee that Tee did not make. A
reading derived from a record's own rules is labelled as derived, with the line
to overturn named, so the next reader can tell a ruling from an inference. This
costs one clause and it is not optional: a fabricated attribution is
unfalsifiable once it is in the canon, because every later reader treats it as
settled and stops checking.

Measured 2026-09-12: a rewrite of the canonical Area vocabulary file recorded
an ordering call as "Ruled 12 Sep 2026." Tee had ruled that day, on pinning a
base ID. He had not ruled on ordering; the agent had, and dressed it as his.
The file was withdrawn inside the hour and kept as a defective copy rather than
deleted.


When a vault claim drifts, correct `services/devon/vault.py` and keep
`deploy/soul/services/devon/vault.py` byte identical, `cp` then `diff`.
The correction records what was wrong and for how long, in the entry or its
comment, the way the Heartbeat entry does. Never silently swap a value: a
reader who reasoned from the stale record needs to know the window.

When a doc claim drifts, amend the doc in place, dated, keeping the history
("was recorded as X until DATE") rather than deleting it. The amendment
removes the pinned quote, which retires the claim; leave the retired pin in
`DOC_CLAIMS` as the tripwire.

When the claim language cannot parse an entry, `node_auth_for` and
`workflow_state_for` raise rather than skip. Extend `_AUTH_PREFIXES` or
`_STATE_PREFIXES`; an unparseable claim is an unchecked claim, and skipping
it recreates the silent gap the tool exists to close.

When the estate side is what needs fixing, stop. Activating or deactivating
a workflow, deploying, repointing a webhook: those are effects, they stay
behind the approval gate, and they are Tee's ruling to make. This skill
corrects records freely and performs no estate effect, ever.

New checkable sentence in a doc? Pin it in `DOC_CLAIMS` while writing it.
A claim born pinned never gets the chance to rot unchecked.

Before pushing any write-back: `python3 -m pytest -q test_estate_reconcile.py
test_devon_integrity.py`, then `ruff check .`. No em or en dashes anywhere in
the changes, `test_devon_integrity.py` enforces it for the package and docs
and `test_estate_reconcile.py` enforces it for the reconciler's own files.

## What drift looks like, from the record

Five stale records in nine days, for calibration:

| Record | Said | Reality | Stale for |
|---|---|---|---|
| `vault WEBHOOKS devon-capture` | auth None | headerAuth since 2026-08-23 | 8 days |
| `vault WEBHOOKS devon-approve-request` ruling | fix pending | fixed 2026-08-25 | 6 days |
| Ecosystem spec, deployment section | autodeploy disabled, deploy by hand | pushes to main self-deploying | days, unwitnessed |
| `vault WORKFLOWS Heartbeat` | active, 6 hour pulse | inactive, pulse dead | found 2026-09-01 |
| `vault WORKFLOWS Error Alarm` | active | inactive | found 2026-09-01 |

## Three ways a read comes back partial

Every one of these was reported as a confident finding before it was caught,
in a single session on 2026-09-12, against a record that four earlier passes
had already touched. They are listed separately because each one looks like a
completed read from the inside.

**A truncated tool result is a silent partial read.** When a response exceeds
the harness limit it is diverted to a file and the tool returns a pointer, not
the data. The session that reads two of three items, hits the limit on the
third and stops has surveyed nothing, and nothing in its own transcript says
so. Query the saved file before drawing any conclusion about coverage. Measured
on an Airtable schema call that returned 104,092 characters: the base that was
skipped held the two fields the session then reported as never built.

**A grep is not a read.** Keyword matching finds the section that matches and
tells you nothing about the file. In the same session the base ID reported as
missing from the estate was sitting in `devon-thread-log` itself, roughly forty
lines below the section that had been searched. Before saying where something
lives, or that it does not, read the file.

**A synced skill is a copy, and you do not control when it refreshes.** An
account-level Claude skill is mirrored into the session container at
`~/.claude/skills/synced/<id>/<name>/SKILL.md`. The sync service refreshes it on
its own schedule, which is neither session start nor read time: measured
2026-09-12, one copy carried an 8 Sep stamp through several hours of a session
and then refreshed mid-session, four days newer, with no read having asked for
it. Invoking the skill through the Skill tool resolves to that same file, so it
is not a second opinion, and there is no write path to the live skill at all.

An agent therefore knows what its copy says and when that copy was stamped. It
cannot force a refresh and cannot tell whether a newer version already exists.
So report both halves or neither: `stat` the file and give the contents with the
mtime, never a bare verdict about the live skill. "The skill says eight" and
"my copy, stamped four days ago, says eight" are different sentences, and
collapsing them puts a false status into a record under today's date. A record
row covering an account-level skill carries Tee's attestation with the date he
gave it, or it carries nothing.

Measured 2026-09-12, twice in one session. First a copy stamped 8 Sep was read
on 12 Sep, reported as a 12 Sep measurement, and written into the canonical
file; Tee corrected it. Then the same paragraph was written claiming the copy is
"never refreshed", and the copy refreshed forty minutes later. Both errors came
from describing the live artifact when only the copy was in hand.

## Traps

- A container without `requirements.txt` installed does not fail a tidy
  handful of tests, it aborts collection outright, and even with the
  missing modules stubbed in the pre-existing failure count runs to
  hundreds. Never read any of that as damage from a write-back: run the
  same pytest selection on a clean checkout (`git stash`, run, `git stash
  pop`) and compare, because CI installs the requirements and sees none
  of it.
- Some MCP reads return HTML-escaped names (`&amp;`). Ids are the join key,
  never names; unescape before showing a name to a human.
- An n8n error workflow fires when a caller names it whether or not it is
  active, so an inactive Error Alarm is record drift, not proof the alarm
  lane is down. An inactive schedule workflow is the opposite: its timer is
  genuinely not running.
- A manual workflow ("manual, read only" in the vault) is inactive on the
  instance. The claim language maps it that way on purpose.
- The census counts what `/api/v1/workflows` returns. Archived workflows do
  not appear in the default listing, so archiving changes the count and the
  migration doc must be amended when that happens.
- The n8n list and detail reads leave no trace on the instance. Snapshot
  freely; it is the one effect-free half of this whole discipline.
