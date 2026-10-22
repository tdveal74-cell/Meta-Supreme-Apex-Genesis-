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
that list for servers containing "graphify" and askQuestion for servers
containing "blotato-help". `SERVER_ALIASES` maps the Graphify UUID to
"graphify" before any rule runs. remember, set_workspace and any tool Graphify
adds later stay gated, under every name including the UUID.

The stand-in verbs in `test_gate_ledger.py` are replaced by the 26 real tool
names, each pinned as a read or a write, under three server spellings and the
UUID. Further tests pin that no other named server gains a Graphify read, that
askQuestion is refused on Blotato itself and on n8n, that blotato-help
sendFeedback stays gated, and that Vertiso's remember is not swept in.

## Measured

| check | result |
|---|---|
| `test_gate_ledger.py` on the fix | 663 passed |
| the same tests against the old gate | 62 failed, 601 passed |
| standalone job, the 46 files listed in CLAUDE.md | 1694 passed |
| `ruff check .` | clean |

The 62 are the 19 refused reads under three spellings, the catalogue test, the
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

## Open

- A new connector UUID is covered only once it is added to `SERVER_ALIASES`.
  Graphify's is the only one listed.
- Vertiso Memory's remember is ungated under its UUID. That is a separate
  ruling and was not taken here.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_graphify-reads-through-the-gate_v1_2026-10-22-2225
DATE: 2026-10-22
DECISIONS: Tee ruled on a card on 2026-10-22 to commit the Graphify read fix to the outward gate, to pass blotato-help askQuestion on that server only, and to map known connector UUIDs to server names rather than gate by the remember suffix.
FINDINGS: at 05e59f4 the gate refused 21 of Graphify's 26 tools, reads included, because READ_VERB anchors on the first word; under the live connector UUID 89245824 it gated none, so remember and set_workspace ran unchecked; both reproduced by independent verifiers. The fix passes 663 gate tests and the old gate fails 62 of them; the standalone job passes 1694. Graphify's index missed every importlib and settings edge to the hook and conflated subprocess.run with the hook's run().
OPEN: the live hook is measured in the first session after merge; new connector UUIDs need listing in SERVER_ALIASES; Vertiso Memory remember is ungated under its UUID and is Tee's to rule on.
STATUS: committed on claude/graphify-read-gate, PR to follow, merge under the standing approval once checks pass.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
