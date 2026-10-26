# Graphify reads through the outward gate

Status record, 2026-10-22. Branch `claude/graphify-read-gate`, commit d3c08a9
on top of main 05e59f4.

## What was wrong

Tee ruled on 2026-10-17 that Graphify's non-read tools need a human signal and
its reads do not. The gate in `.claude/hooks/gate_ledger.py` carried that
ruling as `"graphify"` in `NAMED_SERVERS`, and on a named server a tool passes
only when `READ_VERB` matches the start of its name. Graphify's tools mostly
start "graphify_" or with a noun, so 21 of its 26 tools were refused whenever
Tee had been quiet for 30 minutes, reads included: graphify_find,
graphify_callers, graph_stats, recall and the rest. Only list_workspaces,
list_repositories, query_graph, search and fetch passed.

The tests had not caught it. They pinned the rule with stand-in verbs written
before anyone could read the tool list (search_symbols, find_callers,
get_dependencies, list_tests), and every one of them began with a read verb.

The second defect ran the other way. In this cloud session the Graphify
connector arrives under the UUID `89245824-e0dd-4d6f-94dc-d0712a46ef78`, not
under a name. No rule matched the UUID, so every Graphify tool passed here,
including its two writes, remember and set_workspace. The gate covered
Graphify under the names nobody was using and missed it under the one that was
live.

Both were reproduced by independent verifiers in their own worktrees at
05e59f4 before anything was changed. The first verifier returned the 21 and 5
split exactly, identical under graphify, Graphify and claude_ai_Graphify. The
second returned `(None, False)` for remember and set_workspace under the UUID
and confirmed that Vertiso Memory, connector `43100b80-...`, also exposes a
tool named remember.

## Rulings

Tee ruled three things on one card on 2026-10-22.

1. Commit the read fix. The auto mode classifier refused the first commit as
   self-modification of the gate that guards the session. That refusal was
   correct and was not routed around; the commit went in after his answer.
2. blotato-help askQuestion passes, on that server only. It answers a question
   from Blotato's docs. `"ask"` was not added to `READ_VERB`.
3. Known connector UUIDs are mapped to the server name the rules use.
   Gating by the suffix remember was offered and not chosen, because it would
   also gate Vertiso Memory.

## What changed

`GRAPHIFY_READS` lists the 24 read tools by exact name. `SERVER_READS` holds
that list for the graphify server and askQuestion for blotato-help, each
matched on the exact server name, its `claude_ai_` connector form or a
`plugin_<plugin>_<name>` form. `SERVER_ALIASES` maps the Graphify UUID to
"graphify" before any rule runs.

The first version matched by substring, the way `NAMED_SERVERS` does. The
fresh critic found that `mcp__graphify-evil__recall` and
`mcp__blotato-help-x__askQuestion` passed, scored security 4, and the match was
tightened before merge. A substring is safe on `NAMED_SERVERS` because it
tightens; it is not safe on a list that loosens. Four lookalike tests fail
against the substring version and pass on the exact one. remember, set_workspace and any tool Graphify
adds later stay gated, under every name including the UUID.

The stand-in verbs in `test_gate_ledger.py` are replaced by the 26 real tool
names, each pinned as a read or a write, under three server spellings and the
UUID. Further tests pin that no other named server gains a Graphify read, that
askQuestion is refused on Blotato itself and on n8n, that blotato-help
sendFeedback stays gated, and that Vertiso's remember is not swept in.

## Measured

| check | result |
|---|---|
| `test_gate_ledger.py` and `test_ledger_receipt.py` on the final fix | 684 passed |
| the read and UUID tests against the 05e59f4 gate | 62 failed |
| the lookalike tests against the substring version | 4 failed |
| standalone job, the 46 files listed in CLAUDE.md | 1694 passed |
| `ruff check .` | clean |

Against 05e59f4 the 62 are the 19 refused reads under three spellings, the catalogue test, the
three UUID writes and askQuestion. Every new behaviour turns a test red when
the fix is removed.

Unverified: the live hook. Settings and hooks load at session start, so this
session still runs the 05e59f4 gate, and the first session after the merge is
where the change is measured in use.

## What the graph could and could not see

Re-measured in this session against Graphify's index of this repository,
built at commit 05e59f4 at 2026-10-22T21:58:15Z and 26 minutes old when read.

- `graphify_callers("run")` returned 0 callers.
- `graphify_node` on `claude_hooks_gate_ledger_run` resolved exactly and
  returned two callers. `main()` at L988 is right. `_lookup_branch()` at L403
  is wrong: that line is `subprocess.run`, conflated with the hook's own
  `run()`.
- It returned no caller from a test. `test_gate_ledger.py` and
  `test_ledger_receipt.py` both load the hook by file path through importlib,
  and `.claude/settings.json` names it in three hook commands. The graph sees
  none of those edges.
- `graphify_file_neighbors` on `.claude/hooks/gate_ledger.py` returned 54
  symbols and 0 neighbour files.

So the graph is good for finding a definition and reading its local calls. It
cannot answer "what breaks if I change this" for a file reached by importlib
or a settings string, and a caller list from it needs reading before it is
trusted.

## Open, and what became of it on 2026-10-23

Tee asked for the open items to be worked the next day, and ruled the two
that were his on one card.

- A new connector UUID was covered only once added to `SERVER_ALIASES`. Ruled:
  record, never refuse. A non-read call on a server named by a full UUID that
  `SERVER_ALIASES` does not map is now ledgered as
  `unmapped_uuid:<first eight characters>:<tool>`, ungated, and the ledger
  receipt raises an open thread naming each one to map. A read is not
  ledgered. Rules ahead of it still win, so a listed write such as
  `publish_workflow` is gated under a UUID as before. Nine of the new tests
  fail against 76e1358.
- Vertiso Memory's writes pass the gate under any name. Ruled: leave them
  ungated and close the item. They write to Tee's own memory store, which is
  outside the outward set of 2026-10-14. Under a UUID they are now ledgered by
  the rule above, never refused.
- The Codex review of PR #406 still read "Running" on 9ffe612 more than
  twelve hours after it started, with no findings. It was re-requested with
  an `@codex review` comment on the merged PR.
- The live hook, measured 2026-10-23 at 14:14Z by a scheduled check in this
  session. The gate's own `latest_signal` read the newest human signal as a
  card 50.4 minutes old, so the window was quiet. `mcp__Graphify__graph_stats`
  passed and returned the index of this repository at 6113ea2, 14549 nodes,
  with no ledger row, which is right for an untracked read. Under 05e59f4 the
  same call was refused. `mcp__Graphify__remember` was refused by the
  PreToolUse hook with "the newest human signal is a card 50 min old, outside
  the 30 min window", and the ledger recorded it as row 19, `gate-deny`, class
  `remember`, at 14:14:29Z. Nothing was written to Graphify. The connector
  arrived as `mcp__Graphify__*` in this session, so the alias was not the path
  exercised; it is held by the tests alone.
- The fresh critic on PR #409 passed it and raised one low item: `recall` and
  `hello` are not in `READ_VERB`, so on an unmapped UUID they are ledgered as
  if they wrote. Nothing is refused. Adding them to `READ_VERB` would also let
  them pass on every named server, which loosens the gate. Ruled by Tee
  2026-10-26 on a card: leave it as is. The extra rows are reads, and each
  still names the connector to map.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_graphify-reads-through-the-gate_v1_2026-10-22-2225
DATE: 2026-10-22
DECISIONS: Tee ruled on a card on 2026-10-22 to commit the Graphify read fix to the outward gate, to pass blotato-help askQuestion on that server only, and to map known connector UUIDs to server names rather than gate by the remember suffix.
FINDINGS: the fresh critic passed it with conditions at security 4 because the read list matched servers by substring; tightened to exact names before merge. At 05e59f4 the gate refused 21 of Graphify's 26 tools, reads included, because READ_VERB anchors on the first word; under the live connector UUID 89245824 it gated none, so remember and set_workspace ran unchecked; both reproduced by independent verifiers. The final fix passes 684 tests; the old gate fails 62 and the substring version 4; the standalone job passes 1694. Graphify's index missed every importlib and settings edge to the hook and conflated subprocess.run with the hook's run().
OPEN: the live hook is measured in the first session after merge; new connector UUIDs need listing in SERVER_ALIASES; Vertiso Memory remember is ungated under its UUID and is Tee's to rule on.
STATUS: committed on claude/graphify-read-gate, PR to follow, merge under the standing approval once checks pass.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
