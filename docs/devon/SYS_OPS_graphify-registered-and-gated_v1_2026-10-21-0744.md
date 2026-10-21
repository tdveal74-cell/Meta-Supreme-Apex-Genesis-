# Graphify registered at project scope and gated

Status record for PR #371, merged 2026-10-17 as `747df79`. Written 2026-10-21.

## What shipped

Graphify, a code graph MCP server at `https://api.graphify.com/mcp`, is now
in `.mcp.json` and in `enabledMcpjsonServers` in `.claude/settings.json`. Tee
first added it with `claude mcp add --scope user`, which writes to
`/root/.claude.json`. That file sits in the cloud container's home directory
and is wiped with the container, so the entry was moved into the repo, where
every session reads it.

The gate hook now names it. `"graphify"` is in `NAMED_SERVERS` in
`.claude/hooks/gate_ledger.py`, so any Graphify tool that is not a read needs a
human signal inside 30 minutes. Tee ruled it on 2026-10-17 with "Add it to the
list". `CLAUDE.md` names Graphify in the gated list.

## How it was checked

- Before anything was installed, the npm package named `graphify` turned out
  to be "RGG (Random Graph Generator)", an unrelated project last changed in
  June 2022. Nothing was installed by name.
- An unauthenticated request to the endpoint returned HTTP 401, so the server
  exists and wants a sign-in. No credential is in the repo.
- `test_gate_ledger.py` went from 488 to 504 passed. Removing the
  `"graphify"` entry turned the 8 write cases red and left the 8 read cases
  green. An independent verifier repeated that mutation in its own worktree
  and got the same result.
- The full API suite passed 4838 tests on the first commit. All six hosted
  checks passed on `106d307` before the merge.

## A wrong claim, corrected before merge

The first PR description said `blotato-help` sat outside the gate, and the
first reviewer agreed. Running `classify` showed otherwise:
`mcp__blotato-help__askQuestion` returns gated, because `NAMED_SERVERS` is
matched by substring and `blotato` is inside `blotato-help`. The verifier
confirmed it against `bfc81f6`, the main commit before this change. The
lesson: whether a server is gated is answered by running `classify`, never by
reading the list.

## Open

- Graphify still needs its OAuth sign-in. It reads "needs authentication" in
  the server list, so its tools have never loaded and its real tool names are
  unknown. The tests use stand-in verbs and pin the rule, not the catalogue.
  When the names are readable, check them against `READ_VERB`.
- `askQuestion` on `blotato-help` is a docs lookup that is refused whenever no
  human signal is fresh, because `READ_VERB` has no `ask`. That predates this
  change and is Tee's call.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: Graphify MCP registered at project scope and gated
DATE: 2026-10-21
DECISIONS: register graphify in .mcp.json and enabledMcpjsonServers rather than user scope, which the container wipes; add graphify to NAMED_SERVERS so its non-read tools need a human signal (Tee, 2026-10-17); install no package by name
FINDINGS: npm package graphify is an unrelated 2022 random graph generator; endpoint answers 401 until sign-in; blotato-help was already gated by substring match, so the first PR description was wrong and was corrected after classify was run and an independent verifier confirmed it
OPEN: Graphify OAuth sign-in (Tee); real tool names unread, so check them against READ_VERB once visible; whether READ_VERB should gain ask for blotato-help askQuestion (Tee)
STATUS: merged 2026-10-17 as 747df79 with six hosted checks green and an independent verifier on both commits
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
