# Upstream provenance

`watch` is third-party work vendored into this repository. Nothing under this
directory is ours except this file and `MANIFEST.sha256`, and nothing else
here is edited in place. Fixes go upstream. `test_vendored_skills.py` enforces
that: every file below is hashed into `MANIFEST.sha256`, and a local edit fails
the suite rather than surviving as a silent fork.

| | |
| --- | --- |
| Upstream | https://github.com/bradautomates/claude-video |
| Author | Bradley Bonanno |
| Licence | MIT, see `LICENSE` in this directory |
| Plugin version | 0.3.2 (`.claude-plugin/plugin.json` at the commit below) |
| Vendored commit | `03ceb42f7fa2c4439aca01752118044baabffb8f` |
| Commit date | 2026-09-25 |
| Vendored on | 2026-10-28 |
| Upstream path | `skills/watch/` |

The copy is byte identical to that upstream path at that commit, plus this
file, `MANIFEST.sha256`, and a copy of the upstream repository root `LICENSE`
(the skill folder itself carries none). The commit is upstream `main` and
`HEAD` on the day it was vendored, read with `git ls-remote`, and it is
exactly `v0.3.2`: that tag is an annotated tag object
(`280a6e62498f3c8af797f029ace7a5a6e4d20a91`) that peels to this commit. The
first draft of this file read the tag's own sha off `ls-remote` and called it
"one commit behind"; a critic peeled it. Read `refs/tags/v0.3.2^{}`, not
`refs/tags/v0.3.2`, when checking this again.

## Why it is here

Tee sent a 56 second screen recording on 2026-10-28
(`ScreenRecording_10-26-2026 01-19-43_1.mp4` in his Drive) and asked for the
skills in it installed. The recording is a YouTube Short by `@felixhmohr`,
"Teach Claude Code any skill from YouTube". Every frame was read; it names
three things, and only one of them is a package:

1. this repository, `bradautomates/claude-video`, the `/watch` skill;
2. a free Gemini API key from Google AI Studio, so Gemini watches the video
   natively;
3. a workflow: have Claude read the frames and transcript, have Gemini watch
   the video, merge both reads into a `SPEC.md`, and turn the spec into a
   skill. That is a way of working, not a thing to install.

The Short's own voiceover was not transcribed here: no speech model is in the
cloud image and the captions burned into every frame carry the full script.

## What was and was not copied

Copied: `skills/watch/` whole, which is `SKILL.md`, ten Python scripts under
`scripts/`, the dev-only `scripts/build-skill.sh`, `.skillignore` and
`.gitattributes`. Not copied: the plugin's `hooks/hooks.json` and
`hooks/scripts/check-setup.sh`, a `SessionStart` hook that runs `setup.py
--check` on every session start and prints an advisory line. That hook belongs
to the plugin wrapper, not the skill, and `.claude/settings.json` is where
this repository decides what runs at session start. Also not copied: the
upstream tests, README, CHANGELOG, and the Codex and marketplace metadata.

## Why vendored rather than installed as a plugin

Upstream's own README says the interactive `/plugin` installer is unavailable
in Claude Code on the web, and that in a cloud environment the Gemini key does
not persist between tasks. A plugin install lands under `$HOME`, which is in
the ephemeral container. A skill committed under `.claude/skills/` is part of
the checkout and loads in every session. This is the same reasoning
`.claude/skills/hypit/UPSTREAM.md` and `.claude/skills/typesafe-ai/UPSTREAM.md`
record.

Do not also run `claude plugin marketplace add bradautomates/claude-video`
and `claude plugin install watch@claude-video` in a session that has this
checkout. The plugin carries the same `watch` skill name and would load beside
this one, and it would also install the session start hook.

## What it runs, read before it was vendored

The scripts were read in full. They were not executed in the cloud session
that vendored them: the permission classifier refused to run downloaded code,
and nothing below depends on having run it.

- `setup.py` is a wizard. It writes `~/.config/watch/.env` (mode 0600 on
  POSIX), looks for `ffmpeg`, `ffprobe` and `yt-dlp` with `shutil.which`, and
  on macOS offers to install them through Homebrew. Keys are read from the
  environment first, then that file, then `.env` in the current directory
  (`config.py` lines 103 and 116), so a `GEMINI_API_KEY` in a repo-root
  `.env` is picked up silently; that file is gitignored here.
  `SKILL.md` also offers to take the key pasted in chat. Do not take that
  route in this estate: the gate ledger hook reads every session transcript,
  and a key pasted in chat lands in it. An environment secret, Tee's to set,
  is the only placement that survives a cloud container and stays out of
  the transcript. With `--backend whisperx`
  it downloads `uv` from `astral.sh`, builds a Python 3.12 environment under
  `~/.cache/watch/whisperx-venv`, and pulls CPU PyTorch wheels and about
  1.5 GB of models from PyPI and Hugging Face. None of that happens without
  that flag.
- `watch.py` is the entry point. Local engine: `download.py` runs `yt-dlp`
  against the source site, `frames.py` runs `ffmpeg` for scene or keyframe
  extraction, `transcribe.py` reads native captions first and falls back to
  `whisper.py` (Groq at `api.groq.com` or OpenAI at `api.openai.com`, mono
  16 kHz MP3 upload, keys from the env file) or `local_whisperx.py`.
- `gemini.py` is the other engine: the YouTube URL, or an uploaded copy of a
  local file, goes to `generativelanguage.googleapis.com` with
  `GEMINI_API_KEY` as a request header, default model `gemini-3.7-flash`, and
  the upload is deleted after the answer. `SKILL.md` says, and the code
  agrees, that the engine never switches on its own: a Gemini failure is
  reported and the user chooses whether to rerun with `--engine local`.
- `config.py` and `runtime.py` are shared parsing and subprocess helpers. The
  base runtime imports only the standard library.

Hosts it can contact, by the user's choice at setup: the video's source site
through `yt-dlp`; `generativelanguage.googleapis.com`; `api.groq.com`;
`api.openai.com`; `astral.sh`, `download.pytorch.org`, PyPI and Hugging Face
for the WhisperX install. Nothing is contacted by loading the skill.

The MIT licence puts no condition on our use beyond carrying the notice,
which `LICENSE` here does.

## What the cloud image has, measured 2026-10-28

`python3` 3.13.17 and `ffmpeg` at `/usr/bin/ffmpeg` are present. `yt-dlp` and
Deno are not, so the local engine cannot fetch a URL from a cloud session
until they are installed there, and upstream's README says most sites block
`yt-dlp` from that kind of environment anyway. A local file already in the
container works with `ffmpeg` alone. The Gemini engine needs only the key for
a YouTube URL. That key is Tee's to set, and in a cloud session the env file
it lives in is gone when the container is reclaimed.

## House lint

`python3 -m ruff check --statistics` under this repository's `ruff.toml`
reports 23 findings in `scripts/`: 12 E702, 5 I001, 3 B904, 3 B905. They are upstream's
style, not defects we can touch, so `ruff.toml` carries
`extend-exclude = [".claude/skills/watch"]`. `SKILL.md` also contains six em
or en dashes; the house dash ban is enforced on `services/devon` and
`docs/devon` only, and a vendored file is not edited for it.

## Syncing a newer upstream

```bash
git clone --depth 1 https://github.com/bradautomates/claude-video.git /tmp/claude-video
rm -rf .claude/skills/watch
mkdir -p .claude/skills/watch
cp -R /tmp/claude-video/skills/watch/. .claude/skills/watch/
cp /tmp/claude-video/LICENSE .claude/skills/watch/LICENSE
```

Restore this file, update the commit, version and date rows above, re-read
the licence for changes, re-read `SKILL.md` and the scripts for new network
or install behaviour, then regenerate the manifest the drift check reads:

```bash
python3 - <<'PY'
import hashlib, pathlib
root = pathlib.Path(".claude/skills/watch")
ours = {"UPSTREAM.md", "MANIFEST.sha256"}
lines = [
    f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(root).as_posix()}"
    for f in sorted(p for p in root.rglob("*") if p.is_file())
    if f.relative_to(root).as_posix() not in ours
]
(root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
PY
python3 -m pytest -q test_vendored_skills.py
```
