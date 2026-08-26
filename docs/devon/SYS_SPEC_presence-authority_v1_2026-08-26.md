# Presence authority (Build 15, v1, 2026-08-26)

The ruling, in Tee's words on 2026-08-26: **in a live conversation his message
IS the approval.** Conversation unlimited and instant; consequences not gated
behind an emailed card; everything receipted.

This document is what that became in code, including the part that was wrong
for a day and how it was found.

## The rule

`services/agent_runtime/presence.py` holds the whole policy as a pure function
of a `ToolSpec` and a `Caller`:

| tool | present human | nobody present |
|---|---|---|
| READ | run | run |
| reversible WRITE | run | approval card |
| irreversible / HIGH_IMPACT | confirm inline | approval card |
| named in `ALWAYS_CONFIRM_TOOLS` | confirm inline | approval card |
| BLOCKED | refuse | refuse |

`decide()` takes a `Caller` object, not a boolean. A bool is one typo away from
letting a model turn its own output into consent; a `Caller` is built by the
transport that authenticated a human and by nothing else.

The approval queue is not removed. It is the right instrument for an absent
human and stays exactly as it was for every automated caller. The daily
reflection can still want things and still cannot do them.

## What the gauntlet found

An adversarial pass on 2026-08-26 (39 agents, 35 findings raised, 13 confirmed,
22 refuted) established that the first cut of this did not work. Not "had
rough edges". Did not work. Five things, in the order they matter.

### 1. No confirmation could ever be answered

`confirm_binding` folded the turn id into the token. The endpoint minted a fresh
random turn id on every request, and `ActRequest` carried only `content` and
`confirm_token`. **There was no value any honest client could send that would
match.** Every yes was refused with "confirmation does not match this action; it
was given for something else", which reads like a tampering alert rather than a
design fault.

The unit tests missed it because all of them used a module-level constant
`TURN = "TURN-42"` and computed the token from it. The binding logic was
correct and unreachable, and nothing drove the endpoint.

### 2. Even fixed, the token was forgeable

A SHA-256 of the turn id, tool name, and arguments is a hash of public inputs,
not a secret. Any caller who could name those three could compute a valid
confirmation for a call DEVON never proposed. That turns "confirm this" into
an unmetered tool-invocation API for anything holding a session.

### 3. Answering yes re-ran the work

Resuming meant driving the whole turn again with a token attached, so every
read and every reversible write that preceded the question happened a second
time. Reproduced: `REQ1 ran: ['browser.navigate']` → `REQ2 ran:
['browser.navigate', 'browser.navigate']`.

### 4. Presence never reached a real tool

Every guarded adapter recomputes the approval binding itself and then demands
an APPROVED `ApprovalQueue` record raised by the runtime. That is `github.*`
through `require_approved_runtime_binding`, and `operator.command` through
`execute_runtime_approved`. The presence path supplied none. So a confirmed, authorised write
returned `ToolResult(ok=False, error="runtime approval metadata is missing")`
and the entire feature executed reads and three in-memory `runtime.*` proposals.
It looked like it worked and could not touch anything Tee owns.

### 5. The transcript recorded only successes

Persistence ran under `if answered:`. A turn that halted, stopped on a
confirmation, hit the step limit, or failed wrote nothing at all, including
turns that had run real effects first.

## The decisions taken

### Presence mints the record; the adapters keep their own check

The design question finding 4 raises is a governance one: should a present
caller's ruling **mint an approval record**, or should the adapters learn a
second way to accept a presence decision?

Minting. Under Tee's ruling his live word already IS the approval, so what was
missing was never the authority. It was only the record. Teaching each adapter
a second acceptance path would put two doors on every effect and leave the
independent recomputation checking only one of them. Minting keeps exactly one
door.

`PresenceExecutor._authorise` therefore raises the card and rules on it in the
same call stack, server side, before the handler runs:

- binding computed over the exact arguments, with `turn_id` as the task id and
  the turn's step number as the step id;
- `requested_by` = `DEVON Agent Runtime`, which the adapters verify;
- `decided_by` = the authenticated actor plus `(present)`, so the row says who
  and how;
- the single-use token never leaves the method.

`require_approved_runtime_binding` then recomputes the binding independently a
moment later and finds the row. Unchanged, and still the thing that decides.

The queue row is also the receipt half of the ruling. Every effect run under
presence leaves one, and its id is named in the stream (`approval_request_id` on
`tool_result`) while Tee is watching it happen.

**Fail closed:** an executor with no queue, or a queue that cannot record, does
not run the effect. An effect DEVON cannot account for is one he does not run.

### A confirmation is something the server remembers

`services/agent_runtime/pending.py`. The handle is random, the action is stored,
the claim is single use and scoped to one conversation and one user, and it
lapses after 15 minutes. A client echoes the handle and nothing else, so it
cannot name an action DEVON did not propose.

Answering **resumes** the turn: the stored observations carry the earlier work
forward, the confirmed call runs, and only then is the model asked what next.

Process-local, deliberately. An inline question is asked of someone reading the
stream right now; if the process restarts or he walks away, the right outcome is
that the question lapses and he is asked again. The durable 72-hour instrument
for an absent human already exists and this is not it.

### Everything else

- **Transcript**: every ending writes both rows. With no answer, the assistant
  row says how it ended and names the tools that ran first.
- **Cost**: `PER_TURN_TOOL_BUDGET` caps `council.consult` at one per turn.
  `max_steps` bounds the loop's provider calls and says nothing about a tool's
  own fan-out; one consultation can spend well past a hundred completions.
- **The brake**: the request session is released before the stream opens. A
  stream lives as long as its turn, and a session held across it pinned a pool
  connection for that whole time, which is how long turns could starve the very
  endpoint Tee would use to stop them.
- **Forged metadata**: `_devon_runtime_approval` is stripped from model-authored
  arguments before the decision, the binding, and the handler. A tool call
  cannot carry its own permission slip.

## Known open, deliberately not in this change

**An APPROVED record is replayable.** `ApprovalState` has no CONSUMED state, so
nothing marks a record as spent once its effect has run. Anyone able to present
a valid `request_id` plus binding to a capability adapter could replay the
approved effect.

Not introduced by presence, and not made materially worse by it: the presence
path's `request_id` is created and used inside one call stack and never leaves
the server, so replaying it requires code execution on the API host. The
exposure that predates this is the durable runtime path, where the request id
travels to a human by email.

The fix, named so the next session does not re-derive it: add
`ApprovalState.CONSUMED`, a `transition_approved` method on the store protocol
alongside `transition_pending` (same compare-and-set shape), a new re-runnable
schema file widening `ck_devon_approvals_state` and
`ck_devon_approvals_decision_shape`, and a call in
`require_approved_runtime_binding` that consumes on success. It is a schema
change against a shared table on a live deployment, which is why it is its own
change and not a rider on this one.

## Where to look

| what | file |
|---|---|
| the policy | `services/agent_runtime/presence.py` |
| the brake | `services/agent_runtime/halt.py` |
| one step under presence | `services/agent_runtime/conversation.py` |
| the loop | `services/agent_runtime/agent_turn.py` |
| stored confirmations | `services/agent_runtime/pending.py` |
| the transport | `app/api/v1/conversations.py` (`/act/stream`, `/halt`) |
| what the adapters check | `services/agent_runtime/governance.py` |

Tests: `test_devon_presence_authority.py` (policy),
`test_devon_conversation_turn.py` (one step, binding, brake),
`test_devon_agent_turn.py` (the loop), `test_devon_pending_confirmations.py`
(handles), `test_devon_agent_turn_api.py` (**the endpoint, over HTTP**, which
is the layer where every blocker above actually lived).
