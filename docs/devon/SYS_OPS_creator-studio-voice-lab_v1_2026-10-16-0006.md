# The creator studio layer, and the Voice Lab ship lane

Written 2026-10-16. It covers one session that started from a screen recording Tee put on Drive on 2026-10-15. It records the analysis, his two rulings, and what was built and measured for the first lane.

## The recording

The file is `ScreenRecording_10-15-2026 18-05-35_1.mp4` (Drive id 1P5ZSnYNKL4o2n4WnTSr08HIRbOPAx6re), 95.7 s of iPhone screen capture at 1180x2556. It shows the @restructureai Short "I Built an Entire AI Creator Studio With 0 Employees", which is co-branded with ElevenLabs.

It was read from 48 frames, one every 2 s, plus 12 full-resolution crops. The audio was not transcribed, because no speech model could be downloaded here, so the narration is known only from the burned-in captions.

Getting the file took one environment change. The network policy refused `drive.google.com` and `drive.usercontent.google.com`, and the Drive connector returns content only as inline base64, which a 152.7 MB file cannot fit through. Tee added both hosts under Allowed domains, and they took effect in the same session.

The video shows eight modules around one person:
- ideas and research;
- script and story;
- a Voice Lab, where the real take is kept and the clone re-reads flubbed lines;
- video and visuals through Higgsfield and Descript;
- global dubbing into ten languages;
- repurposing and posting at local time;
- an AI sales line on ElevenLabs Agents with Stripe and Cal.com;
- a data dashboard with a 7:00 brief.

Its revenue and view figures are mockup screens in a sponsored post. They are unverified, and they are not evidence.

## Rulings

Tee ruled on inline cards on 2026-10-15:
- The studio is incorporated as a layer on the shared engine. It is not a second studio.
- The Voice Lab ship lane is built first.

The case for building it first is in the repo. There have been 0 YouTube publishes since 2026-09-03. Presenter render cannot run on live V5, and the HeyGen lane is unfunded. Voice Lab routes around both: his real take is the base track, and the clone fills only the lines he flubbed.

## Gaps the video skips, carried here as gates

- An AI disclosure flag on every upload that carries clone audio. The sales agent also says it is an AI.
- His own voice and likeness only. The video's "Maya Cole" is a stock persona.
- A human watches the finished cut end to end.
- New lanes sit under the provider watchdog.
- A cost line for metered tools.
- A rights check on music and B-roll before dubbing.

## What was built

The render worker gained four things, in `deploy/render-worker/jobs.js`.

`align_script` lines the script up against word-timed speech to text.
- It keeps a reading only when it says the line verbatim.
- It chooses readings with a dynamic program that keeps the most script words in order. On a tie, the later reading wins.
- It returns `rerecord` with no edl when over 30 percent of lines are patched.

`take_patch` splices the take with the clone audio over a held frame.
- It renders one ffmpeg run per segment and joins them with the concat demuxer as a stream copy.
- It requires `take_duration`, and refuses spans past it or out of time order.
- It snaps every segment to whole frames on both tracks.
- It takes `width` and `height` so that segments are cut at the presenter canvas before the tonemap.
- It has no default for `hdr`.

`presenter_composite` gained `must_cover`.
- It refuses at submit when a clone window is not inside one opaque cutaway.
- It lays a black plate under each window, so a cutaway with no frames shows black and never his face.

`probe` now reports `pix_fmt`, `color_transfer` and `hdr`.

## Findings

Every number here was measured in the session container, with ffmpeg 6.1.1.

**The single-run `take_patch` would have killed the VPS.** On a 40 s 4K HEVC HLG take, 64 items as seeked inputs peaked at 13.6 GiB and died. The box has 7.8 GiB. Segmented, the same 64 items peaked at 1,068 MiB, and the output measured 736 frames against 736 planned. 256 items peaked at 1,427 MiB, with 2,944 frames against 2,944 planned.

**The first acceptance run found an A/V drift.** Video rounded to the frame and audio did not, so each splice added 13 ms. Every builder test was green while it happened. Segments are now whole frames. The acceptance script fails at frame 76 against a copy without that snapping, so it is a real negative control.

**A fresh critic quarantined the first commit, d535cf3.** Its blocker was that `align_script` kept readings one word off the script, for example "forty percent" against a script line saying thirty. Its other findings:
- the 64-item cap;
- 198 s of event-loop blocking;
- spans past the file end;
- an empty cutaway showing the face;
- out-of-order spans;
- greedy placement;
- a lip-sync lag of +28.4 ms after a seek.

All of these were fixed in a637d8f. The lag now lands within half a frame: -5.0, +9.4 and -10.6 ms against a -4.0 ms source. Left as a documented caller contract: an understated patch `duration` is honoured. The n8n lane must take it from `probe`.

**Digits never match number words.** ElevenLabs speech to text writes numbers as words, so a script line written with digits always goes to the clone. TQO scripts should write numbers as words for lines the take should keep.

The suites at a637d8f:
- `jobs.test.js`: 90 passed.
- `server.test.js`: 46 passed.
- The negative control holds.
- `voice-lab-acceptance.js`: 11 passed, with real ffmpeg.

None of it has run on the VPS.

## Shown to Tee

A private artifact, the studio map, holds the module ledger, the lane, the measurements and the build order: https://claude.ai/artifact/VJtHwKunUb42gMv4dyzSpZ

## Open

- A second fresh critic on a637d8f.
- Deploying the worker to the VPS, then running `voice-lab-acceptance.js` there and checking that `/health` reads 21 jobs.
- The `TQO Voice Lab` n8n workflow, as an unpublished draft. Creating it is a write to the live instance and goes on a card.
- One real episode end to end, watched by Tee.
- The consent record for the clone, and the YouTube altered content label rule.
- Later phases, each on its own card: wiring into V5, dubbing, local-time posting, the sales line, the 7:00 brief.

## DEVON RECEIPT

AREA: TQO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_creator-studio-voice-lab_v1_2026-10-16-0006.md
DATE: 2026-10-16
DECISIONS: Tee ruled on cards on 2026-10-15 to incorporate the one-person creator studio from the @restructureai Short as a layer on the shared engine rather than a separate studio, and to build the Voice Lab ship lane first. He added drive.google.com and drive.usercontent.google.com to the environment's allowed domains so the recording could be read.
FINDINGS: The video's eight modules map onto the estate with Voice Lab, dubbing and the AI sales line missing. A single-run take_patch peaked at 13.6 GiB on 64 items of 4K HEVC against a 7.8 GiB VPS; segmented, it peaked at 1,068 MiB with 736 of 736 frames. The first acceptance run found a 13 ms per-splice A/V drift that every builder test missed. A fresh critic quarantined d535cf3 because align_script kept off-script readings at 0.9 similarity; a637d8f keeps verbatim readings only. Digits never match number words.
OPEN: Second critic on a637d8f; VPS deploy and on-box acceptance; the n8n Voice Lab draft on a card; one real episode watched end to end; clone consent record and the YouTube label rule; later phases on their own cards.
STATUS: Render worker jobs built and measured in the container on branch claude/creator-studio-voice-lab; not deployed; nothing publishes.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
