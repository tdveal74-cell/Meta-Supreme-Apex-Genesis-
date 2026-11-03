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
`/root/.agent-hq`, and printed `Agent HQ  http://127.0.0.1:7777`. The backup
file name carries the stamp 20261103-163610 from the VPS's own clock, so the
install landed at 16:36 by that clock. The server runs in the foreground of
that Termius tab and stops with it.

The next two steps were handed over as instructions and came back as his
word, with no screenshot of either. The first: one Termius rule, type Local,
host EditForge VPS, local port 7777 to 127.0.0.1 port 7777, then Safari on
the phone at that address. His answer: "It opened". The second: `claude` in
`/root` in a second tab, one prompt, and the root desk on the Ops floor to
watch. His answer: "It worked". What the page showed at any moment was not
captured, and the events file below is the only artifact of that session.
Nothing here moved to done on this session's say so; the two answers are his.

## What the events file shows

Read back by one paste after the session, sent twice with the same five rows,
`/root/.agent-hq/events.jsonl` held five rows, every one for the bot `root`, in this order: SessionStart,
UserPromptSubmit, Stop, SubagentStop, Notification of type `idle_prompt`.
Five of the six installed hooks fired on one short session. SessionEnd is
absent, and the paste cannot say why: the session may still have been open
when the file was read, or `/exit` was never typed. It is listed under OPEN,
not explained. The idle_prompt after the Stop is the case Tee ruled on
2026-11-03, read as resting, so under that rule the page would show the root
desk resting and not amber; what it showed was not captured. SubagentStop
fired on a one prompt session, so Claude Code ran a subagent for that prompt;
the hook recorded it and this doc does not explain it.

The roster line `/opt/devon/quality90-ai-review` was graded before this doc
was written, because the session folder name `-opt-devon-quality90-ai-review`
could also spell `/opt/devon-quality90-ai-review`. Not a finding: `hq.py`
reads the cwd from the newest transcripts in each folder, their own `cwd`
field, and never decodes the folder name.

## A lesson for the paste loop

The first diagnostic was handed over as six lines, one command per line, at
the day's first attempt, hours before the run: the VPS login line in that
screenshot reads 08:22:38. It arrived in the shell with a trailing backslash
on five of the six lines, the shell showed its continuation prompt on each,
and the output shows the first `echo` printing the next command's words as
its own arguments, with no success line. Where the backslashes were added,
Termius, the phone's clipboard or the paste itself, was not determined. The
diagnostic rewritten as one line, the commands joined with `;` and two of
them changed in passing, ran and printed `DIAG OK`, and every later step was
handed over as one line. The paste-loop skill now says so, as what was seen
on this run.

## What is Tee's

Two things wait on him, each on a card: whether Agent HQ on the VPS becomes a
systemd unit so it outlives the Termius tab, and whether the Context Pill gets
a line for it, since a host now carries hooks and a server that no standing
document names. The Thread Log page for this session is filed in Notion with
the receipt below: https://app.notion.com/p/40d68ff50db6812fb162d30710e461b3

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_agent-hq-first-run_v1_2026-11-03-1703.md
DATE: 2026-11-03
DECISIONS: Tee ruled on a card that the phone reaches Agent HQ through a Termius local port forward, the server unchanged and loopback only, and on the same card that the DEVON filing waits for the first run. The run was done on the VPS srv1936199 as root, in /opt/Meta-Supreme-Apex-Genesis- at 22f249c, with the roster of eight bots approved by typing y.
FINDINGS: Five of the six hooks fired on one real session on the VPS, SessionStart, UserPromptSubmit, Stop, SubagentStop and an idle_prompt Notification, all for the root bot, read back from events.jsonl. The page opened in Safari on the iPhone through the forward and a session ran in /root while Tee watched the page; his words were "It opened" and "It worked", and no capture of the page exists. A six line block pasted into the shell from the iPhone arrived with a trailing backslash on five lines and ran as one command, cause not determined; the diagnostic rewritten as one line joined with ; ran. The roster path /opt/devon/quality90-ai-review comes from the transcripts' own cwd field, not a decode of the folder name, so it is not a finding.
OPEN: SessionEnd did not appear in the five rows and the cause is not known, the session may still have been open. What the page showed during the session was not captured; a screenshot of it on the next session is the cheap artifact. The server runs in a foreground Termius tab and dies with it; a systemd unit is on a card. The Context Pill carries no line for Agent HQ on the VPS; on a card. Sessions in the cloud are invisible to this install by design.
STATUS: First run done on the VPS on 2026-11-03 with Tee watching the page, his words "It opened" and "It worked"; five of six hooks fired and SessionEnd is open; filed to the Notion Thread Log, the page is linked in the body; this doc on branch claude/agent-hq in PR #483.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
