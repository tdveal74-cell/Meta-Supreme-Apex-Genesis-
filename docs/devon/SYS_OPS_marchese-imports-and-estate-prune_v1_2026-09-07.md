---
title: The three Marchese imports, built; and the estate pruned from 64 workflows to 53
type: SYS_OPS
version: 1
date: 2026-09-07
area: Systems
status: two-conventions-written-eleven-archived-six-blocked-on-mcp-access
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: a993cec
branch: claude/video-analysis-incorporation-9h6rtc
supersedes: none
---

# The three Marchese imports, and the prune

Tee ruled "go" on all three imports proposed in
`SYS_OPS_austin-marchese-automation-framework-incorporation_v1_2026-09-07.md`.

## Import 1 and 2: written into the house conventions

Both are now in `.claude/skills/devon-learning-lane/references/n8n-conventions.md`,
which `CLAUDE.md` says applies estate wide and not only to the learning lane.

**Say what you did, with counts.** A terminal notification never says only that
it ran. It names what it touched, with numbers, and where the numbers came
from. Not "sweep complete" but "read 128 ledger rows, 3 non-terminal past 96h,
3 cancelled, 0 refused". The number is the point: an operator who sees
"1 of 1 emails" on a day they know they got forty has caught a broken
automation in one glance, and no alerting rule would have fired, because
nothing failed. The quiet path is not exempt; a zero item run reports
"0 of 128 matched" rather than silence, because silence and a broken read look
identical.

This is the first law of `CLAUDE.md` pointed at machines instead of at a
session. That law governs what a session may assert. Nothing governed what a
workflow may assert, and the estate has already paid for the gap: the Build 12
envelope read `not_captured` forever and the Face, the Heartbeat and the
operational report all repeated it.

**Break before you spend.** A workflow that depends on a credential, a table, a
host or a connector checks they answer BEFORE doing any work, and refuses with
a message naming what is missing. The estate's two error handlers are both
Error Triggers, so by construction they fire on a crash that already happened.
Nothing refused a doomed run before it started consuming executions. This is a
burn lever as much as a correctness one: at 264 executions a day against a cap
the cutover runbook expects to hit between 2026-09-17 and 2026-09-25, a lane
that discovers at node 30 that its credential died has spent thirty nodes to
learn what node 1 could have told it.

Written as conventions rather than applied to all thirteen scheduled lanes at
once, deliberately. A convention binds every future workflow including ones
nobody has thought of; thirteen individual edits bind thirteen. Applying them
lane by lane is now ordinary work with a rule to point at.

## Import 3: the prune, done

His filter: an automation either removes a constraint or increases the value
produced. If it does neither, do not build it, and because the world is
dynamic, prune what stopped earning its place.

Applied to all 64 live workflows, read from the instance rather than the
census. Seventeen failed the filter. Eleven are archived; six could not be
touched and are listed below.

**Archived, eleven.** All were inactive, and none was referenced as a
sub-workflow target or as an error workflow by anything active, checked before
archiving:

| Workflow | Id | Why |
|---|---|---|
| Pill v16 Splice | `Rr4Agd7UtdUbH9Nf` | self described one-shot, ran |
| Naming v4 In Place | `EuPHrxmyQ69Mha6r` | one-shot doctrine migration, ran |
| Naming v4 Capability Clause | `mMaWH5T2sXovJpNC` | same |
| Filing Laws v2 | `tx0QTS8DlFJ3EH3Q` | same |
| Filing Laws v3 Merge | `USU9PjlT7M6ocgkD` | same |
| Directory v6 Correction | `1Udz2KOjV4omNjax` | same |
| DEVON Soul Index Setup (one-shot) | `vYr35jqNNaAztGhQ` | its own description says unpublished after its single run |
| DEVON Build 08 Credential Probe (throwaway) | `pm5hoO4eFpGhlAb4` | self labelled throwaway |
| Cerebras Smoke Test | `BSMAEOeWciqKbaFs` | self labelled throwaway test |
| DT Bootstrap Tables (TQO Migration S1a) | `svqHaaMzZPeGee8e` | created the tables, idempotent, spent |
| S5 Seed: TQO Idea Row | `be5rCRZ1ktLnmwI4` | seed row, spent |

Verified by re-reading the instance: 64 workflows before, 53 after. Archive is
reversible in n8n, so any of these comes back with unarchive.

**Blocked, six.** The legacy TQO graveyard, every one superseded by V5 and
inactive:

`TQO - ORCHESTRATOR` `ljrWDpRVgK8gxQwH`, `TQO FINAL V1` `80Um0VPtbVQIO47n`,
`TQO FINAL V1` `o09uEM6O2JedxpF5`, `TQO FINAL V1 FIXED 2` `hnVhgvRJOLVPfXHI`,
`TQO FINAL V2` `k5B5dcewspDpNSHO`, `TQO FINAL V4` `WDFEnVIziUmGA3Pj`.

All six carry `availableInMCP: false`, so the API refuses to archive them:
"Workflow is not available in MCP. Enable MCP access from the workflow card."
That flag was in the listing and was read past on the first attempt. Tee can
archive them from the n8n UI, or enable MCP access and they become one call
each. There is no V3; the sequence really does skip it.

**Kept despite being inactive.** These pass the filter as constraint driven
tools that are meant to sit idle until invoked, which is not the same as dead:
`DEVON Purge List (manual)`, `DEVON Vault Comparison`, `DEVON Master Index`
(which carries a "never change it back to a create operation" warning worth
preserving), `DEVON End to End Watch Harness`, `DEVON Learning Lane Table
Reader`, `DEVON Capture Hook`, and `TQO FINAL V5`, held dark on purpose.

## A compliance finding the prune surfaced

`OS 29 Platform Policy Sensor` (`7WyIarNoJa2irx2r`) is INACTIVE. It is a daily
sweep of watched platform policy pages that flags changes material to TQO, TSWS
or NCO Forge.

Tee's standing rules say there is no exception path for compliance items, and
name platform policy first. A platform policy sensor sitting switched off is
that exception in practice. It is not pruned; the recommendation is the
opposite, that it should be running. Activating it is Tee's call because it
adds executions against a cap the estate is already walking toward.

## What was not done

The Gumroad payload guard, still owed from
`SYS_OPS_tqo-v5-webhook-auth_v1_2026-09-07.md`, is not in this document.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_marchese-imports-and-estate-prune_v1_2026-09-07
DATE: 2026-09-07
DECISIONS: Tee ruled go on all three imports
FINDINGS: 17 of 64 workflows failed the constraint versus enhancement filter; 11 archived, 6 blocked by availableInMCP false; estate 64 to 53
OPEN: OS 29 Platform Policy Sensor is inactive and is a compliance item by Tee's own standing rules; the six TQO legacy versions need archiving from the UI; the Gumroad payload guard
STATUS: two conventions written estate wide, prune executed and verified
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
