---
title: DEVON Ecosystem
type: SYS_SPEC
version: 1
date: 2026-08-26
area: Systems
status: current
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
canonical_ref: main
owner: DEVON
supersedes_note: complements SYS_SPEC_devon-ecosystem-control-map_v1_2026-08-26
---

# DEVON Ecosystem v1

One organism. One intent. One receipt.

## What this document is

The DEVON ECOSYSTEM diagram Tee supplied on 2026-08-26, compiled into code. The
control map records the authority picture for humans. This records the parts
that now run, where each one lives, and what it refuses.

An audit on 2026-08-26 sorted the diagram into what was enforced, what existed
only on a map, and what was absent. This build closed the absent column. The
audit's honest split is kept below rather than smoothed over, because a claim
that everything is live would be exactly the failure this system exists to stop.

## The three words

| Word | What it means | Enforced by |
|---|---|---|
| One organism | Every box is one system, not a federation | `services/devon/ecosystem.py` holds the whole map in one module |
| One intent | Every input from any channel becomes exactly one Universal Intent with a UUID | `open_intent`, and `intents` in the ledger |
| One receipt | Every intent ends in exactly one Universal Receipt | `check_receipt`, and a unique constraint on `universal_receipts.intent_id` |

## Authority, locked

`TEE > TEE SOUL > DEVON > COUNCIL > AUTOMATION > TOOLS`

Locked means no code path reorders it and no caller supplies their own ordering.
`outranks` and `may_override` answer the question, and every refusal names its
reason. The Council stays under DEVON per Tee's ruling of 2026-08-26: the
External Intelligence box in the diagram is placement on the page, not a
promotion.

## The five layers of the mind

| Layer | Holds | May be written |
|---|---|---|
| 1 Tee Soul | Who Tee is, the eight facets | Never. Tee amends it outside the system |
| 2 Devon Attention | What DEVON notices now | Never written, rebuilt per intent |
| 3 Devon Conscious | What DEVON is thinking now | Never written; its durable trace is the ledger and the receipt |
| 4 Devon Subconscious | What DEVON has experienced | Appended through the learning gate, never edited in place |
| 5 Devon Soul | Who DEVON has become | Only with Tee's approval, through the Soul Committer |

`check_layer_write` is the gate, and it fails closed on a layer that does not
exist. The mind has five.

## The Live State Ledger

Ten tables in PostgreSQL, carrying the diagram's own names so the picture and
the schema can be read side by side: `intents`, `actions`, `events`,
`approvals`, `artifacts`, `executors`, `systems`, `errors`, `verifications`,
`learning_candidates`, plus `universal_receipts` for the receipt block.

Schema `database/schemas/012_live_state_ledger.sql`, migration
`012_live_state_ledger`, writer `app/services/live_state_ledger.py`, API
`/api/v1/ledger`.

If it is not in the ledger it did not happen, and a claim that disagrees with
the ledger is wrong.

**The ledger observes the approval authority. It never grants.** The authority
stays in `services/devon/approval.py` and its shared store. A row in `approvals`
records which request belonged to which intent and how it was ruled, so the
ledger can answer "was this approved" without becoming a second place that can
approve. There is deliberately no route under `/ledger` that approves anything.

## The Event Bus

Thirteen universal events, and the order they may occur in:

`INTENT_RECEIVED` `CONTEXT_LOADED` `SOUL_READ` `SUBCONSCIOUS_RECALLED`
`PLAN_CREATED` `APPROVAL_REQUESTED` `APPROVAL_GRANTED` `ACTION_STARTED`
`ACTION_COMPLETED` `ACTION_FAILED` `VERIFICATION_PASSED` `ARTIFACT_CREATED`
`LEARNING_CAPTURED`

Laws, all enforced by one function so the checker and the writer cannot drift:

1. Every intent opens with `INTENT_RECEIVED`, and is received exactly once.
2. Each event names what must already stand on the intent before it.
3. `ACTION_STARTED` on an effect intent requires `APPROVAL_GRANTED` first.
4. Two events are reserved to services over HTTP, dated 2026-09-02: `APPROVAL_GRANTED`, and a `PLAN_CREATED` whose payload names an `approval_request_id`. `POST /api/v1/ledger/intents/{id}/events` refuses both with 403; the knowledge loop writes them at approve and propose. The intent read may still list `APPROVAL_GRANTED` as legal next; that is the ledger law, not the HTTP contract.
4. No action starts while the emergency stop holds.
5. Only the thirteen. The database carries the same list as a check constraint,
   so a caller that never touches the writer still cannot invent an event.

Intent state is derived from the events on every append rather than set by a
caller, so the summary column and the event log can never disagree. A failure
after a completion leaves the intent failed: the ledger reports the worse truth.

## The Universal Receipt

One per intent, refused twice over: by `check_receipt` and by a unique
constraint. Required content is `what_happened`, `verification`, `provenance`;
optional is `artifacts`, `learned`, `next_steps`.

A receipt cannot be issued before the intent reached a terminal event, and an
effect intent that skipped its gate cannot be receipted at all. An amendment is
a new intent, never a second receipt.

## Memory indexes and deletion protection

| Index | Layer | Protection |
|---|---|---|
| `tee-soul-layer` | Tee Soul | PROTECTED (MAX), read only |
| `devon-soul` | Devon Soul | PROTECTED, approval gated writes |
| `devon-subconscious` | Devon Subconscious | PROTECTED (POLICY), learning lane appends |

`may_delete_index` refuses every index, including one it has no record of,
because deleting the unrecorded is still deleting. A single record is a
different question: reversible by design in the subconscious, and requiring the
same ruling that created it in the soul.

Deletion protection is now also sent to the vendor at index creation
(`services/intelligence/soul.py`), because a policy that lives only in this
repository cannot stop a console click or a script that never imports it. The
value is declared once in the doctrine and imported, so the two cannot drift.

The three indexes that already existed carry vendor deletion protection too.
Tee confirmed it on 2026-08-26, so the gap the audit recorded is closed at the
vendor as well as in code. That confirmation is a stated fact rather than a
read this repository performed: nothing here can query Pinecone, so a later
reader who needs certainty checks the console rather than trusting this line.

## The action execution layer

DEVON decides where. `route_action` sends internal duties to n8n and commercial
ones to Zapier, and parks anything it does not recognise as `UNROUTED` rather
than guessing. A guessed executor runs the wrong thing somewhere real, and
unlike a wrong tag it cannot be corrected after the fact.

| Executor | Role | Boundary |
|---|---|---|
| n8n | internal executor | Runs inside the estate. Still passes the approval gate for effects |
| Zapier | external executor | Reaches commercial services. Never holds DEVON canon or secrets |

## Emergency stop

Any level may engage it: a stop that needs permission is not a stop. Only Tee
releases it, because releasing is a decision to let effects run again. While it
holds, no action starts. Work already started is reported as it actually ended,
never as cancelled.

Engaged and released through `/api/v1/ledger/emergency-stop`, stored as a
control row in `systems`, and checked on every `ACTION_STARTED`.

## The four portfolio properties

`TQO` The Quiet Operator, `TSWS` The Shadow We Share, `NCO` NCO Forge, `ACX`
Ascension Caudex. They share infrastructure only where DEVON approves the shared
service. Their canon, visual systems, audiences and strategy do not merge.

The Area registry in `services/devon/areas.py` owns these codes. This module
lists them and a test asserts every one still resolves through that registry, so
the map can never become a second registry that drifts.

## Deployment, read back

Merging is not deploying, so this section records the read back rather than the
merge.

**Standing read back, 2026-09-05 at 20:50Z, against main at `077d7b5`.** All
three surfaces verified current, after the third account block cleared.

| Surface | Deployment | Commit |
|---|---|---|
| Railway `api` | `38d5d387` SUCCESS, created 19:56:13Z and finished 20:02:21Z; the deploy log carries the alembic context lines from the pre deploy hook | `077d7b5` |
| Vercel `devon-soul` | `dpl_E9Whg4NdDRbntcBxp1sik356MEg3`, READY, `target: "production"` | `077d7b5` |
| Vercel `meta-supreme-apex-genesis-web` | `dpl_7pK6tCvCMGB7wVhub9Y36bbxF79v`, CANCELED, `target: "production"`, which is the `ignoreCommand` skipping | `077d7b5` |

The web skip was verified by hand rather than trusted: `cb01b7a..origin/main`
over `apps/web`, `packages/ui`, `pnpm-lock.yaml` and `pnpm-workspace.yaml` is
empty, and `cb01b7a` is the last commit that actually built that project. So
nothing is owed to the web surface and it is current on its own terms. The
block that stood earlier in the evening is settled by these records existing at
all, which is the only signature a block leaves.

**Superseded read back, 2026-09-04, against main at `edaf03e`.** All three
surfaces verified current.

| Surface | Deployment | Commit |
|---|---|---|
| Railway `api` | `406809cc` SUCCESS at 19:31:41 UTC, container started, application startup complete at 19:31:34, `alembic upgrade head` ran in pre deploy with nothing pending | `edaf03e` |
| Vercel `meta-supreme-apex-genesis-web` | `dpl_XeMEfHQZju83jE28yW2aovwk9Voq`, READY, `target: "production"` | `f476195` |
| Vercel `devon-soul` | `dpl_9Uf6twCzfiTFXUogMJntNv4xHorG`, READY, `target: "production"` | `94c49af` |

Both Vercel surfaces sit behind main on purpose and both are current on their
own terms. Every production deployment since is `CANCELED`, which is the
`ignoreCommand` skipping. The skips were not taken on trust: each project's
real rule was read out of its own `vercel.json` and the same comparison run by
hand, `f476195..edaf03e` over `apps/web`, `packages/ui`, `pnpm-lock.yaml` and
`pnpm-workspace.yaml`, and `94c49af..edaf03e` over `deploy/soul`. Both empty,
so nothing is owed to either surface.

That day also carried the second account block. Vercel answered "Account is
blocked" on the PR #132 head at 19:01Z, Tee cleared it, and the merge created
deployment records on both projects at 19:24:57Z, which is what settles a block
rather than any status turning green. `list_teams` on the same day reports the
account on the Pro plan, so the free plan cap below is history and no longer
the limit. When it moved is not recorded anywhere this repository can read, so
do not date the move from this line; the reading is what is verified.

**Superseded read back, 2026-08-26.** Kept because the promotion and the cap it
describes are what the rules were built from.

| Surface | Deployment | Commit |
|---|---|---|
| Railway `api` | `a6c1908c` SUCCESS at 13:01:58 UTC, healthcheck passed, `alembic upgrade head` ran with nothing pending | `c0fa80c` |
| Vercel `meta-supreme-apex-genesis-web` (recorded as `meta-supreme-web` until 2026-09-02; that project no longer exists) | `dpl_Bf5QS6rzDyJoWBqf5msoX2vUitep`, READY, `target: "production"` | `5f409cf` |
| Vercel `devon-soul` | `dpl_6e6XWExoD7xSYb5uDKjT1t6C4mp1`, READY, `target: "production"` | `5f409cf` |

The two Vercel surfaces reached production by promotion at 11:10 UTC after the
free plan cap of 100 deployments a day blocked the automatic production builds
earlier in the day. `5f409cf` and repo main `44568cd` differ only by the merge
commit; their trees are byte identical, so production carries main's content.

Railway was four merges behind on 2026-08-26 and nothing noticed. From that
day until 2026-09-01 this section recorded autodeploy as disabled, on the
observation that the Railway GitHub App was not installed, with a standing
instruction to deploy every merge that touches container code by hand. The
staleness it described was real: legitimate through `#70`-`#72` (docs, skills,
`vercel.json`, none of which the API builds from), real at `#73`, closed by
the hand made deployment `a6c1908c` at 13:00 UTC.

The record then went stale the way this document warns everything does. By
2026-08-31 autodeploy was working: deployment `5a86779f` built itself from the
`#107` merge commit `abdc03b` with trigger `push`, and a read back on
2026-09-01 confirmed recent merges to `main` deployed without hands. Nothing
recorded when the GitHub App was installed or by whom. The manual deployment
instruction is withdrawn; the read back rule is not. A merged PR is still not
a shipped one until the deployment id, state and commit are read back, and
`scripts/estate_reconcile.py` now pins this section's sentences so the next
silent reversal fails a run instead of waiting for a session to trip over it.

A `target` of `null` on a Vercel deployment means preview, not production. That
distinction is written down here because reading a green preview as a shipped
production build is the exact mistake this document exists to prevent.

## What is still not live, stated plainly

- **The learning lane's own half.** Promotion into `devon-subconscious` and the
  approval gated commit into `devon-soul` run as live n8n workflows recorded in
  `services/devon/vault.py`. This repository holds their gates, not their
  execution. `learning_candidates` is where the ledger parks what might feed
  them; it does not promote anything by itself.
- **The external operating surfaces.** Claude, ChatGPT, Codex, Deep Research,
  Work, connected apps and scheduled tasks report `contract_ready` with
  `live_verified: false` until each returns its own receipt. No invented green.

## Where it lives

| Part | File |
|---|---|
| Doctrine, effect free | `services/devon/ecosystem.py` |
| Ledger schema | `database/schemas/012_live_state_ledger.sql` |
| Migration | `database/migrations/versions/012_live_state_ledger.py` |
| Storage models | `app/models/live_state_ledger.py` |
| Writer, the only thing that mutates | `app/services/live_state_ledger.py` |
| API | `app/api/v1/ledger.py` |
| Vendor deletion protection | `services/intelligence/soul.py` |
| Pure tests | `test_devon_ecosystem.py` |
| Database tests | `test_live_state_ledger.py` |

`services/devon/ecosystem.py` performs no effect. It opens no socket, writes no
row, calls no executor and touches no index. The writer does all of that and
asks the doctrine first, which is the same split every other module in the
package keeps and which `test_devon_integrity.py` enforces.
