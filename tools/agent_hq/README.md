# Agent HQ

A live 3D office for the Claude Code sessions on one machine. One floor per
team, one desk and one small robot per bot. Working robots type, resting ones
close their eyes, robots waiting on you glow amber and appear in the "Waiting
on me" panel, stuck ones turn red. Everything runs on the machine itself and
talks only to 127.0.0.1. Nothing it reads leaves that machine.

## Start it

From the repository root:

```bash
python3 tools/agent_hq/hq.py up
```

Then open http://127.0.0.1:7777. `up` does three things, each idempotent:

1. The first time, scans the roster, prints it, and asks for your OK before
   writing `~/.agent-hq/roster.json`. Pass `--yes` to skip the question;
   with no terminal (a service, a pipe) it says so and goes ahead.
2. Copies `hq.py`, `hook.py`, `index.html`, `app.js` and `vendor/` into
   `~/.agent-hq/` (created 0700), so the hooks keep working if the
   repository moves, and merges six hooks into `~/.claude/settings.json`
   (SessionStart, UserPromptSubmit, Notification, Stop, SubagentStop,
   SessionEnd). Existing hooks are kept, the file is backed up beside itself
   before the first write, a symlinked settings file is written through, and
   its mode is kept. A second run adds nothing.
3. Serves.

Sessions already running when the hooks land do not fire them until their
next event, so start a fresh session to see the first desk light up.

Afterwards `python3 ~/.agent-hq/hq.py up` works from anywhere.

## Files

| path | what |
|---|---|
| `tools/agent_hq/hq.py` | server, CLI, installer, roster scanner, state builder (stdlib only) |
| `tools/agent_hq/hook.py` | the hook: one JSON line per event, exit 0, no output |
| `tools/agent_hq/index.html`, `app.js` | the office page, Three.js, polls `/state` every 3 s |
| `tools/agent_hq/vendor/` | Three.js 0.187.0 (`three.module.js`, `three.core.js`, LICENSE) from the npm tarball, pinned by `MANIFEST.sha256` |
| `~/.agent-hq/roster.json` | every bot: name, job, model, team, kind, source |
| `~/.agent-hq/events.jsonl` | one line per hook event, 0600 |
| `test_agent_hq.py` | the offline tests, run in CI's standalone job |

## Commands

```bash
python3 tools/agent_hq/hq.py up            # roster (asks once), hooks, serve on 7777
python3 tools/agent_hq/hq.py up --yes      # same, without the question
python3 tools/agent_hq/hq.py install       # hooks and files only
python3 tools/agent_hq/hq.py roster        # rescan, print, ask, merge into roster.json
python3 tools/agent_hq/hq.py roster --json # print only
python3 tools/agent_hq/hq.py serve --port 7777
python3 tools/agent_hq/hq.py state         # /state once, as JSON, for a terminal
python3 tools/agent_hq/hq.py uninstall     # remove the six hook entries, keep the data
```

`AGENT_HQ_DIR` moves the data directory. When it is set at install time the
hook line carries that path, so the hooks work whether or not a later shell
exports it. `CLAUDE_CONFIG_DIR` moves `~/.claude`, as Claude Code does.

## The roster

`roster` reads three places and merges the result into `roster.json`:

- `~/.claude/agents/*.md`, user level agents
- `<folder>/.claude/agents/*.md` for every folder sessions have run in
- the folders themselves, read from the `cwd` field inside the transcripts
  under `~/.claude/projects/`, one "session" bot per folder, with the model
  taken from the newest assistant line; the folder `up` runs in and any
  `--cwd` count too

Team is inferred from keywords in the name and description (Visuals, Content,
Research, Ops, in that order; Ops when nothing matches). Edit `team`, `name`
or `job` in `roster.json` and a rescan keeps your edits; it refreshes `model`
and `source` from the files, keeps the previous version as
`roster.json.previous`, and refuses to touch a file it cannot parse, so a
stray comma costs a retry rather than your edits. An agent's id is its file,
so two files with one `name` are two desks. A bot the scan did not see
stays while its file or folder is still on disk and is marked `retired`
only once that is gone. A new bot in the roster gets a desk the next time
the page polls.

A session in a folder the roster does not know still shows up, on an
"Unassigned" floor, so nothing runs invisibly.

## What the hook writes

One JSON line per event: `time` (milliseconds, local offset), `event`,
`session_id`, `cwd`, `transcript_path` (the token counter reads it) and
`bot`. Added where the event carries them: `message` on a Notification;
`notification_type`, `title`, `source`, `reason`, `agent_type`, `agent_id`,
`agent_transcript_path` and `stop_hook_active` (a boolean); and `summary`,
the first 200 characters of the last assistant message on Stop and
SubagentStop, which is what "Finished today" shows. Every added text value
is cut at 300 characters. The prompt text is never written. SubagentStop is
installed for everyone, since the only cost of a hook that never fires is
nothing. `bot` is matched by the agent's frontmatter name (kept in the
roster as `agent_type`) or by the longest folder match, so renaming a bot in
the roster does not break the match.

## Status rules

Per session, from `events.jsonl` and the session's transcript. Events are
ordered as the hook wrote them, so a Stop and a prompt inside one second
still sort correctly.

- waiting on me: a Notification since the last prompt that nothing has
  answered, meaning no Stop after it and no transcript turn line after it. An
  `idle_prompt` notification after a Stop reads as resting; set
  `IDLE_IS_WAITING = True` in `hq.py` to count it.
- resting: stopped, ended, no prompt yet, or nothing for 24 hours.
- working: mid turn, with a new transcript line inside the last 10 minutes.
  A subagent transcript growing under the session counts, so a session that
  delegated a long job is working, not stuck.
- stuck: mid turn, nothing new for 10 minutes (`STUCK_AFTER_S`).

A bot shows the highest of its runs: waiting, then stuck, working, resting.
An agent bot (a `.claude/agents` definition) shows working while a session
has an open `Agent` tool call of its type, and resting once that call has
returned and SubagentStop has landed. When the same agent name is defined
in a project and at user level, the session's own project copy is the one
that lights up. The detail panel's "runs" counts sessions for a folder bot
and open calls plus finished subagent transcripts for an agent bot. The
header counts bots.

## Tokens

Summed from the `usage` field of every assistant line in each session's
transcript, once per message id (the transcript repeats a message once per
content block), bucketed by local day. The desk bar is relative to the
busiest bot today; the label is the absolute count (input + output + cache
read + cache write). Subagent transcripts under `<session>/subagents/` count
toward the agent named by SubagentStop when the roster has it, and toward
the parent session's bot until then. No model is called to count anything.

## What leaves the machine

Nothing. The hook makes no network call. The server binds 127.0.0.1 only,
refuses any Host header that is not loopback, serves only the five files it
knows, and sends a Content-Security-Policy that allows no third party
script. Three.js is vendored, not loaded from a CDN. The page's one fetch is
`/state` on the same origin.

What stays on the machine is still worth knowing. `/state` answers any
process on this machine, as every loopback server does, and it carries each
bot's current step, the notification text and the Stop summaries. The step
is built from a tool call's description, file path or pattern, never from a
Bash command, a URL, a prompt or a search query; when the last block is
plain assistant text, the step is the first 90 characters of that text, so
whatever the assistant chose to say can appear there. `events.jsonl`,
`roster.json` and `roster.json.previous` are 0600 inside a 0700 directory,
and every hook run and install keeps them that way.

## Known limits

- The current step is read from the transcript's last assistant block, so a
  tool still running shows as that tool.
- A session killed mid turn (no Stop, no SessionEnd) reads as stuck after 10
  minutes and as resting after 24 hours.
- The "Finished today" list is built from Stop events, so it starts empty the
  day the hooks are installed.
- The first `/state` after a start reads every transcript of the last 24
  hours from the beginning; later reads take only the new bytes. A day with
  hundreds of megabytes of transcripts costs a few seconds once.
- An `Agent` call run in the background returns its tool result at once, so
  its agent bot shows working only until then; the subagent's tokens land on
  the parent until SubagentStop names the agent. An `Agent` call whose result
  line never lands is closed by the session's Stop or by its next prompt, so
  an agent bot never stays lit for a turn that is over.
- The page needs WebGL2. iPhone Safari has it; a remote desktop without GPU
  acceleration may not. "fit view" in the header frames the tower again.
