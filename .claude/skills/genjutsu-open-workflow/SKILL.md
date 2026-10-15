---
name: genjutsu-open-workflow
description: Install, run or judge the Genjutsu Open Source Workflow (sirioberati/Genjustsu-Open-Source-Workflow, the TEIN persona-swap app that sends a depth or face-mesh video plus character references to Seedance through Enhancor). Load before entering any API key into it, before running it on footage of Tee or his wife, or when asked to set it up on a device. Compiled 2026-10-13 from a sandbox install at commit 40fd6615 and a read-only audit of every source file.
---

# Genjutsu Open Source Workflow

A local FastAPI app plus a command line. It separates the voice with Replicate Demucs, builds a depth or face-mesh version of the on-screen person (Replicate depth and SAM 3, or MediaPipe locally), uploads the composite and the character reference images to a public file host, asks Seedance 2.5 through Enhancor to replace the person with the supplied character, then puts the original soundtrack back packet for packet. MIT licence on code and docs only; the TEIN names, logos and example media are excluded.

## What was verified

Installed from the runbook in a Linux sandbox, every step as documented: 51 of 51 checksums OK, Rubber Band 3.3.0, cloudflared 2026.10.0, Python 3.13 main venv and a 3.12 face-mesh venv with mediapipe 1.1.0, both setup scripts exit 0, `doctor.py` and `doctor.py --mesh` report LOCAL UI READY and GENERATION BLOCKED with no keys, 13 unit tests pass without network, `test_composite.py` passes, the app serves on 127.0.0.1. The cloudflared quick tunnel could not open there because the sandbox cannot resolve `api.trycloudflare.com`; that is a sandbox limit, not a repo fault. The full command log is `GENJUTSU_SETUP_REPORT.md` beside the TSWS package on Drive.

It needs macOS or Linux with Python 3.12 or newer, Rubber Band, cloudflared and two API keys. An iPhone cannot run it. The two devices registered to the Desktop Commander connector (penguin, srv1936199) were both offline when probed; nothing is known about their OS or tools and nothing was installed on them.

## Before any key goes in

As shipped, with the default hosts, it publishes a copy of Tee's voice and in one mode his face. That conflicts with the owned-voice rule and with the no-paid-generation boundary. The order of changes, all small, before a first real run:

1. Replace `media_host.upload` with a private signed-URL uploader (`docs/MEDIA-HOSTING.md:15` says how) and set `MEDIA_HOST_FALLBACKS` empty, so nothing goes to tmpfiles.org (6 hour expiry) or catbox.moe (never expires, never deleted).
2. Put a confirmation gate in front of every Replicate call. Preparation bills three times on one click (`app.py:13-33`, `pipeline.py:131-139`); `repair-rgb` bills SAM 3 again from the agent CLI with no gate (`workflow.py:41-45`); the Seedance draft gate is an artifact hash an agent can write itself (`mask_review.py:28`); HD is a second billed call.
3. Write a disclosure stamp on the output. Nothing in the pipeline adds a watermark or C2PA metadata, and `pass_faces` is sent true.

Only then decide whether the swap itself is inside "owned, never rented": the reference must be Tee's or his wife's own likeness under the recorded consent, and nothing in the code checks whose face it is.

## As installed on srv1936199 (2026-10-15)

The three changes above now exist as an overlay on commit 40fd661, not upstream and not in this repository: a private S3 uploader with no public fallback, a billing grant from `grant.py` that only a person at a terminal can issue and that every billed call spends, and a burned in disclosure stamp on the final preview. It runs as the Docker project `genjutsu` on 127.0.0.1:3500 of srv1936199, reached by SSH tunnel, with no keys. Tee ran the install himself in Termius. Still unset: `MEDIA_BUCKET`, a webhook URL, and the key custody decision. The grant is a file, so an agent running as the same user can forge one; the real controls are keys that no agent can read and, optionally, a root owned `GENJUTSU_GRANT_DIR` with `sudo grant.py`. An agent that hits GrantRequired stops and tells Tee. Details are in `docs/devon/SYS_OPS_tsws-editable-repair-workflows_v1_2026-10-14-2109.md`.

## What leaves the machine, by file

- The complete original soundtrack, un-pitched voice included, to Replicate for Demucs: `audio_workflow.py:27-43`.
- The isolated vocal stem pitched up three semitones, embedded in the composite, to tmpfiles then catbox then Seedance: `audio_workflow.py:88-104`, `media_host.py:12-25`, `seedance_bridge.py:16-21`. Pitch shifting is trivially reversible.
- In fast face-mesh mode the original RGB frames with mesh lines over the face: `mesh_worker.py:19-24`.
- Every character reference image or video: `app.py:49-57`, `seedance_bridge.py:19`.
- The runs folder keeps every public URL, the webhook capability URL and provider responses, and the app serves it on localhost: `app.py:84`.
- Google Fonts on every UI load; gradio_client telemetry to Hugging Face when that depth provider is chosen. Neither is disclosed in the repo.

Secrets: none in the repository. `.env` is created empty with mode 600 and is gitignored. Keys are read from the environment and sent only as headers to their own vendor. AGENTS.md and the bundled skill push an agent toward autonomy ("carry authorized jobs through without stopping"); with keys present and the gates above missing, that language is the real risk.

## Rules for a session that runs it

- Never enter or request a key in chat. The runbook forbids it and so do we.
- Never run `prepare`, `repair-rgb`, `submit` or HD on an agent's own initiative. Each is money or likeness leaving the machine.
- Treat `runs/` as confidential and never post an envelope or request JSON to a channel.
- A green `doctor.py` proves the install, not the privacy posture. Re-read the three changes above before calling it ready.
