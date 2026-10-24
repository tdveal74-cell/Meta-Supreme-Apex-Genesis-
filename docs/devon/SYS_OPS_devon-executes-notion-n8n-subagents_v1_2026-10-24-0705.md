# DEVON executes: Notion, n8n and subagents in the Agent Runtime

Ruled by Tee 2026-10-24, on three cards in one session. First card: "Give
DEVON direct access", first action "N8N & Notion". Second card, after the
session corrected its own first card: "Both and he needs to be able code and do
everything", and "Create Inbox and Tasks". Then, in chat, "He needs to be able
to write code" and "He needs to be able to call subagents too", and a third
card: code through the Claude Agent SDK on a VPS of DEVON's own, and subagents "Both", run
and return in the runtime plus worker subagents inside code jobs.

## What the first card got wrong, and what changed the build

The first card said that after an approval nothing runs the effect. That was
true of one route, `POST /devon/approvals/decide` at `app/api/v1/devon.py:478`,
and false of DEVON as a whole. Reading further found two execution lanes that
already existed:

- The n8n lane. 48 DEVON workflows on the n8n VPS, the Face to the Action Router
  (`NYcEp03Oqlvq86Mb`, webhook `devon-action`) to executors for `drive.draft`,
  `airtable.row` and `zapier.mcp`. The Face last ran at 2026-10-24T01:05:28Z,
  execution 4210. Both figures were read live through the n8n API by this
  session and are reproducible only with n8n access, not from this repository.
- The Python Agent Runtime. `app/services/agent_tasks.py::build_tool_registry`
  registers GitHub (read, branch, write file, open and merge a pull request),
  operator commands, browser, EditForge, vision and the Council, each behind
  the same approval binding in `services/agent_runtime/governance.py`.

So DEVON could already write code through the runtime. What neither lane
reached was Notion, and the runtime could not hand a job to n8n. This arc adds
those two adapters to the runtime, beside the GitHub one, which is direct
access without a second approval system. `services/devon` stays network free
and its invariant is untouched: the adapters live in `services/notion` and
`services/n8n_actions`, the same way `services/github` does.

The second card's "Create Inbox and Tasks" was answered by not creating them.
A search of the workspace found `Inbox, Notes and Ideas` (`4deffb01`), `Tasks`
(`ab006f1a`) and `Projects and Goals` (`78a7c25c`) already under DEVON Second
Brain. The code's "is missing" labels were stale, and the card had repeated
them as fact. A second Inbox would have split captures across two databases.

## What was built

| Piece | Where |
|---|---|
| Notion database map, schemas read 2026-10-24 | `services/devon/vault.py::NOTION_DATABASES`, soul copy byte identical |
| Notion client, create then read back | `services/notion/client.py` |
| Tools `notion.create_page` (WRITE), `notion.read_page` (READ) | `services/notion/agent_adapter.py` |
| Action Router client, v1 AUTHORIZED envelope | `services/n8n_actions/client.py` |
| Tool `n8n.dispatch` (WRITE) | `services/n8n_actions/agent_adapter.py` |
| Tool `runtime.call_subagent` (WRITE) | `services/agent_runtime/expansion_tools.py` |
| `stop_before_approval` on the run loop | `services/agent_runtime/runtime.py`, `app/services/agent_tasks.py` |
| Registry wiring | `app/services/agent_tasks.py` |
| Capture and read replies no longer call the three databases missing | `services/devon/commands.py`, `services/devon/assistant.py`, soul copies byte identical |
| Code worker for the VPS, Claude Agent SDK, draft pull request out | `deploy/code-worker` (`worker.py`, `server.py`, `DEPLOY.md`, service unit) |
| Tools `code.task` (HIGH_IMPACT), `code.status` (READ) | `services/code_worker` |
| Worker tests added to the standalone CI job | `.github/workflows/ci.yml`, `CLAUDE.md` |
| Hermes record, 21 tools to 27 | `docs/devon/hermes-surface.json`, `SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md` |
| Tests, 52 | `test_devon_notion_agent_adapter.py`, `test_devon_n8n_action_adapter.py`, `test_devon_call_subagent.py`, `test_code_worker.py`, `test_devon_code_worker_adapter.py` |

Properties of both adapters:

- A write runs only on an approved card bound to its exact arguments, and the
  approval is spent before the call, so one ruling performs one effect.
- Everything cheap and refusable is checked before the approval is spent: the
  database, every property and select option, the date, the action name, the
  payload, whether the credential is set. A typo costs a correction, not a
  ruling.
- A Notion create is read back and must sit under the database it was sent to
  before it is reported. A router answer is reported done only when an executor
  moved the envelope past AUTHORIZED; a refusal, an empty answer and an HTTP
  error each come back as a failure with the reason.
- `ACTIONS` is pinned to the router's `TARGETS` table, ceiling for ceiling, by
  reading the router source in a test.

## Subagents

`runtime.call_subagent` spawns the same durable child `runtime.spawn_subagent`
writes, plans it, and runs it inside the parent's step. The child runs its read
steps and stops BEFORE any step that would raise a card. That is deliberate. A
card's single-use token is returned only to whoever ran the step that raised
it, and from inside a tool call that is the parent's observation log, where a
token would either be stored in plain text or lost with the card unapprovable.
So a child that reaches a write comes back to the parent as a failure naming the
child task, and Tee runs that child directly, which raises its card the normal
way. Only a completed child is a success. Chains stop at three deep. Each call
is itself a WRITE and costs a card, which is the real brake on a runaway plan.

Three of the four tests were checked by breaking the guard they cover and
watching them fail: running the child without `stop_before_approval`, removing
the depth check, and treating every child state as success.

## The code worker

`deploy/code-worker` runs one approved job: a fresh clone, a new branch
`devon/code-<job>`, the Claude Agent SDK with a test writer and a reviewer as
subagents under a turn and dollar limit, then the worker runs the job's test
command itself and opens a DRAFT pull request carrying the result and the cost.
It never merges and never pushes to the base ref. It runs on DEVON's own box,
ruled the same day, not on the n8n VPS.

The GitHub token: blanked in the agent's environment, handed to git per command
as a header and never written to any config, and the push is made from a second
pristine clone with hooks and local config disabled. The last part exists
because the critic reproduced the hole it closes: an agent with Write in its
clone could plant a `pre-push` hook that reads the token out of
`GIT_CONFIG_PARAMETERS`, or an `insteadOf` rewrite that sends the authed push to
another host. What stays open, stated plainly: the agent's shell runs as the
same Unix user as the worker and can read the worker's environment through
/proc. The limits are the token's own scope, the per job `max_budget_usd`, the
Console spend limit on `ANTHROPIC_API_KEY`, and allowlisting only trusted
repositories. A separate user for the agent is stage two of the box.

Other critic findings fixed the same day: a job left mid-flight by a crashed
worker is closed as failed on the next start instead of reading as running
forever; a test command that hangs is a test result and still gets its draft,
titled `TESTS TIMED OUT`; an agent that ended in error or at its limit lands as
`done_agent_error` with the subtype in the title; a push whose pull request then
fails to open is recorded as `pushed_pr_failed` naming the branch; git and test
subprocesses no longer block the server's event loop; the branch carries the
job id verbatim; and `runtime.call_subagent` no longer lets a model inherit
`parent_task_id` and shorten the depth count.

The worker tests drive real git against a local bare remote with a fake agent
and a recorded GitHub. Guards broken on purpose and caught by a test: pushing to
main instead of the job branch, removing the token scrub, trusting the agent's
word instead of running the tests, and a planted pre-push hook in the agent's
clone.

## Not proven

No call has reached the live Notion API or the live Action Router from this
code. Every test uses a mock transport. Four things stand between this and a
live receipt, and all four are Tee's:

1. Set `DEVON_NOTION_TOKEN` on the API deployment, from a Notion internal
   integration.
2. Share the three databases with that integration. An integration that
   authenticates still sees nothing until each is shared, which is the trap
   `vault.NOTION["known_trap"]` records.
3. Set `DEVON_N8N_ACTION_KEY` to the router's `x-devon-key` value. That key is
   approval equivalent for a write, so it belongs only on the deployment.
4. Stand up the code worker on DEVON's own box per `deploy/code-worker/DEPLOY.md`
   and set `DEVON_CODE_WORKER_URL`, `DEVON_CODE_WORKER_KEY` and
   `DEVON_CODE_WORKER_REPOS` on the API deployment.

The proof after that is one approved `notion.create_page` into the Inbox with
the page id in the receipt, and one approved `n8n.dispatch` of `spine.echo`,
which writes nothing.

Unverified: whether the router's entry reconcile step accepts an envelope that
did not come from its own ledger. The router source reads `Reconcile Entry
Envelope` before dispatch and that node's body is not in this repository.

## Next arcs

- DEVON's own computer, ruled 2026-10-24: its own box, separate from the n8n
  VPS, in two stages. First a persistent workspace with a shell and files,
  which is where the code worker above and the existing Operator Bridge run.
  Then a desktop driven by Claude computer use on the same box.
- A Notion executor behind the Action Router, so the n8n lane reaches Notion
  too. Needs a Notion credential in n8n and a publish.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_devon-executes-notion-n8n-subagents_v1_2026-10-24-0705.md
DATE: 2026-10-24
DECISIONS: DEVON executes directly; both lanes; Notion and n8n first; existing Inbox, Tasks and Projects databases used rather than duplicated; code through the Agent SDK on DEVON's own box; subagents both in the runtime and inside code jobs.
FINDINGS: The runtime already executed GitHub, operator and browser effects; the stale missing labels on the Notion databases; the first card understated what existed.
OPEN: DEVON_NOTION_TOKEN, database sharing, DEVON_N8N_ACTION_KEY, DEVON's own box and the code worker on it, the desktop stage, first live receipts, n8n Notion executor.
STATUS: built and tested against mock transports; live proof waits on the settings above and the worker box.
