# MoneyPrinterTurbo, tailored to one flow

Session https://claude.ai/code/session_01SsiDmKXeivWwUHLhvqFcAw, 2026-10-30 into
2026-10-31. Tee sent a post (x.com/maxwell_lenoir, 2026-10-30) about
MoneyPrinterTurbo and said "Install this", then asked "How can we tailor it so it
don't violate the YouTube policy", then "Ok do it". This doc records what was
built, what was measured, what the critics found and what is still his to rule.
Branch `claude/mpt-shorts-tailored`, PR #444.

## The tool

harry0703/MoneyPrinterTurbo, MIT, version 1.3.9 at commit
`27843a994bfa29c43c02150861d51490a6ca4bd2` (2026-10-30). The post said "more than
130,000 stars"; the GitHub page showed 136.6k on 2026-10-30, so that held. Given
a keyword it has an LLM write a script, a stock Edge voice read it, stock or AI
clips matched to it and a random bundled song mixed under it.

That default is the template YouTube refuses to monetize. The monetization page
(support.google.com/youtube/answer/1311392, policy renamed "inauthentic content"
on 2025-07-15) bars "AI-generated content made with generic or unoriginal
templates giving the impression of mass production without adding the creator's
original, authentic insights or perspective". The voice breaks the owned-voice
rule. The altered content page (answer/14328491) lists "Cloning one's own voice to
create voice overs or dubs" as needing no label.

## What shipped on the branch

`tools/mpt_shorts/render_short.py` runs MoneyPrinterTurbo one way only: a
supplied script, a supplied voiceover file, local clips in a given order, one
9:16 video, captions from a local Whisper model, no music, no cross-post. It
refuses before rendering on a provider credential, proxy, cross-post switch,
non-loopback bind or missing caption model in the install; a voiceover that does
not read as the script; clips that do not cover the voiceover; a caption font
with no licence file beside it; and a script, spoken text or voiceover that
repeats another episode in the ledger. It writes a manifest per render and never
publishes.

`tools/mpt_shorts/install.sh` pins the commit, uv 0.11.32, the project's uv.lock
and `Systran/faster-whisper-base.en` at revision `3d3d5de` with four sha256 sums,
and writes the locked `config.toml`. `tools/mpt_shorts/fonts` holds Atkinson
Hyperlegible Next instanced to Bold for TQO and the unmodified Inter 4.1 Bold
TrueType for NCO Forge, each with its OFL text. Skill `mpt-shorts` carries the
audit and the rules. `test_mpt_shorts.py`, 33 tests, joins the standalone job.

## Measured

| check | result |
|---|---|
| source audit, four dimensions, every finding re-checked by an independent verifier | 75 findings: 74 confirmed, 0 refuted, 1 unverified |
| plain pip install, Python 3.13.17 | exit 0, 153 s, Pillow 11.3.0 |
| project test suite offline | 3000 passed, 9 failed, 54 skipped; the 9 pass with ffmpeg 7.0.2 |
| `install.sh` from empty, then again | exit 0 in 40 s with warm caches, Pillow 13.0.0, MoviePy 2.2.1, audit empty; rerun exit 0 |
| wrapper render, 19.26 s Piper voiceover, two 12 s clips, 4 cores | 193 s to 220 s, 1080x1920 h264 and aac, 19.267 s; script said 1.0 and said is script 1.0 on the final code |
| clip order and captions | frames at 2, 11, 13 and 18 s read clip 1, 1, 2, 2; captions burned in Atkinson Bold |
| mismatched voiceover | refused in 5 s, before any render |
| clip with 6 s of picture and 12 s of sound | refused before any render |
| repeat, short clips, woff2 font | each refused |
| network on the wrapper's path, `strace -f` | 18 processes, 0 `connect` calls; a control socket under the same tracer recorded 1 |
| `test_mpt_shorts.py` | 69 passed; 28 of 29 gate mutants fail it, the survivor equivalent; the process group test fails on a kill of `cli.py` alone |
| standalone list, ruff | 5557 passed, clean |

The voiceover used for every render was a Piper test voice, never published, and
never Tee's. No render has run on the VPS.

## Two defects found in MoneyPrinterTurbo itself

`subtitle.correct()` rewrites Whisper's caption text with the script's lines, so
captions always read as the script. The first version of the wrapper checked
captions against the script and scored a mismatched voiceover 1.0, which measured
nothing. The wrapper now transcribes the voiceover itself before rendering.

In `sequential` mode `combine_videos` keeps only the first slice of each clip
(`video.py:1073-1074`), and the default `random` mode shuffles slices. The
wrapper sets the clip length above the longest clip, so each plays whole and in
order.

## What the critics found

A fresh critic with the policy lens, verified by a second agent, confirmed seven
findings against `9d46c46`, all fixed in `b694d64` or this doc:

1. The owned-voice rule is not enforced by code: a stock TTS file reading the
   script passes. Now stated in the skill, and every manifest carries
   `voice_identity_checked: false`.
2. "The only way to run it" was a convention: a direct `cli.py` run can still
   produce a stock Edge voice. The skill now says so.
3. The repeat check was weaker than described. It now also compares what the
   voiceover says, and the skill states exactly what it compares.
4. The status doc the skill pointed at did not exist. This is it.
5. The skill said the lock installs MoviePy 2.1.2. It installs 2.2.1, whose
   `__version__` reads 2.1.2.
6. `inter-bold.ttf` was CFF OpenType in a .ttf name. Replaced with the release's
   own TrueType.
7. Clip rights and YouTube's reused content rule were not addressed. The skill
   now bars unlicensed clips, and manifests carry `clip_rights_checked: false`.

A second critic with the correctness lens attacked the same commit with real
files. Its findings, fixed in the commit after this doc's first version: a clip
whose sound outlasts its picture passed the footage check and came out with a
frozen frame, so clips are now measured by their picture; a voiceover covering
half the script passed the 0.6 ratio, so the check now needs 0.85 of the script
said and 0.85 of what was said to be the script; the repeat check exempted a
same episode id on another show, skipped unreadable manifests and treated a
missing ledger as empty, and all three now stop the render; a nested manifest
crashed it; `install.sh` broke on a relative path; renders left their clip
copies and task folders behind, 152 MB after a few runs; and 25 of 33 gate
mutants survived the tests. The tests now run preflight and render whole
against a stand-in `cli.py`, and 21 of 22 gate mutants fail them.

A fresh verifier then re-ran every failing check at `5c98104`. All seven fixes
held on the success path, and it found three gaps, each measured: a render that
failed or ran out of time left MoneyPrinterTurbo's clip copies behind, because
MPT copies clips before it can fail and names them only on success; the tests
stubbed `probe()`, so a mutant that restored the frozen-frame defect passed
them; and a take missing only its last sentence said 0.90 of the script and
passed. Now: a render cleans every copy that appeared during it, under a lock
so it is one render per install; `probe()` is tested on ffprobe's own report
shapes and reads an mkv or webm stream's DURATION tag; and each third of the
script must be 0.85 said. The 17.5 s cut is refused at 0.71, a render killed at
30 s leaves the copy count at 20 before and after, and a real render with an
mkv clip passes. 65 tests; 28 of 29 gate mutants fail them, the survivor
equivalent.

A second fresh verifier confirmed all three at `a10baf9` on real media and
raised two smaller items, both closed in the next commit: a timeout killed
`cli.py` but left its ffmpeg encoder running for a few seconds, so the render
now runs in its own process group and a timeout kills the group (a real render
killed at 30 s left no encoder and no `cli.py`); and the per third bar refused
a single misheard word in a six word third of a 20 word script, deterministically,
so each third may now always miss one word. 69 tests.

## Open, and whose

- Installing it on the VPS is Tee's ruling. Nothing was installed on any device.
- Wiring it into `TQO FINAL V5` or the render worker is a workflow edit and a
  publish, so it is his too.
- The thresholds (0.85 voice coverage per third, 0.5 repeat similarity) are
  starting values. The ledger is where they get set once real renders exist.
- Render time on the VPS's 2 shared cores is unmeasured.
- Unverified: whether MoneyPrinterTurbo's hard coded Codex OAuth client id is
  OpenAI's own. It only matters to someone signing in through that provider,
  which this flow never does.

## DEVON RECEIPT

AREA: Systems, TQO, NCO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_mpt-shorts-tailored_v1_2026-10-31-0044.md
DATE: 2026-10-31
DECISIONS: Tee asked to install MoneyPrinterTurbo and then to tailor it to the YouTube inauthentic content policy, and said "Ok do it" to running it only as an assembler of our own script, Tee-clone voiceover and local clips. No device install and no n8n change were made without a ruling.
FINDINGS: The default flow is the template the policy refuses and its voice is rented. MoneyPrinterTurbo rewrites captions to the script and keeps only the first slice of each clip in sequential mode; the wrapper works around both. The bundled fonts and songs carry no licence. The wrapper's render makes no network connection, measured with strace. Two critics' findings on the first commit were verified and fixed: the code cannot check whose voice or whose clips it is, so manifests say so; a frozen-frame clip and half a voiceover used to pass; the repeat check failed open four ways; most gate lines had no test.
OPEN: VPS install and n8n wiring are Tee's rulings; thresholds are starting values; VPS render time unmeasured.
STATUS: Branch claude/mpt-shorts-tailored, draft PR #444, not merged at writing. Sandbox install and renders proven in the cloud container only.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
