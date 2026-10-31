---
name: openmontage
description: Install, drive or judge OpenMontage (calesthio/OpenMontage, AGPL-3.0), the agent-driven video production system with 12 production pipelines and 151 tools over Remotion and HyperFrames renderers. Load before running any of its pipelines, before any key goes into its .env, before it touches Tee's voice or face, or when asked to make a video "like this one" with it. Installed 2026-10-30 at commit 195eab2 outside this repository by scripts/install.sh, and a zero-key demo rendered and was measured.
---

# OpenMontage

A Python tool library, a Remotion composer and a large body of instructions. The agent is the orchestrator: it reads `AGENT_GUIDE.md`, picks one of the pipeline manifests in `pipeline_defs/`, reads a stage director skill before each stage and calls the tools. There are 13 manifests at the pinned commit, 12 productions plus `framework-smoke`. The X post that named it on 2026-10-30 claimed 100+ tools and 700+ skill packs; this commit holds 151 tools and 140 SKILL.md files (91 under `.agents/skills`, 49 under `.claude/skills`), plus 157 instruction files under `skills/`.

Licence: GNU AGPL-3.0. Running it for our own productions and owning what it renders is fine. Copying its code into this repository, or offering a modified copy to anyone else over a network without publishing that modified source, is not. The installer keeps it outside this repository for that reason and for a second one: ruff and pytest would sweep its code into our checks.

## Install

```bash
bash .claude/skills/openmontage/scripts/install.sh
```

It fetches exactly commit `195eab24478dc9363326aec437aefc3701635ddf` into `$OPENMONTAGE_HOME` (default `~/OpenMontage`), runs upstream's `make setup` with Python 3.11, which is the version upstream's CI runs (uv fetches it; override with `OPENMONTAGE_PYTHON`), then loads the tool registry and prints the counts. It refuses a target inside this repository, a directory that is not a git checkout, a checkout at any other commit, and an empty repository whose origin is not OpenMontage. It resumes its own interrupted fetch. A re-run at the pin takes about 8 seconds.

`~` is the ephemeral container home, so the install is gone when the container is reclaimed and each new session runs the installer again. Anything worth keeping from `projects/` goes to Drive before the session ends.

To move to a newer upstream commit, change `PIN` in the installer and re-read what changed against the rules below. Upstream pins nothing on the Python side (`requirements.txt` is all `>=`, `piper-tts` has no version) and the HyperFrames npm package is always fetched at latest, so two installs at the same pin can differ. The Remotion side is pinned: `remotion-composer/package-lock.json` resolves 244 packages from registry.npmjs.org, each with a sha512 integrity hash.

## What was verified, 2026-10-30, in a cloud container

- The installer exited 0 in 1m51s: Python 3.11.17, the Remotion composer installed from its lockfile, `piper-tts` 1.8.0, HyperFrames 0.8.222 from npx. The registry loaded 151 tools in 26 capability groups, 41 usable with no key set.
- `render_demo.py world-in-numbers` exited 0 in 2m15s on the first run, which included Remotion downloading its 92 MB Chrome Headless Shell from remotion.media. ffprobe on the file: 1920x1080 h264 at 30 fps, 23.06 s, 4.3 MB, and an AAC track that is silence (mean and max volume -91.0 dB). Frames at 2, 8, 15 and 21 s were looked at: animated charts and titles, and `blackdetect` found no black segment. This proves the visual render path only.
- Every installer path was run: fresh install, re-run at the pin, resume after an interrupted fetch (with `make` stubbed), and the four refusals.
- Not verified: any keyed provider, any production pipeline end to end, any speech output, Backlot, a HyperFrames render, and upstream's own test suite.

## Driving it from this repository

The session's project is this repository, so OpenMontage's own `CLAUDE.md`, its 49 skills and its three slash commands do not load. Work through Bash in the checkout. Read `$OPENMONTAGE_HOME/AGENT_GUIDE.md` as upstream's contract; it calls itself binding, and this skill and this repository's `CLAUDE.md` outrank it wherever they differ. Run tools with the checkout's `.venv/bin/python` from the checkout root. Its Layer 3 skills under `.agents/skills/` are files to read before a tool call, as the guide asks.

The guide tells the agent to start the Backlot board and open a browser at the start of every pipeline (`AGENT_GUIDE.md:225`). A cloud session has no browser, so skip it. Backlot binds 127.0.0.1:4750 only, serves GET routes only, and starts as a detached process that outlives the call.

## House rules that outrank its defaults

1. Owned voice only. Every speech path falls back to a library voice when no voice is named: `tools/audio/elevenlabs_tts.py:187` hard-codes one for ElevenLabs, OpenAI defaults to alloy, Google to Chirp3-HD, Piper to lessac, and `tts_selector` simply takes the first available provider by rank. For anything Tee might publish, pass his clone's voice id with `preferred_tool="elevenlabs_tts"`, reading the id from DEVON and never from memory. The `localization-dub` pipeline and the avatar-spokesperson "narration over graphics" fallback both use a ranked library voice; refuse both for show work. A library voice is acceptable only for a scratch timing pass that is deleted, never for anything that leaves the session. `mistral_tts` and `fish_audio` will clone from any audio handed to them; never give them anyone's audio but Tee's, or the consented TSWS recordings.
2. Own likeness only. The avatar tools take whatever face they are given (`talking_head` from a photo, `lip_sync` on a plate, `heygen_avatar` from an avatar id) and nothing checks whose face it is. Only Tee's own likeness goes in.
3. No paid call without Tee's yes. `config.yaml` ships `budget.mode: warn` with a $10 total and a $0.50 per-action threshold, and warn mode never blocks (`tools/cost_tracker.py:151`). `CostTracker` is built only in tests, so no tool enforces a budget, and the guide asks only that the agent announce a paid call before making it (`AGENT_GUIDE.md:96`). Here every paid call, or every batch with its total, gets Tee's approval in chat first, with the price. `heygen_avatar` and the ElevenLabs v4 models refuse to estimate a price, so get the quote before asking.
4. Keys are Tee's to set. Never ask for or accept one in chat. This environment's proxy holds a real key for generativelanguage.googleapis.com, so a placeholder `GOOGLE_API_KEY` or `GEMINI_API_KEY` in the checkout's `.env` would switch on billed Gemini calls, including `gemini_omni_video` uploading local video to the Gemini Files API. Writing any key into `.env` is a ruling for Tee.
5. A human watches the whole render. The edit and compose stages carry no human gate in any of the five pipelines read, so the final render exists before anyone looks, and the self-review passes with unresolved criticals after two rounds (`skills/meta/reviewer.md:87`). Nothing moves toward Published until Tee has watched it end to end. OpenMontage never posts to a platform: its only publisher, `export_bundle`, packages files locally, so publishing stays behind the OS 28 gate.
6. Disclosure and rights. No pipeline has an AI-disclosure, rights or platform-policy step. The reference-video workflow downloads someone else's video with yt-dlp and offers "same structure, different subject" concepts; its only guard is against a carbon copy, and it never asks about rights. Use it to study structure and pacing. Never reuse the reference's footage, audio or likeness, and put anything modelled closely on one named creator in front of Tee first. The Pixabay music tool scrapes pixabay.com while presenting itself as desktop Chrome (`tools/audio/pixabay_music.py:114`); whether that fits the site's terms is Tee's call before it runs.
7. Code it runs. `math_animate` executes model-written Python on the host through manim, and upstream's own comment says its denylist is not a sandbox (`tools/graphics/math_animate.py:34`); never pass `allow_unsafe_code`. Listing providers, which `make setup` and the installer both do, runs `npx --yes hyperframes doctor` at whatever version npm serves that day.

## What leaves the machine

With a key set, each provider tool calls its own vendor: fal.ai, ElevenLabs, HeyGen, OpenAI, Google, xAI, Replicate, Runway, Kling, MiniMax, Higgsfield, Suno and about twenty more. Local media goes out in a few of them: video to the Gemini Files API, images to fal.ai storage, files to Atlas Cloud, audio to Mistral and Azure speech, and audio to HeyGen voice conversion.

With no key at all, it still reaches out. The npm registry and the HyperFrames package are fetched on every preflight. Stock archives are searched when a pipeline asks: Wikimedia Commons, Internet Archive, NASA, the Library of Congress, NARA, Coverr, Pond5's free tier, ESA, NOAA, JAXA, Mixkit and Dareful. Model weights download on first use, CLIP and Whisper from Hugging Face and face restore and upscale models from GitHub releases. Remotion fetches its Chrome on the first render. GSAP and three.js load from cdn.jsdelivr.net when HyperFrames or three.js scenes render, and the Backlot UI loads Google Fonts.

No telemetry, analytics or update check was found in upstream's own code; third-party libraries were not inspected. `video_analyzer` runs locally, and its keyframes go to whatever model runs the agent session.

Writes outside the checkout: `~/.openmontage/clips_cache` on first use of the clip corpus builder (20 GB cap, `OPENMONTAGE_CACHE_DIR` moves it), each model library's own cache, the npx cache and Remotion's Chrome.

## How this was read

Three read-only scanners went over the pinned commit on 2026-10-30, one for machine side effects, one for the network surface and one for agent instructions against these rules, and every fact above carries the file and line they cited. Tee asked for no reviews, so no second agent re-ran their checks: claims that something is absent are grep results, not proofs. Not read in full: most of `tools/`, the skill trees under `.agents` and `.claude`, `docs/` and `tests/`. Which speech provider ranks first by default is unverified, because `lib/scoring.py` was only grepped.
