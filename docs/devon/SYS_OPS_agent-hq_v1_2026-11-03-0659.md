# Agent HQ: a local 3D office for the Claude Code sessions on one machine

Written 2026-11-03. It records the build of `tools/agent_hq` on branch
`claude/agent-hq`, PR #480, and what was measured before it was handed back.

## The ask

Tee asked for a live 3D office for his Claude Code bots that runs on his own
machine with nothing leaving it: a roster of every bot with job, model and
team, hooks in `~/.claude/settings.json` that append one JSON line per event
to `~/.agent-hq/events.jsonl`, token counts per bot read from the transcripts
the hooks name, one dependency free server on 127.0.0.1:7777 serving the page
and `/state`, a Three.js tower with one floor per team and a desk and robot
per bot, a header with a clock and per status counts, a "Waiting on me" panel
and a "Finished today" list, a three second refresh, one command to start it,
and a test by starting and stopping one session.

## What was built

One stdlib Python script, `hq.py`, is the server, the CLI, the installer, the
roster scanner and the state builder. One tiny script, `hook.py`, is the hook.
`index.html` and `app.js` are the office, on Three.js 0.187.0 vendored from
the npm tarball and pinned by `MANIFEST.sha256`. `test_agent_hq.py` holds 54
offline tests and runs in the standalone job. The first `up` shows the roster
and asks for an OK before saving it; hooks are merged beside existing ones,
through a symlink, keeping the file mode, and reversed by `uninstall`.

Status rules per session: waiting is a Notification since the last prompt that
nothing has answered; stuck is a turn with no transcript line for ten minutes,
a subagent writing under the session counting as a line; resting is stopped,
ended, no prompt yet, or quiet for a day. Events are ordered as written, so a
Stop and a prompt in the same second sort correctly. Tokens are summed once
per message id and bucketed by local day.

## What was measured

A real nested Claude session ran in the cloud container with the hooks loaded
from a scratch settings file and wrote SessionStart, UserPromptSubmit, Stop
with the summary "pong" and SessionEnd to the events file; `/state` then
showed the lane with 121,742 tokens for the day and the Stop in the finished
list. The page rendered in headless Chromium with zero console errors after
every round, in the real state and in a nine bot demo carrying all four
statuses. One test runs the one command as a process, fires the exact
installed hook line through `/bin/sh` for four events and reads the result
back from `/state`. The full API suite passed on the first commit, 9620
passed and 2 skipped, and only the tool's own files changed after it.

This container's own `~/.claude/settings.json` was not modified: the auto mode
classifier refused that as self modification, and it is not Tee's machine. The
installer ran against a scratch config directory instead.

## The critic rounds

Three rounds, every finding checked by an independent agent in its own
worktree. Round one, six lenses over `594401c`: 40 findings verified, 38
confirmed, 1 refuted, 1 unverified; answered in `c28dbe1`. Round two re-checked
all 38 (32 fixed, 5 documented choices, 1 still present) and swept the diff,
confirming 17 more; answered in `b57bff1`. Round three re-checked those 18
(15 fixed, 2 documented choices, 1 still present); the one left, an Agent call
whose result line never lands keeping its bot lit after the session stopped,
is answered in `96d7de2`, with one independent verifier on that commit.

The documented choices, each stated in the README: an idle_prompt
notification after a Stop reads as resting, a session quiet for a day reads
as resting rather than stuck forever, SubagentStop is installed for everyone,
the hook stores a 200 character summary and the transcript path, subagent
tokens move to the agent bot when SubagentStop names it, and `/state` answers
any process on the machine, as every loopback server does.

## What is Tee's

The roster list for his own machine, asked on a card. Whether an idle prompt
after a Stop should count as waiting on him. Running the one command on his
machine and watching the first desk light up. The merge, under the standing
grant, once CI is green on the head.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_agent-hq_v1_2026-11-03-0659.md
DATE: 2026-11-03
DECISIONS: Built as a tool in this repository rather than a one off in the container, since the container's home directory is ephemeral and the installer must run on Tee's machine. Three.js vendored from the npm tarball under a sha256 manifest rather than loaded from a CDN. The first roster is shown and confirmed before it is saved. Judgment calls on the status rules are documented rather than literal and put to Tee.
FINDINGS: Three critic rounds confirmed 38, then 17, then 1 findings against successive commits, each answered in the next commit; the medium ones were a parent reading stuck while its subagent worked, agent bots never reading working, same second Stop and prompt ties, rescans retiring live folders, a settings symlink replaced by a plain file, lost file modes, a whole hook group dropped on uninstall, an unbounded first read, agents matched by a rewritable display name, ids that shifted on a duplicate name, and a broken roster.json flattened without backup. A real nested session fired all four hooks and reached the page; the page rendered clean in headless Chromium after every round.
OPEN: Tee's OK on the roster for his machine, the idle_prompt ruling, running the one command on his machine, the merge of PR #480 once CI is green, and the verifier's read of 96d7de2.
STATUS: Built, tested offline and with one real session, three critic rounds closed, PR #480 open as a draft with CI running on 96d7de2.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
