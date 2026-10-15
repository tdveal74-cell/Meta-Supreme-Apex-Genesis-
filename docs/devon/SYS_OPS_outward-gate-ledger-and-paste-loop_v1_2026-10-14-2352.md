# The outward gate, its ledger, and the paste loop

Ruled by Tee on 2026-10-14: "Yes on all 3 decisions and file it", after a read of
every cloud session in the account (67 sessions, 101,079 events, 1,752 messages
he typed). The three decisions were a gate and ledger for outward calls, a
skill for the paste loop, and rotating the secrets he had pasted into sessions.

## What the read found

Counts come from `SESSION_AUDIT_2026-10-14.md` in the session scratchpad and
are not in the repository. 1,810 outward high tier calls ran. Of them, 45
merges, 49 workflow edits, 36 publishes, 29 workflow executions and 29 force
pushes ran with no answered card and no message from him in the 30 minutes
before. The paste loop appeared as 33 pasted outputs and 13 asks for a command
by itself or in smaller parts, by text match, not hand count.

## What was built

- `.claude/hooks/gate_ledger.py`, wired in `.claude/settings.json` on
  PreToolUse, PostToolUse and PostToolUseFailure. CLAUDE.md carries the rules
  under "The outward gate and its ledger". 256 tests in `test_gate_ledger.py`,
  added to the standalone job in `ci.yml`.
- `.claude/skills/paste-loop/SKILL.md`, and CLAUDE.md now counts nine skills,
  eight of them ours.
- `.claude/ledger/` is ignored by git.

## How it was checked

Seven fresh critics in two rounds, each in its own worktree, each echoing the
commit it reviewed. Round one (five critics, base 599bcab) found classifier
misses in the shell parser, uncovered connector tools, scrub gaps, a lockout
when the ledger could not be written, image bearing messages not counting as
messages, future timestamps, nested subagent paths, and prose that claimed more
than the code did. Round two (two critics, base db1c367) found one line loops,
comments with apostrophes, command wrappers with flags, redirects read as
refspecs, scheme-less local URLs and a verb list that was an allowlist of
writes. Every finding an honest model would hit was fixed and pinned by a test
that names the input. The gate was also run against this session's real
transcript: the newest signal was read as a typed message and the same file
read two hours later was refused.

## What it does not do

It reads the command text of curl and git only. A write through wget, gh, an
inline script or the GitHub MCP file tools is invisible to it. An answered card
counts as presence and not consent, because the hook cannot read the answer. A
scheduled or webhook session has no human in it, so every gated call there is
refused by design. It reads the whole transcript on a gated call, about 0.4 s on
a 53 MB file.

## Not verified

- What the harness does with the wrapper's `exit 1` when the script or python3
  is missing. It was recalled from the hook contract, not measured, because hook
  settings load at session start and were not live here.
- A subagent's real hook input. Fixtures and a critic's synthetic run pin the
  path handling, and no live subagent call has confirmed it.
- Nothing reads the ledger into DEVON. It is per container and not durable.

## Rotation list, Tee's to run

I did not read the values and cannot rotate anything. Kinds are inferred from
shape only, so confirm each before revoking.

| date | session | shape | likely owner |
|---|---|---|---|
| 2026-08-12 | Repo build and AAA upgrade | one 64 character hex token | EditForge MCP token |
| 2026-08-26 | Seven improvements continuation | one provider key | Cerebras |
| 2026-08-29 | EditForge status update | six 64 character hex tokens, one `key_` token | EditForge tokens |
| 2026-08-31 | Local DEVON in EditForge | two JWTs | n8n API key |
| 2026-09-23 | Hostinger VPS Razako repo | one OAuth code | Hostinger, single use |

The stored account transcripts are not redacted, so these values remain in them
until rotated. The OAuth code is single use, so revoking the grant is only
needed if it was never exchanged.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_outward-gate-ledger-and-paste-loop_v1_2026-10-14-2352.md
DATE: 2026-10-14
DECISIONS: Tee ruled "Yes on all 3 decisions and file it": build the gate and ledger, build the paste-loop skill, rotate the pasted secrets. The classifier gates every tool on named platform servers except reads, and merges stay ledger only under the standing approval of 2026-10-11.
FINDINGS: 1,810 outward high tier calls in 67 sessions; 45 merges, 49 workflow edits, 36 publishes, 29 workflow executions and 29 force pushes ran with no card and no message in the prior 30 minutes. Two critic rounds found and fixed the shell classifier misses, the coverage gaps and an overclaiming doc.
OPEN: Tee rotates the five secret groups above. The hook's live behaviour, the exit 1 handling and the subagent path are measured in the first session after this merges. Nothing reads the ledger into DEVON.
STATUS: Built, 256 tests passing, two critic rounds applied, not yet live.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
