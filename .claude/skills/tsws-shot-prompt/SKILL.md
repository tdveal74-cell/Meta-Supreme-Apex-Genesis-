---
name: tsws-shot-prompt
description: Write, run and judge a generation prompt for a The Shadow We Share (TSWS) shot on WaveSpeed, its AI Cinema Studio or the WaveSpeed connector, using Tee's AI realism guide and the live canon on Drive. Load when Tee asks for a TSWS prompt, a Cinema Studio prompt, a start or end frame, or a regenerated Episode shot (the regeneration list, SH020, SH070, SH100 and the other street shots). Compiled 2026-10-30 from the SH020 job, two fresh critics and the measured failures below.
---

# TSWS shot prompts

How to turn one TSWS shot into prompts that a generator can run and a reviewer can check, without inventing canon. The canon itself is not in this file. It lives on Drive and changes by dated ruling, so every run starts by reading it. This file holds the method and what was measured the first time it ran.

## Read the canon first, every time

The precedence rule from Visual Bible v2.11 governs: newest filed ruling first, then skill, data stores, packages, and the bible last. Older production books on Drive still carry superseded directions, so check every source's date before using a line from it. A real contradiction goes to Tee on an `AskUserQuestion` card. Never resolve one yourself.

| Source | Drive id | What it gives |
|---|---|---|
| Realism guide, `CAPTURE_2026-09-26_codex_tsws-visual-control-menu.md` | `1Opb4F6eKKTtwNYEAc5gLQaJVUHQbxnsW` | the standing realism rules, the QC gate, the six shot-brief questions, the controls menu, one-variable retests |
| Production Prompt Book, `BOOK_02_EDITABLE.md` | `1regQDiW5ZgDj4lMCM972LS8B51lf6OAI` | P41 (the copy-paste realism block for stills), P43 (environment realism), P39 (adapt a prompt to the live tool schema) |
| Canon folder `00_CANON` | `1IRamTK0jDCgT0W8LMgsUntAsxR4oTERO` | dated rulings, Visual Bible, Series Bible, merged decision log; search it for anything newer than the files named here |
| Character and mask ruling of 2026-10-25, `TSWS_Auren_Vespera_Character_Sheets_MASTER_v1.4_2026-10-25.md` | `1Z4WP5FmTSzIWwtblaZUbAFCaucdvCrL4` | the governing mask design for the leads and the street crowd as of 2026-10-30 |
| Rulings of 2026-10-30, `TSWS_RULINGS_2026-10-30_street-plate-exception_SH070-stopper.md` | `1qLI0fubMTscx_9NoPoItrU8EQ0Q9gzPe` | the street-plate exception to R27 and R26, G01 as the SH070 stopper, the scarf pedestrian's hair |
| Episode 1 long-form shot manifest | `1Bb9kIZ9tXpD4PGmA6-yx2F9RRjSe503fqfW5HXHNO34` | beats, the seven unresolved parent shots, editor verdicts, measured defects, the pending rulings queue |
| Street generation proposal, `STREET_GENERATION_JOB_PROPOSAL_NOT_SUBMITTED.json` | `1Emk3fuD08FzNoV5VNKSylkgKw3y9MRNN` | the chained start and end frame design for SH020, SH070 and SH100. Its mask and stopper wording is superseded |

Two boundaries come from the `shadow-we-share-brand` skill and the rulings. The living mark and the soul plates are never generated; static mark exports are frames of the p5 mark. Auren and Vespera appear only through their approved identity references, never from a text description.

## The method

1. **Pick the shot from the record, not from memory.** The manifest names each shot's editor verdict and logged defects. Start there and quote the exact cue.
2. **Get the native master and verify it.** The Drive connector refuses downloads over 10 MB. A larger master downloads only while it is link-shared, which Tee switches by hand in the Drive app. Check the sha256 against the editor's record. Afterwards, ask Tee to set it back to Restricted, then read back both its permissions and an unsigned download. On 2026-10-30 the SH020 and SH150 masters were found still open to anyone with the link, left that way since 2026-10-16.
3. **Look at the frames person by person.** Extract the first and last frames at native size plus a contact sheet across the take. Write a table of every visible person: what they carry at each end and what they need. Note who leaves or enters the frame. The SH020 table found what the editor's notes did not. Masks appeared partway through the take, one pedestrian's hair changed style, and walkers seen from behind entered at the right edge.
4. **Answer the guide's six questions, then choose three to five controls.** Write the stills prompt as five to ten decisive instructions. Append P41 to stills only, never to motion prompts. Where a shot has no gold thread, replace P41's last sentence, "Keep the specified mask and thread state.", with a sentence naming the mask state.
5. **Write the motion prompt to match its own endpoints.** Give one action and the camera behaviour. Name who leaves frame and who enters, and say that nobody appears or vanishes inside the frame. A prompt that says "no new people" while the closing frame holds people the opening frame does not invites a first-and-last-frame model to morph them in.
6. **Keep the locked camera.** The Episode 1 street shots share one locked camera, with skyline registration within 0.5 px at every cut. A street shot generated from text alone breaks continuity with its neighbours. Generate stills from the native frames and animate between them.
7. **Make the end frame first.** The end still is also the next shot's start frame. Pin anyone who also appears in the downstream approved frame to that frame's mask and hair. Then make the start still from the native first frame.
8. **Give the start still a head sheet, not the end still.** Crop the masked heads from the accepted end still onto a neutral grey sheet. Pass that as the second image, with one sentence saying it is a sheet of reference heads and not a scene.
9. **Check every still before any video runs.** See "Checking a still" below. If one check fails, repair that defect, and re-run only with Tee's approval: one corrective submission per shot, with a materially different approach.
10. **Save what was submitted.** Keep each submitted prompt verbatim, plus the prediction id, the output sha256 and the price.

## Checking a still

`scripts/align_still.py` does the measuring. It needs OpenCV, which this repository does not pin, so run it from a throwaway virtual environment in the scratchpad, never the project's own. It prints registration in three static regions before and after an affine alignment, writes the aligned still, and draws a change map. Pass `--boxes` to measure how far given people moved.

- **Size.** Nano Banana Pro edit at 2K returned 2752x1536 on every run on 2026-10-30, about 0.8% wider than 16:9. A plain resize to 1920x1080 left the skyline 2.85 to 3.03 px off vertically. An affine alignment brought every static region within 0.33 px. Never stretch blindly; align, then measure.
- **People.** The end still's edit moved bodies by about 8 to 19 px while the background stayed within 0.2 px. Pasting new heads onto native bodies would then leave neck seams. Composite heads back onto the native frame only when the bodies sit within about 1 px; otherwise keep the aligned full render and record why.
- **Added and removed people.** Compare the edges of the frame as well as the subjects. The SH020 end-still edit dropped two walkers seen from behind and added a background man by the lobby. People with no visible face can be restored from native pixels along a minimum-difference seam, with no paid run.
- **Masks.** Every visible face is masked, and no superseded design remains. Each person shared by both stills wears the same mask in both, and no two people wear the same one. At 4x zoom, a small dark eye mask can read as sunglasses; flag it rather than pass it.
- **Realism gate.** Reject or mark pending on skin smoothing, anatomy drift, invented or sterile environment detail, implausible reflections or shadows, staged gaze, changing proportions, or mask or mouth instability.

## WaveSpeed and Cinema Studio

- **Cinema Studio is a website feature only.** No API, command line or MCP route reaches it, checked 2026-10-30 against the docs, `llms.txt`, the CLI 0.4.24 source and the connector's tools. It runs ordinary catalog models (Seedance 2.5 and 2.0, Wan 3.0, Kling 4.0, MiniMax H3) and writes director-panel choices into the prompt on WaveSpeed's servers. The preset text never reaches the browser, so a run with presets cannot be saved verbatim. Leave the panel cards on Auto, turn Enhance off and write the camera direction into the prompt.
- **First and last frames.** The Kling 4.0 API (`kwaivgi/kling-v4.0/image-to-video`) takes `image` and `last_image`, 3 to 30 s, 720p or 1080p. Whether the Cinema Studio composer shows a last-frame slot was unverified on 2026-10-30. If it does not, run the same prompt on the model page or through the connector.
- **Audio.** Set it off where the tool allows, and strip it before placement regardless. Conform to the 30 fps timeline.
- **Price before every run.** `get_price` and `estimate_only` are free. Quotes on 2026-10-30, at the discounted rate with list in brackets: Nano Banana Pro edit at 2K, $0.126 ($0.14). Kling 4.0 at 8 s, 1080p, first and last frame, $1.504 ($1.88); at 720p, $1.005 ($1.256). Seedance 2.5, same shot, no audio, $6.48 ($7.20). Re-quote; never reuse these.
- **Never resubmit a run that timed out on the client.** The run keeps going on the server; poll it with `get_prediction` and a wait under 60 s, since the connector times out at 60 s.

## Measured failures, with receipts

| Date | What happened | Receipt |
|---|---|---|
| 2026-10-30 | The start still was edited with the full end still as its second image. The model copied the end still's layout: the scarf pedestrian came out at foreground size, and the beige-coat pedestrian and the midground were removed. | prediction `85746d6cc07d4edfb6aeb45eb61e929d` |
| 2026-10-30 | The retry with a head sheet as the second image held every person within 0.2 px of native. | prediction `a4b1e94aa291419fbea2d5821946f6fe` |
| 2026-10-30 | The end-still edit dropped two walkers seen from behind at the right edge. They were restored from native pixels along a seam at x 1668 to 1711. | prediction `0f2d81b163fb4bfb8e2c5c68a73b3df2` |
| 2026-10-30 | A test frame made on 2026-10-23, before the Venetian ruling, carried lower-face cloth masks, which the 2026-10-25 ruling bans. Do not reuse earlier test frames without checking them against the current ruling. | `TSWS_E01_SH020_startframe_image_TEST_20261023.jpg` |

## Still unverified

- Cinema Studio's Image-mode model list and its Kling 4.0 last-frame slot.
- Whether Cinema Studio's "prompt sent to the model" view shows the expanded preset text after a run.
- Which pedestrian in the SH020 end still is G01.
- How the 2026-10-30 SH020 stills animate. Step 2 had not run when this file was written.
