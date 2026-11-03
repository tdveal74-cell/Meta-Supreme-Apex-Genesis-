# Agent HQ: the first run on the VPS, watched from the iPhone

Written 2026-11-03. It closes the open item in
`SYS_OPS_agent-hq_v1_2026-11-03-0659.md`, running the one command on Tee's
own host and watching the first desk light up. PR #480 had merged as
`24753df` earlier the same day.

## Where it ran

Tee has no Mac and works from an iPhone, so the host was found with one read
only diagnostic pasted into Termius. It answered: `srv1936199`, Ubuntu 24.04.4
LTS, logged in as root, Python 3.12.3 and git installed, no copy of this
repository, and project folders already under `/root/.claude/projects`, so
Claude Code had run there before. That is the VPS that runs n8n, not a
laptop. Agent HQ there sees the sessions that run there, and none that run in
the cloud, this one included.

Tee ruled on a card, before the run, that the phone reaches the page through
a Termius local port forward, with no change to the server: it stays on
127.0.0.1, and the phone's own 127.0.0.1:7777 is mapped to the VPS's over
SSH, so the page is up only while that SSH session is. He ruled on the same
card that the DEVON filing waits for the first run, which is this doc.

## The run

The repository, which is public, was cloned to
`/opt/Meta-Supreme-Apex-Genesis-` at `22f249c`, the head of main at that
minute. `python3 tools/agent_hq/hq.py up` printed the roster, eight bots: the
three workflow agents the repository carries, `scanner`, `verifier` and
`editor`, and five session lanes read from the transcripts' own `cwd` field,
`/opt/devon/quality90-ai-review`, its `work` subfolder,
`/opt/Meta-Supreme-Apex-Genesis-`, `/root` and `/tmp`, sorted onto the
Research and Ops floors. Tee answered `y`. It wrote
`/root/.agent-hq/roster.json`, added the six hooks to
`/root/.claude/settings.json` after copying it to
`settings.json.agent-hq-backup-20261103-163610`, copied the seven files into
`/root/.agent-hq`, and printed `Agent HQ  http://127.0.0.1:7777` at 16:36
UTC. The server runs in the foreground of that Termius tab and stops with it.

One Termius rule, type Local, host EditForge VPS, local port 7777 to
127.0.0.1 port 7777, and Safari on the phone opened the page. Tee's word:
"It opened". In a second tab he ran `claude` in `/root`, typed one prompt,
"Run ls here and tell me what you see.", and watched the root desk on the Ops
floor. His word: "It worked". Nothing here moved to done on this session's
say so; he watched it.

## What the events file shows

Read back by one paste after the session, `/root/.agent-hq/events.jsonl` held
five rows, every one for the bot `root`, in this order: SessionStart,
UserPromptSubmit, Stop, SubagentStop, Notification of type `idle_prompt`.
Five of the six installed hooks fired on one short session. SessionEnd is
absent, and the paste cannot say why: the session may still have been open
when the file was read, or `/exit` was never typed. It is listed under OPEN,
not explained. The idle_prompt after the Stop is the case Tee ruled on
2026-11-03, read as resting, so the desk went quiet, not amber.

The roster line `/opt/devon/quality90-ai-review` was graded before this doc
was written, because the session folder name `-opt-devon-quality90-ai-review`
could also spell `/opt/devon-quality90-ai-review`. Not a finding: `hq.py`
reads the cwd from the newest transcripts in each folder, their own `cwd`
field, and never decodes the folder name.

## A lesson for the paste loop

The first diagnostic was handed over as six lines, one command per line.
Termius on the iPhone pasted it with a trailing backslash on every line, so
the shell ran the whole block as one `echo` and the success line never
printed. The same commands joined with `;` on one line ran cleanly, and so
did every later step. The paste-loop skill now says so, measured on this run.

## What is Tee's

Two things wait on him, each on a card: whether Agent HQ on the VPS becomes a
systemd unit so it outlives the Termius tab, and whether the Context Pill gets
a line for it, since a host now carries hooks and a server that no standing
document names. The Thread Log page for this session is filed in Notion with
the receipt below.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_agent-hq-first-run_v1_2026-11-03-1703.md
DATE: 2026-11-03
DECISIONS: Tee ruled on a card that the phone reaches Agent HQ through a Termius local port forward, the server unchanged and loopback only, and on the same card that the DEVON filing waits for the first run. The run was done on the VPS srv1936199 as root, in /opt/Meta-Supreme-Apex-Genesis- at 22f249c, with the roster of eight bots approved by typing y.
FINDINGS: Five of the six hooks fired on one real session on the VPS, SessionStart, UserPromptSubmit, Stop, SubagentStop and an idle_prompt Notification, all for the root bot; the page opened in Safari on the iPhone through the forward and Tee watched the root desk change, his words "It opened" and "It worked". A multi line block pasted into Termius on the iPhone gains a trailing backslash per line and runs as one command, so one line joined with ; is the form that works. The roster path /opt/devon/quality90-ai-review comes from the transcripts' own cwd field, not a decode of the folder name, so it is not a finding.
OPEN: SessionEnd did not appear in the five rows and the cause is not known, the session may still have been open. The server runs in a foreground Termius tab and dies with it; a systemd unit is on a card. The Context Pill carries no line for Agent HQ on the VPS; on a card. Sessions in the cloud are invisible to this install by design.
STATUS: First run done and watched end to end by Tee on 2026-11-03; filed to the Notion Thread Log; this doc on branch claude/agent-hq for the PR.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
