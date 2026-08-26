# Build 15 close-out: presence authority, live (v1, 2026-08-26)

Supersedes nothing. Closes the arc opened by Tee's ruling of 2026-08-26 that in
a live conversation his message IS the approval, and by the ask behind it: "i
should be able to interact with Devon like I interact with you."

The design account lives in `SYS_SPEC_presence-authority_v1_2026-08-26.md`. This
is the operational record: what shipped, what proves it, and what is still open.

## What is live

| | |
|---|---|
| Merge commit | `67065cf`, PR #75, merged 2026-08-26T17:24Z on standing authorization |
| CI at merge | run 32992342964 on head `6a21b85`, all four jobs green |
| Railway deploy | `d057b04f`, created 17:25:04Z, SUCCESS 17:26:32Z |
| Previous deploy | `e162f73d` on `6704894` (PR #74) |
| Vercel | rate limited, `api-deployments-free-per-day`, all four projects, clears in 24h |

The merge commit has two parents, `6d6b1d5` (PR #76, EditForge governed
execution, merged by another session at 16:50Z) and `6a21b85`. Both verified
present in main's history before the deploy was accepted.

## Autodeploy is confirmed working, behaviourally

This was an open question carried from the 2026-08-26 morning session, where
Railway was found stale because the GitHub App was not installed and two deploys
had to be run by hand. Installing it was Tee's action; whether it actually
worked could only be settled by a merge.

It is settled. Deployment `d057b04f` was created twenty seconds after PR #75
merged, `reason: deploy`, naming commit `67065cf` on branch `main`, with no
manual trigger. Nothing in this session deployed anything by hand.

## How far the deploy was verified, and where it stops

Verified from here:

- deployment `d057b04f` status SUCCESS on commit `67065cf`, branch `main`
- container started 17:26:27Z, alembic ran against the production database,
  `agent registry seeded`, `Application startup complete`, uvicorn serving on
  `0.0.0.0:8080`
- the same commit passed the CI container-contract job, which imports
  `app.main` inside the production image

NOT verified from here, and stated rather than implied: no HTTP read-back of
`/openapi.json` or `/conversations/{id}/act/stream` against
`api-production-5644.up.railway.app`. The agent proxy refuses egress to that
host (`CONNECT tunnel failed, response 403`), which matches the standing note in
the `steward` skill that live-environment verification cannot run from CI or
agent containers and is always a manual item for Tee.

So the claim this doc supports is: the new image built from `67065cf` is running
and serving. The claim it does NOT support is that anyone has called the new
endpoint and got a turn back. That is the first thing to do once
`DevonChat.tsx` is wired, and it is the real acceptance test for Build 15.

## The surface

`POST /conversations/{id}/act/stream` runs one turn and streams it.
`POST /conversations/{id}/halt` stops one by id. Event contract:

`turn_started` then (`turn_resumed` / `tool_started` / `tool_result` /
`tool_unknown` / `refused` / `tool_capped`)* then exactly one terminal event:
`answer`, `needs_confirmation`, `card_required`, `halted`, `step_limit`, or
`error`.

A `needs_confirmation` event carries an opaque `confirm` handle. Echo it in the
next request's `confirm` field to resume the turn. The handle is single use,
scoped to one conversation and one authenticated user, and lapses in fifteen
minutes.

## What it cost to get right

Two adversarial passes, eight confirmed defects between them. The first cut did
not work at all: no confirmation could be answered, and presence never reached a
single guarded tool. The second pass then found that irreversible WRITEs ran
without asking, which was worse than anything in the first round.

The lesson worth carrying, because it caused both: **the tests never drove the
endpoint.** Every unit test built its own ToolSpec and used a module-level turn
id constant, so they proved the logic read its inputs and proved nothing about
the transport or the real tool registry. `test_devon_agent_turn_api.py` exists
to make that impossible to repeat, and two tests in
`test_devon_presence_authority.py` now assert against `build_tool_registry()`
rather than hand-built specs.

Two tests were deleted rather than kept during that work: one leaked a pool
connection and broke its neighbour, one hung on failure instead of failing. A
test that damages the run around it is worse than no test.

## Open, in priority order

1. **`DevonChat.tsx` is not wired to `/act/stream`.** The backend is done and
   the event contract has settled, but the Command Center still calls
   `/intelligence/ask` and `/agent-tasks`. Until this lands, none of Build 15 is
   reachable from the surface Tee actually uses. Next PR, off a fresh branch.
2. **`ApprovalState` has no CONSUMED state**, so an approved effect is
   replayable by anyone able to present a valid `request_id` plus binding to a
   capability adapter. Predates presence. The exact fix is scoped at the end of
   the spec doc; it is a schema change against the live shared `devon_approvals`
   table and needs its own PR.
3. **A disconnect still loses the assistant transcript row.** Tee's own message
   is now written before the stream opens and is safe. The assistant row is
   best-effort and shielding does not fix it. The durable record of any EFFECT
   is the approval row, committed before the handler runs, so this costs
   conversational history and never the audit trail.
4. **Process-local stores.** The halt registry and the pending-confirmation
   store are per API process. Correct at one replica (Railway
   `numReplicas: 1`), and the failure direction is safe: an unrecognised handle
   is refused and DEVON asks again. Redis is the fix when the service scales out.

## Verification standard used

All four CI jobs were reproduced locally before every push, against PostgreSQL
16 with pgvector, including the standalone job run exactly as CI runs it with no
`PYTHONPATH` and no database. 997 tests passed at merge. The `steward` skill was
corrected in the same arc: it said CI was three jobs (it is four, the Railway
container contract was missing) and named an alembic head two versions stale.
