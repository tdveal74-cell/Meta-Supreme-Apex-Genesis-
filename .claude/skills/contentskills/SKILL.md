---
name: contentskills
description: Install, drive or judge ContentSkills by Blotato (blotato/contentskills, AGPL-3.0), a local short vertical video pipeline with writing and posting skills. A fresh session does not have it; run scripts/install.sh first, about four minutes. Load before running any of its pipelines, before any key goes into its .env, before it touches Tee's voice or face, and before anything it makes is posted.
---

# ContentSkills

A Node and Python pipeline that turns a topic or a recorded take into a short vertical video: storyboard, local voice, Chromium-drawn graphics, ffmpeg composite, quality check. Upstream is https://github.com/blotato/contentskills, pinned here at `d137fbf17e4a8614d41185535c32b284e4845e4b` (its initial commit, 2026-11-24). Its code is GNU AGPL-3.0 (`LICENSE`): running it for our own productions is fine. Copying its code into this repository, or offering a modified copy to anyone over a network without publishing the source, is not. That is why it is installed outside this repository and not vendored.

## Install

```bash
bash .claude/skills/contentskills/scripts/install.sh
```

Run it with a Bash timeout of at least 600000 ms, or in the background. It fetches the pin into `$CONTENTSKILLS_HOME` (default `~/contentskills`) and runs upstream's `npm run setup`. It needs node 22 or newer, npm, uv, ffmpeg, ffprobe, git and python3, and refuses without them. It refuses a target inside this repository, a checkout at another commit, a checkout with local changes to tracked files, any untracked file that would load as code, and a media file that is neither its Git LFS pointer nor the file the pointer names. Exit codes are in the script's header: 0 installed, 1 a check failed, 3 refused, 4 installed with media still a pointer.

`~` is the ephemeral container home, so each new session installs again.

## What was measured

| date | result |
|---|---|
| 2026-11-26 | fresh install in this cloud container, exit 0, 3 min 28 s: three Python 3.13.18 environments import (voice 16 packages, effects 4, transcribe 23), the three Kokoro model files match their checksums, 432 of 432 media files are the real files, chrome-headless-shell 158.0.8127.88 installed. Run by the installing session once. |

Not verified: any render, the dashboard, the quality check, the ElevenLabs path, the posting skill, and any machine other than this container. The speech model `small.en` downloads on first transcription. This cloud session's git proxy serves no Git LFS objects, so upstream's setup fetches each media file from media.githubusercontent.com and checks its SHA-256; that host answered 200 on 2026-11-25.

## Driving it from this repository

Work through Bash in the checkout. Read `AGENTS.md` and `skills/make-video/SKILL.md` there first; this file and this repository's CLAUDE.md outrank them wherever they differ. Its storyboard flow stops for the user's approval on a local page at `localhost`. A cloud session has no browser, so approval is Tee's answer on a card, and `npm run approve` runs only after that answer. Look at results as stills (`npm run frames`, `npm run stills`) and send them with SendUserFile.

## House rules that outrank its defaults

1. **Owned voice.** Its default narration is Kokoro, a stock voice. For anything that could be published, speech comes only from ElevenLabs with Tee's clone `TEE_CLONE` in `services/devon/show_registry.py`. Make the take elsewhere and use `"voice": {"provider": "recorded"}` with `voice/voice.json`, or its ElevenLabs provider with that exact voice id. After every call read the voice id on the result and discard the audio unless it equals `TEE_CLONE`. Kokoro is acceptable only for a scratch timing pass that is deleted before the session ends. Never create a voice clone at any vendor. TSWS characters are voiced by Tee and his wife from recordings.
2. **Owned likeness.** Footage is Tee's own take. Never a third party's face, and its reference-style feature (`npm run style -- from <url>`) studies colours, type and pace only; never reuse another creator's footage, audio, graphics or words.
3. **No paid call without Tee's yes, on a card.** The ElevenLabs provider and the `generate` skill (kie.ai) spend money. Name the tool, the model and the price first.
4. **Nothing posts until Tee has watched it end to end.** Its `post-scheduler` skill publishes through Blotato. Posting is outward and needs Tee's answer on a card for the accounts, caption and time, after he has watched the final. Blotato's subscription read as expired on 2026-11-26, so that path is closed until he renews it. AI disclosure is set at publish and is Tee's call for each piece.
5. **Keys.** Never ask for or accept a key in chat. Writing any key into upstream's `.env.local` is Tee's ruling.
6. **Invented numbers.** Upstream allows made-up figures when asked. For TQO, NCO Forge and TSWS, no invented figure ships.
7. **Time gate.** A render still running after 30 minutes is stopped and reported. After three failed renders of the same piece, stop and ask.

## What leaves the machine

With no key set, upstream's setup contacts github.com, media.githubusercontent.com, huggingface.co and the npm registry, and uv contacts PyPI. Its footage and style tools can call a video host when given a URL. With a key, `pipeline/voice_elevenlabs.py` sends each narrated line to api.elevenlabs.io. Its dashboard binds 127.0.0.1 and refuses non-local origins (`dashboard/serve.mjs`). This list comes from searches over the pinned commit, not a line by line read.

## Syncing a newer upstream

Change `PIN` in the installer and the commit named above, install into a new `CONTENTSKILLS_HOME` because the installer refuses a checkout at another commit, re-read `AGENTS.md`, `pipeline/setup.mjs` and the posting and generate skills for new network behaviour, and re-measure.
