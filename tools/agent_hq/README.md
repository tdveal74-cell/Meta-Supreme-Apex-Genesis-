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

1. Copies `hq.py`, `hook.py`, `index.html`, `app.js` and `vendor/` into
   `~/.agent-hq/`, so the hooks keep working if the repository moves.
2. Merges six hooks into `~/.claude/settings.json` (SessionStart,
   UserPromptSubmit, Notification, Stop, SubagentStop, SessionEnd). Existing
   hooks are kept. The file is backed up beside itself before the first write.
   A second run adds nothing.
3. Writes `~/.agent-hq/roster.json` if it does not exist, then serves.

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
| `~/.agent-hq/events.jsonl` | one line per hook event |
| `test_agent_hq.py` | the offline tests, run in CI's standalone job |

## Commands

```bash
python3 tools/agent_hq/hq.py up           # install, roster if missing, serve on 7777
python3 tools/agent_hq/hq.py install      # hooks and files only
python3 tools/agent_hq/hq.py roster       # rescan, print the table, merge into roster.json
python3 tools/agent_hq/hq.py roster --no-write --json
python3 tools/agent_hq/hq.py serve --port 7777
python3 tools/agent_hq/hq.py state        # /state once, as JSON, for a terminal
python3 tools/agent_hq/hq.py uninstall    # remove the six hooks, keep the data
```

`AGENT_HQ_DIR` moves the data directory; the installed hook command honours
it too. `CLAUDE_CONFIG_DIR` moves `~/.claude`, as Claude Code does.

## The roster

`roster` reads three places and merges the result into `roster.json`:

- `~/.claude/agents/*.md`, user level agents
- `<folder>/.claude/agents/*.md` for every folder sessions have run in
- the folders themselves, read from the `cwd` field inside the transcripts
  under `~/.claude/projects/`, one "session" bot per folder, with the model
  taken from the newest assistant line

Team is inferred from keywords in the name and description (Visuals, Content,
Research, Ops, in that order; Ops when nothing matches). Edit `team`, `name`
or `job` in `roster.json` and a rescan keeps your edits; it refreshes `model`
and `source` from the files and marks a deleted agent `retired`. A new bot in
the roster gets a desk the next time the page polls.

A session in a folder the roster does not know still shows up, on an
"Unassigned" floor, so nothing runs invisibly.

## Status rules

Per session, from `events.jsonl` and the session's transcript:

- waiting on me: a Notification since the last prompt that nothing has
  answered, meaning no Stop after it and no transcript turn line after it. An
  `idle_prompt` notification after a Stop reads as resting; set
  `IDLE_IS_WAITING = True` in `hq.py` to count it.
- resting: stopped, ended, no prompt yet, or nothing for 24 hours.
- working: mid turn, with a new transcript line inside the last 10 minutes.
- stuck: mid turn, nothing new for 10 minutes (`STUCK_AFTER_S`).

A bot shows the highest of its sessions: waiting, then stuck, working,
resting. The header counts bots, not sessions.

## Tokens

Summed from the `usage` field of every assistant line in each session's
transcript, once per message id (the transcript repeats a message once per
content block), bucketed by local day. The desk bar is relative to the
busiest bot today; the label is the absolute count (input + output + cache
read + cache write). Subagent transcripts under `<session>/subagents/` count
toward the agent named by SubagentStop when the roster has it, otherwise
toward the parent session's bot. No model is called to count anything.

## What leaves the machine

Nothing. The hook makes no network call. The server binds 127.0.0.1 only,
refuses any Host header that is not loopback, serves only the five files it
knows, and sends a Content-Security-Policy that allows no third party
script. Three.js is vendored, not loaded from a CDN. The page's one fetch is
`/state` on the same origin.

## Known limits

- The current step is read from the transcript's last assistant block, so a
  tool still running shows as that tool.
- A session killed mid turn (no Stop, no SessionEnd) reads as stuck after 10
  minutes and as resting after 24 hours.
- The "Finished today" list is built from Stop events, so it starts empty the
  day the hooks are installed.
- The page needs WebGL2. iPhone Safari has it; a remote desktop without GPU
  acceleration may not.
