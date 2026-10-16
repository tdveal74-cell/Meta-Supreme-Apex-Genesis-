# Owned presenter pipeline, checkpoint

Written 2026-10-16 as a checkpoint, not a close. Tee ruled on a card to file the session's work now and close the arc after he has watched the first render. Everything below that is marked unverified stays so until that render.

## Rulings

Tee ruled on inline cards on 2026-10-15 and 2026-10-16:
- Own the whole stack, and build the full personal pipeline: script in, his cloned voice and avatar out, one finished video, on open models. He chose this over proving a render first and over building a product to sell.
- Rent the GPU. The Runpod agent provisioned one L40S on Secure Cloud in US-TX-3 after the RTX 4090, A5000, L40S and A40 were all unavailable on Community Cloud.
- The code lives in a new private repo, `tdveal74-cell/presenter-pipeline`, separate from this one.
- Runpod's MCP write tools sit behind the 30-minute outward gate. Shipped as PR #349, merged as main daaa7c9.
- In the presenter-pipeline repo, Desktop Commander runs without prompts, with the gate copied in.
- Install the model weights now and stop the pod until his clips are recorded.
- Checkpoint now, close the arc after the first render.

## Findings

The HeyGen teardown verdict is DON'T BUILD, and the critic's six findings on it were fixed:
- What HeyGen runs on does not move to one person: a self-reported 30M users and a $60M Series A at a $500M valuation (aggregator figures, unverified).
- The only portable mechanism is a done-for-you service, which is the Enhancor-derived service already in its 30-day test.
- A first draft understated a credit range. 3 to 4 videos of 8 to 12 minutes at 20 credits a minute is 480 to 960 credits, not 480 to 720.

Open-model licences for a monetized pipeline, read 2026-10-16:
- Chatterbox and OpenVoice are MIT, by web search of their READMEs; their LICENSE files are not yet read.
- MuseTalk's own LICENSE file on the pod reads MIT. Its components (Whisper, DWPose, S3FD, ft-mse-vae) are unchecked, so the pipeline's licence gate stays shut for release renders.
- Wav2Lip's README forbids commercial use because of its LRS2 training data. The code keeps it out by allowing musetalk as the only face engine.
- SadTalker and LivePortrait are uncleared and not wired.

The render VPS, srv1936199, has no GPU: 2 vCPU and 7.8 GB RAM, measured 2026-10-15.

The pipeline repo has four commits on main:
1. 0458973 is the v0.1 scaffold. A worktree critic found six defects in it, and all were fixed and re-measured, 12 of 12 functional checks. The worst was a clean unwatermarked copy left on disk beside a test render.
2. 9e522f1 runs setup without sudo when already root.
3. e379933 wires both model stages to their real interfaces. Read on the pod, both v0.1 guesses were wrong:
   - Chatterbox has no command line interface, only a Python API.
   - MuseTalk takes its inputs from a task YAML rather than flags.

   The chunker was tested here: every word survives in order, no chunk over 300 characters. The MuseTalk wrapper was tested against a fake MuseTalk and leaves no clean frames.
4. 827979f adds the allow rule and a byte-identical copy of `gate_ledger.py`. Run as a process from that repo, it denies `start_process` and `create-pod` 45 minutes after a human message, allows them 1 minute after, and always passes `read_file`.

The pod reaches the private repo through a git bundle carried over the VPS, because the session cannot create deploy keys: the API path is refused by the proxy.

Install state on the pod at 01:53Z:
- The Chatterbox venv works: torch 2.6.0+cu124 with CUDA available, and its weights load at 24 kHz.
- The MuseTalk venv stopped at mmpose. Its dependency `chumpy` failed to build because its setup.py imports pip, which the isolated build environment lacks. A resume that builds `chumpy` without build isolation was launched at 01:53Z, and its result is not yet read.

## Open

- **MuseTalk install:** read `/workspace/install_resume.log` for `MT_IMPORT_OK` and `ALL_DONE`.
- **Pipeline sync:** the pod still holds commit 9e522f1. Sync e379933 and 827979f onto it.
- **Voice smoke test:** run the voice stage on real weights with Chatterbox's default voice, using no identity.
- **Tee's inputs:**
  - a 30 to 60 second base clip, recorded neutral to camera
  - a 30 to 60 second voice sample
  - the filled consent record
- **First render:** produce the first watermarked test render and have Tee watch it end to end. That is the gate for closing this arc.
- **MuseTalk components:** check their licences before any release render.
- **Runpod connector:** add Runpod as a claude.ai connector. In-session OAuth is not available in a cloud session.

Unverified:
- The two model wrappers have not yet run end to end on real weights.
- The 20 to 40 minute install estimate was never measured.
- The HeyGen pricing figures come from third-party guides, because heygen.com was unreachable from here.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_owned-presenter-pipeline_v1_2026-10-16-0153.md
DATE: 2026-10-16
DECISIONS: Tee ruled on cards on 2026-10-15 and 2026-10-16: own the whole stack and build the full personal presenter pipeline on open models; rent the GPU, an L40S on Runpod Secure Cloud; keep the code in a new private repo, tdveal74-cell/presenter-pipeline; gate Runpod writes behind the 30-minute ledger, merged as PR #349 at daaa7c9; allow Desktop Commander in the new repo with the gate copied in; install weights now; file this checkpoint and close the arc after the first render.
FINDINGS: HeyGen is DON'T BUILD, and its only portable mechanism is the Enhancor-derived service already in test. Chatterbox, OpenVoice and MuseTalk's own code are MIT, Wav2Lip is excluded for commercial use, and MuseTalk's components are unchecked. Both v0.1 model wrappers guessed wrong interfaces and are rewired in e379933. The Chatterbox venv and weights work on the pod, and the MuseTalk venv stopped at the chumpy build, now resuming.
OPEN: Read the MuseTalk resume log; sync e379933 and 827979f to the pod; run a default-voice smoke test; Tee records a base clip and voice sample and fills the consent record; first watermarked render watched end to end by Tee; MuseTalk component licences; Runpod as a claude.ai connector.
STATUS: Pipeline code is on the pod and the voice stage is installed. Nothing has rendered yet, and the arc stays open until Tee watches the first render.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
