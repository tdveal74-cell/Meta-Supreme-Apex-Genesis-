# DEVON improvements handoff (v1, 2026-08-26)

Tee ordered all seven estate improvements built ("i want them all",
2026-08-26 session). Build 13 (the Heartbeat) shipped the same night. This doc
is the working map for the follow-on sessions: what is live, what is drafted,
and the smallest sound change for each remaining item, with file anchors so no
session has to re-derive them. Verify anchors against the tree before editing;
line numbers drift.

## State as of this writing

Live and proven:

- Heartbeat Pulse `dRgTNLod2s8BAcPg` published (6h beats). Survived a
  16-agent adversarial gauntlet: 13 findings, 7 confirmed, all fixed before
  publish (emailed-as-receipt semantics, timestamp-validated anchors,
  soul_overdue rename, fail-closed reflection watch). First real beat
  2026-08-26T01:14Z: row id=2 in devon_heartbeat_log, Gmail message
  1a03ba24d5f0e692 delivered, row flipped emailed=yes by Mark Emailed.
- Daily Reflection Routine `trig_01XCKFGEbojhkPRnNbMd8yCP` (11:30 UTC),
  first reflection row live.
- Spec: `.claude/skills/devon-learning-lane/references/heartbeat.md` (merged
  in PR #52, commit e9616c0).

Known open estate facts the heartbeat now alerts on daily: eight E2E watch
jobs from Aug 24 sit non-terminal in the ledger (4 EXECUTING, 4
WAITING_APPROVAL, ULIDs in the first pulse email). Item 5 clears them.

## The seven items

### 1. Recall at decision time (repo work, highest value) - DONE 2026-08-26

Shipped exactly as planned: `AgentRuntime.__init__` takes an optional
`soul: SoulLayer`; `create_task` awaits `soul_recall_payload(soul,
clean_goal)` (module function in `services/agent_runtime/runtime.py`) into
`merged_context["soul_recall"] = {context, records, errors}` before the plan
freezes. Any recall exception degrades to the payload naming the failure.
Mirrored in `DurableAgentTaskService.create_task`
(`app/services/agent_tasks.py`) behind `app.services.soul.get_soul_layer()`,
so the durable seam is inert until `SOUL_RECALL_ENABLED` +
`PINECONE_API_KEY` are set. CONTEXT-NOT-COMMAND framing and Tee-before-DEVON
ordering are pinned by tests in `test_devon_agent_runtime.py` (runtime seam,
including a RecordingPlanner proving the payload reaches the planner) and
`test_devon_soul_recall_seam.py` (durable seam, repos stubbed, no DB).
Partial recall surfaces in `errors`, never looks empty.

### 2. Council for gated jobs (repo work) - DONE 2026-08-26

Shipped as planned: `council.consult` (risk READ) registers in
`build_tool_registry()` via `CouncilCapabilityAdapter`
(`services/intelligence/council_adapter.py`), a thin adapter over
`ExecutiveController.run` returning SynthesisResult fields as ToolResult
metadata; the tool name is the shared constant `COUNCIL_TOOL_NAME` in
`services/agent_runtime/contracts.py`. Every effectful step's approval card
now carries the latest successful council observation (capped, flattened,
marker-prefix-stripped so a synthesis can never forge a binding marker) or
the exact sentence "No council consultation is on record for this task." -
appended before the marker, which stays the final element, so the
governance binding checks stay green. Tests: `test_devon_council_tool.py`
(adapter reads, card content, marker order, forged-marker stripping,
failed-consultation handling); no new approval-level taxonomy.

### 3. First genuine PROMOTE (live lane) - ASSESSED 2026-08-26, waits on real work by design

Ruled in the 2026-08-26 session (decision authority granted): the first
PROMOTE will NOT be manufactured. A synthetic pair of same-theme jobs would
make the gate PROMOTE fabricated experience into devon-subconscious - a
real write from fake evidence, defeating the word "genuine". The lane is
structurally ready and waiting on nothing but real work: as of 2026-08-26
the ledger holds only the eight stale E2E jobs (swept by the janitor, and
CANCELLED never feeds), the feed log holds two fed jobs, the commit log one
(the reverted smoke). The path stays as written: two or more real
same-theme jobs COMPLETED through the ledger (run real runtime jobs against
the deployed API, or let the feeder pick up jobs Tee runs); the feeder,
gate, and committer need no further changes. Every commit still goes
through an approval card; slow down on the tap (approve and reject sit
adjacent).

### 4. Upstream webhook auth flip - DONE 2026-08-26

Workflow `VznESplSFCs8ldph` (webhook devon-build12-upstream) now carries
Header Auth with credential "Devon Capture Key", published (active version
same as draft, updated 2026-08-26T01:56Z); the workflow also became
MCP-available the same day. The feeder was already sending x-devon-key, so
the automatic feed never noticed. AUTH notes updated in
`services/devon/vault.py` WEBHOOKS (+ mirror),
`ids-and-contracts.md`, SKILL.md, and the runbook in the same change.
Anonymous-curl verification is blocked from build containers (egress to the
n8n host is proxy-blocked); the config read-back and the next feeder digest
stand as the receipts.

### 5. Ledger Janitor - PUBLISHED 2026-08-26T01:38Z

Workflow `HKNEDVy7PUKPtsrN` (DEVON - Ledger Janitor) is live: daily 02:30
UTC, sweeps jobs non-terminal past 96h to CANCELLED THROUGH the guarded
ledger webhook (credential Devon Capture Key attached), VERIFYING legally
two-steps FAILED then CANCELLED, envelope history preserved plus a janitor
trace note, digest email only when it acted, Error Alarm + 300s timeout set.
Dry-tested (execution 3581) before publish. Registered in
`services/devon/vault.py` WORKFLOWS (+ deploy mirror + skill tables +
runbook) in the same change. First live sweep run on demand at
2026-08-26T02:21Z (execution 3592): SUCCESS, zero jobs swept, and that is
CORRECT - the eight stale E2E jobs carry updatedAt stamps of Aug 24
01:02-07:53 UTC, only 42-49h old, past the heartbeat's 24h alert threshold
but under the janitor's 96h action TTL. This doc's earlier expectation that
the first sweep would clear them was a timing error, now corrected: the
Aug 28 02:30 sweep cancels the first two (01:02 stamps), the Aug 29 sweep
the remaining six, each with a digest email. The heartbeat keeps alerting
until then - warn early, act late is the design. A session check-in is
armed for 2026-08-28T03:05Z to verify the first acting sweep.

### 6. Weekly table backup by email - PUBLISHED 2026-08-26

Workflow `qCfGZ1CwmpK9vOta` (DEVON - Weekly Table Backup) is live: Sundays
03:10 UTC, reads the four learning-lane tables, converts each to CSV
(Convert to File nodes), merges the binaries onto one item, and sends one
Gmail with four attachments. approval_queue is EXCLUDED on purpose (rows
carry plaintext decision tokens; mailing them would let inbox access
approve soul writes) - documented in the canvas sticky, vault.py, the
skill tables, and the runbook. Error Alarm + 300s timeout attached.
Dry-tested (execution 3589, Gmail pinned): all four tables read (13 rows
total), four CSVs built and merged, subject and body correct. Registered
in vault.py WORKFLOWS (+ mirror + skill tables) in the same change as
publish.

### 7. Build 14: reflection to intent (design constraint fixed) - DEFERRED BY DESIGN

The reflection may WANT things but never DO them: its recommendations become
approval cards (POST devon-approve-request), and only an approved card may
become a ledger job. Autonomy through the gates, never around them
(heartbeat.md design rules). As of 2026-08-26 items 1, 2, 4, 5, and 6 are
done and item 3 waits on real work; the remaining gate on Build 14 is its
own stated constraint - the heartbeat is one day old and needs a track
record of pulses and reflections first. Deliberately not built in the
2026-08-26 session for that reason; revisit once the reflection rows have
accumulated for a week or two.

## Session receipts

Build 13 gauntlet and fixes: session of 2026-08-25/26 (this doc's commit).
Gauntlet findings live in the merged heartbeat.md; the queue two-tap flow,
committer v2 semantics, and REVERTED procedure are already in
`references/ids-and-contracts.md` and `references/runbook.md`.
