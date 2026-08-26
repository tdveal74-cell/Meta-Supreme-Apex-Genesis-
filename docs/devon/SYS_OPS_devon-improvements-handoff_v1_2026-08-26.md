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

### 2. Council for gated jobs (repo work)

There is no "level 3" and no council trace string in this repo; the real
parking spot is `services/agent_runtime/runtime.py` `run_next`
(approval_required branch, message "human ruling required"). A full 9-seat
council already exists (`services/agents/registry.py`,
`services/intelligence/executive_controller.py` `ExecutiveController.run`).

Smallest sound change: register a `council.consult` tool with
`risk=ToolRisk.READ` in `build_tool_registry()`
(`app/services/agent_tasks.py` ~line 76), a thin adapter over
`ExecutiveController.run` modeled on `services/browser/agent_adapter.py`,
returning SynthesisResult fields as ToolResult metadata. Then extend the
`what_happens` text for effectful steps to carry the latest council
observation, or the words "no council consultation is on record for this
task" - appended BEFORE the approval marker is computed, so
`services/agent_runtime/governance.py` binding checks stay green
(`test_devon_shared_approvals.py`). No new approval-level taxonomy.

### 3. First genuine PROMOTE (live lane)

Needs two or more real same-theme jobs COMPLETED through the ledger so the
gate sees independent sources with a clear receipt. Egress from build
containers to the n8n host is proxy-blocked; drive the ledger via the n8n MCP
(`execute_workflow` on the ledger webhook workflow is not possible - webhook
workflows need real POSTs - so either run real runtime jobs against the
deployed API or have the feeder pick up jobs Tee runs). Every commit still
goes through an approval card; slow down on the tap (approve and reject sit
adjacent).

### 4. Upstream webhook auth flip (TEE, by hand, 2 minutes)

Workflow `VznESplSFCs8ldph` (webhook devon-build12-upstream) is deliberately
open; the feeder already sends x-devon-key, so flipping costs nothing. In the
n8n editor: open the workflow, select the Webhook node, set Authentication to
Header Auth, pick credential "Devon Capture Key", save, publish. Then update
the AUTH note in `services/devon/vault.py` WEBHOOKS and
`.claude/skills/devon-learning-lane/references/ids-and-contracts.md` in the
same change. Verify: next feeder digest still shows fed jobs (it will), and an
anonymous curl now gets 403.

### 5. Ledger Janitor - PUBLISHED 2026-08-26T01:38Z

Workflow `HKNEDVy7PUKPtsrN` (DEVON - Ledger Janitor) is live: daily 02:30
UTC, sweeps jobs non-terminal past 96h to CANCELLED THROUGH the guarded
ledger webhook (credential Devon Capture Key attached), VERIFYING legally
two-steps FAILED then CANCELLED, envelope history preserved plus a janitor
trace note, digest email only when it acted, Error Alarm + 300s timeout set.
Dry-tested (execution 3581) before publish. Registered in
`services/devon/vault.py` WORKFLOWS (+ deploy mirror + skill tables +
runbook) in the same change. Remaining verification: the first live sweep
(02:30 UTC) should clear the eight stale Aug-24 E2E jobs and the
heartbeat's stuck_jobs alert should drain on the following pulse; a session
check-in is armed for 02:54 UTC to confirm both.

### 6. Weekly table backup by email (n8n, additive)

Weekly schedule; read devon_state_ledger, devon_build12_feed_log,
devon_soul_commit_log, devon_heartbeat_log; convert each to CSV (Convert to
File node, not hand-rolled Buffer code); merge binaries onto one item; one
Gmail with four attachments. approval_queue is EXCLUDED on purpose: its rows
carry plaintext decision tokens, and mailing them would let inbox access
approve soul writes. Document the exclusion in the sticky and the skill.
Register in vault.py in the same change as publish.

### 7. Build 14: reflection to intent (design constraint fixed)

The reflection may WANT things but never DO them: its recommendations become
approval cards (POST devon-approve-request), and only an approved card may
become a ledger job. Autonomy through the gates, never around them
(heartbeat.md design rules). Build only after items 1-6; the heartbeat needs
some track record first, and the first reflections are already producing the
raw material.

## Session receipts

Build 13 gauntlet and fixes: session of 2026-08-25/26 (this doc's commit).
Gauntlet findings live in the merged heartbeat.md; the queue two-tap flow,
committer v2 semantics, and REVERTED procedure are already in
`references/ids-and-contracts.md` and `references/runbook.md`.
