---
name: mpt-shorts
description: Install, run or judge MoneyPrinterTurbo (harry0703/MoneyPrinterTurbo), the topic-to-video generator, held to the one flow that keeps inside YouTube's inauthentic content policy and the owned-voice rule. Load before installing it on any device, before entering any key into it, before rendering a Short with it, or when someone shares a post about it. Compiled 2026-10-31 from a source audit of commit 27843a9 with every finding independently verified, a sandbox install, and renders through tools/mpt_shorts/render_short.py.
---

# MoneyPrinterTurbo, tailored

A Python app with a Streamlit WebUI, a FastAPI server and a command line. Given a keyword it has an LLM write a script, a TTS voice read it, stock or AI clips matched to it and a random song mixed under it, then burns captions and writes an MP4. MIT licence. Version 1.3.9 at commit `27843a994bfa29c43c02150861d51490a6ca4bd2`, dated 2026-10-30. The GitHub page showed 136.6k stars that day.

## Why it is held to one flow

Its default output is the thing YouTube refuses to pay for. The monetization policy (support.google.com/youtube/answer/1311392, renamed "inauthentic content" on 2025-07-15) bars "AI-generated content made with generic or unoriginal templates giving the impression of mass production without adding the creator's original, authentic insights or perspective" and "image slideshows, templated storylines, or scrolling text with minimal or no narrative, commentary, or educational value". The policy grades the channel and the video, not the tool, so no setting makes it compliant. What does is taking every creative choice away from it.

Its default voice is a stock Microsoft Edge voice, which breaks "voice and identity owned, never rented".

So the only permitted use is as an assembler: our script, our Tee-clone voiceover file, our local clips, one video per run, captions made on the box. `tools/mpt_shorts/render_short.py` is the only sanctioned way to run it here. The install itself still carries the full CLI, WebUI and API; with no provider key in it the default keyword flow (a Moonshot script, Pexels clips) cannot finish, but a direct `cli.py` run with a supplied script and local clips would still read the script in a stock Edge voice, which needs no key. Running it any way but through the wrapper breaks the rule.

## What the code checks, and what it cannot

It checks: the install holds no provider credential, no proxy, no cross-posting, binds to loopback and keeps an inbound key; the caption model is on disk; the voiceover decodes, runs at most 180 s and, transcribed on the box, covers at least 0.85 of the script and of each third of it (a third may always miss one word, so one misheard word in a short script does not refuse a take a retry cannot fix) and is at least 0.85 the script, so half a take, a take missing its last sentence or a take with other speech fails (small numbers count the same as digits or words); every clip is local, 480 px or more a side, its picture runs as long as its sound (read from the stream, or from the DURATION tag of an mkv or webm), and the pictures together cover the voiceover; only one render runs on an install at a time; the caption font is a .ttf with a file named OFL or LICENSE beside it; the script, what the voiceover says and the voiceover's bytes do not repeat another episode, or the same episode for another show, in the ledger (shared 3 word shingles over the smaller set, 0.5, a starting value); the ledger exists and every manifest in it reads; the output is 1080x1920 with audio, within 0.35 s of the voiceover, with captions.

It cannot check, and says so in every manifest (`voice_identity_checked: false`, `clip_rights_checked: false`): whose voice it is, so a stock TTS file reading the script passes; whether each clip is ours or licensed, which YouTube's separate reused content rule also turns on; what the licence file beside a font actually says; how many Shorts go out a day, or anything outside the ledger it is pointed at, so a second ledger is a second memory. Those stay with the person who watches the render end to end.

Disclosure: YouTube's altered content page (support.google.com/youtube/answer/14328491) lists "Cloning one's own voice to create voice overs or dubs" as not needing the label. AI generated realistic footage and AI music as the main focus do need it, which is one more reason the generators stay off.

## What was verified

- Source audit, four dimensions (what leaves the machine, security, voice and identity, overlap with the render worker), 75 findings, each re-checked by a separate verifier at the same commit: 74 confirmed, none refuted, one left unverified: whether the hard coded Codex OAuth client id is OpenAI's own, a terms question for anyone who signs in through that provider, which this flow never does.
- Plain pip install on Python 3.13.17: exit 0 in 153 s, `pip check` clean, but it resolves Pillow 11.3.0 because MoviePy caps it. The project's own test suite offline: 3000 passed, 9 failed, 54 skipped in 531 s. All 9 failures trace to the system ffmpeg 6.1.1 and pass with ffmpeg 7.0.2 first on PATH.
- `tools/mpt_shorts/install.sh` from an empty directory: exit 0 in 40 s here, with warm caches. It takes the uv.lock route, which carries the patched Pillow 13.0.0 and MoviePy 2.2.1 (whose own `__version__` attribute still reads 2.1.2), verifies the caption model by sha256, writes `config.toml` at mode 600, and its audit came back empty. A second run is idempotent.
- Renders through the wrapper on 4 cores: a 19.26 s Piper test voiceover over two 12 s labelled clips took 193 s to 202 s and came out 1080x1920, h264 and aac, 19.267 s. Frames at 2 s, 11 s, 13 s and 18 s show clip 1, clip 1, clip 2, clip 2, so order holds. Captions burned in Atkinson Hyperlegible Next Bold. The voiceover covered 1.0 of the script and was 1.0 the script once numbers count either way. Each render deletes its own task folder and every clip copy MoneyPrinterTurbo made during it, whether it succeeded, failed or ran out of time, and a timeout kills MoneyPrinterTurbo's whole process group, its ffmpeg encoder included. A SIGTERM, SIGHUP or SIGINT to the wrapper kills the group and cleans up the same way, unless the caller had set that signal to ignored: a render started under `nohup`, or as a script's background job, rides out the hangup or Ctrl-C it was shielded from. A SIGKILL to the wrapper takes `cli.py` with it (it is set to die with its parent), and the next render finishes the cleanup from an in-flight marker. Measured on the real install: a timeout at 30 s and a supervisor's SIGTERM or SIGHUP each left no MoneyPrinterTurbo process running. A SIGKILL takes `cli.py` at once, but an ffmpeg encoder it already started finishes its step, reparented to pid 1: about 6 s when the kill lands in the concat step, writing into the task folder the next render removes. The render after a SIGKILL put the copy and task folder counts back where they were.
- Refusals, each measured on real files: a voiceover of another script (refused in 5 s before any render), the same script and voiceover under a new episode id, clips shorter than the voiceover, a clip with 6 s of picture and 12 s of sound (which MoneyPrinterTurbo would have padded with a frozen frame), and a woff2 caption font (its CLI takes .ttf or .ttc only). Coverage thresholds were set from faster-whisper transcripts of the full take (0.944 both ways before number matching), its first 62 percent (0.606 of the script) and the take plus other speech (0.563 the script). A take cut at 17.5 s, missing only its last sentence, said 0.90 of the script and passed the overall share; its weakest third is 0.71 and it is refused.
- `test_mpt_shorts.py`, 77 tests, runs preflight and render whole against a stand-in `cli.py` in a real child process that copies clips before it can fail, as MoneyPrinterTurbo does, and tests `probe()` on ffprobe's own report shapes. Of 36 mutants of the gate lines, 35 fail the suite; the survivor weakens the mode `lock-config` creates the file with, which the `chmod` after it restores. Each of the two later fixes, reverted, fails its own tests.
- A fresh verifier re-ran every critic's failing check at `5c98104` and found all seven fixed on the success path, and three gaps that are now closed: copies left by a failed render, `probe()` untested, and a missing last sentence passing. A second verifier confirmed those at `a10baf9` and raised two more, now closed: an orphaned encoder after a timeout, and the per third bar refusing one misheard word in a six word third. A third verifier confirmed both at `060749f` and found that the fix for the first put MoneyPrinterTurbo out of reach of a signal sent to the wrapper; that is closed too. A fourth confirmed the signal handling at `c07980c` and raised four smaller problems, each confirmed by its own verifier. Tee ruled on 2026-10-31 to fix two and keep two as known limits. Fixed: a stop signal the caller set to ignored (HUP, INT or TERM) now stays ignored, so a render started under `nohup` rides out the hangup, and a marker write that fails on a full disk no longer blocks later renders. Kept: the encoder a SIGKILL leaves behind, above, and the cleanup after a killed render deleting any copy made before the next render, so never run `cli.py` directly on a wrapper's install.

- No network on the wrapper's path, measured: one full render run under `strace -f -e trace=connect,sendto` covered 18 processes (the transcription check and MoneyPrinterTurbo's render) and recorded zero `connect` calls. A control socket under the same tracer recorded its one. An audit verifier's trace across the project's whole test suite and a plain CLI render, taken together, did see two TCP 443 attempts to GitHub addresses, which it attributed to the version check; which of the two runs made them was not separated.

Installed on srv1936199, the EditForge VPS, on 2026-10-31 by Tee in Termius: audit empty, Python 3.12.3, MoneyPrinterTurbo at the audited commit, 1.8G under `/opt/mpt-shorts` with the source at `/opt/mpt-shorts-src`. The first attempt failed because uv, asked for `python3`, chose a uv-managed CPython 3.15 on that host over `/usr/bin/python3` (measured there: the pinned uv's `python find python3` returns the managed 3.15.0, and `/usr/bin/python3` under `UV_PYTHON_PREFERENCE=only-system`), and ctranslate2 4.7.1 has no 3.15 wheel. `install.sh` now hands uv the `python3` first on PATH by absolute path, with `UV_PYTHON_PREFERENCE=only-system`, and refuses one outside 3.11 to 3.14. If the first `python3` on PATH is itself one uv manages, the install uses it. Not verified: a render on that host, so its time on 2 shared cores is unknown.

## Two defects found in its own behaviour

1. `subtitle.correct()` rewrites Whisper's text with the script's lines. Captions therefore always read as the script, even over the wrong voiceover: a mismatched render scored 1.0 on a caption check. The wrapper transcribes the voiceover itself with the same local model before rendering and compares that with the script.
2. In `sequential` concat mode `combine_videos` keeps only the first slice of each source file (`video.py:1073-1074`), and in the default `random` mode it shuffles slices. The wrapper sets the clip length above the longest source, so each clip plays whole, in the order given, and it refuses footage shorter than the voiceover rather than let it loop.

## Install

On the host, as the user that will run it. Needs git, curl, sha256sum, ffmpeg and python3 3.11 or newer.

```bash
tools/mpt_shorts/install.sh /opt/mpt-shorts
```

It clones the audited commit and checks it, installs pinned uv 0.11.32 into its own venv, runs `uv sync --frozen --no-dev` on the `python3` first on PATH, by absolute path and only if it is 3.11 to 3.14, so uv cannot swap in a Python it manages, downloads `Systran/faster-whisper-base.en` at revision `3d3d5de` and checks four sha256 sums, then writes the locked `config.toml`: listen on 127.0.0.1, a random inbound `api_key`, captions from local Whisper, no provider key anywhere. It pipes nothing into a shell, starts nothing and asks for no key.

## Render

```bash
python3 tools/mpt_shorts/render_short.py render \
  --mpt-root /opt/mpt-shorts/mpt --mpt-python /opt/mpt-shorts/mpt/.venv/bin/python \
  --show tqo --episode tqo-s001 \
  --script script.txt --voice tee-voice.mp3 \
  --clips demo1.mp4 demo2.mp4 demo3.mp4 \
  --font tools/mpt_shorts/fonts/atkinson-hyperlegible-next-latin-bold.ttf \
  --out out/ --ledger /opt/mpt-shorts/ledger
```

It prints one JSON line and exits 0 with the output, or exits 2 with `refused` and the reason. Every render writes a manifest to the ledger: hashes of the script, voiceover, every clip, the font and the output, the exact command, `published: false` and `human_review: pending`. The ledger is what the repetition check reads: `install.sh` creates it, a missing one or an unreadable manifest in it stops the render, so keep one per host and never delete it. MoneyPrinterTurbo stops taking clips once the picture covers the voiceover, so the manifest calls them `clips_supplied`.

Caption fonts live in `tools/mpt_shorts/fonts` with their OFL texts. TQO: Atkinson Hyperlegible Next Bold, instanced at weight 700 from the variable `sites/tqohq/fonts` woff2 with fontTools 4.60.1, which makes it a Modified Version under OFL section 3; the licence declares no Reserved Font Name, so the name may stay. NCO Forge: Inter Bold, the unmodified TrueType from the Inter 4.1 release (`extras/ttf/Inter-Bold.ttf`, sha256 `288316099b1e0a47a4716d159098005eef7c0066921f34e3200393dbdb01947f`) with that release's own licence text. MoneyPrinterTurbo's CLI takes .ttf or .ttc only, so a woff2 is refused. The bundled MoneyPrinterTurbo fonts carry no licence and two are named after Apple and Microsoft system fonts.

`--fit contain` (default) keeps the whole frame of a screen recording with bars; `--fit cover` fills the frame and crops.

## What leaves the machine, by path

On the wrapper's path, nothing by design: no LLM (`--video-script` is supplied), no TTS (`--custom-audio-file`), no stock or AI footage (`--video-source local`), no music (`--bgm-type none`), captions from a model on disk. Elsewhere in the app, all verified at the commit:

- WebUI: an unconditional GET to `api.github.com/repos/harry0703/MoneyPrinterTurbo/releases/latest`, at most once per 12 h per process, no user data, no off switch (`app/services/version_checker.py:17`). The wrapper never starts the WebUI.
- Default TTS: the narration text to Microsoft's Edge read-aloud service, `speech.platform.bing.com`, with no key (edge-tts 7.3.1). Any `voice_name` without a known provider prefix goes down that path (`voice.py:771`). An empty or mistyped name such as `ElevenLabs:` makes the task fail; a valid Edge voice name produces a stock voice with no warning.
- ElevenLabs TTS: the whole script in one request with hard coded voice settings (stability 0.5, similarity 0.75) that may not match the clone's own (`voice.py:2515-2527`). Our lane already makes the voiceover, so this path is unused.
- VoxCPM TTS uploads a reference voice recording to `api.modelbest.cn` (`voice.py:3228`). Never with Tee's voice.
- Video-to-music (`bgm_type` sonilo or elevenlabs) uploads a silent proxy of the finished video, faces included.
- Upload-Post cross-posting POSTs the MP4 and publishes to TikTok, Instagram and YouTube, privacy default "public". Off by default; the audit refuses an install with it on.
- `docs/skill/mpt_agent.py` downloads the moving `main` branch zip, not the audited commit, and runs it with the user's keys.

## Never

- Never load the upstream `docs/skill/SKILL.md` or run `mpt_agent.py`. It tells an agent not to ask for confirmation, to pipe `astral.sh` installers into a shell, to ask for keys in chat, and it defaults to a stock Chinese Edge voice.
- Never put a provider key in its `config.toml`. The audit refuses any non-empty credential, and the HTTP API with a key in it lets anyone who reaches the port spend that key in any voice it can use, including a clone.
- Never run Tee's presenter footage through it. Clips are opened with `audio=False`, cut and by default shuffled (`video.py:805-815`); it has no avatar or lip sync stage. B-roll and screen recordings only.
- Never use the HTTP API for this lane. It cannot take a supplied voiceover (`custom_audio_file` must sit inside a task directory the server creates), it ships unauthenticated on 0.0.0.0, and its Origin check trusts the Host header.
- Never use `bgm_type random`. The 29 bundled songs have no licence; the README says they came from YouTube.
- Never use `--batch-file`, `--video-count` above 1, or the same render on two channels.
- Never feed it a clip that is not ours or licensed for this use, and never a stock TTS voiceover. The code cannot tell either.
- Never publish from it. A human watches the output end to end, then it goes through the gated n8n lane.

## Where it fits, and where it does not

The 2026-10-31 overlap scan found almost every stage duplicates the estate: the script writer in `TQO FINAL V5`, the ElevenLabs clone voice, Pexels b-roll, and the render worker in `deploy/render-worker`, which already runs faster-whisper base.en word timings (`words.py`) and ffmpeg assembly with loudness handling MoneyPrinterTurbo lacks. What it adds is the caption burn and clip fitting for a vertical Short. Its seam into the estate is the command line on the box, called by the worker; there is no webhook, and the HTTP API's state is in memory and lost on restart. Wiring it into n8n is a workflow edit and a publish, so it is Tee's ruling.

The full status record is `docs/devon/SYS_OPS_mpt-shorts-tailored_v1_2026-10-31-*.md`; the newest wins.
