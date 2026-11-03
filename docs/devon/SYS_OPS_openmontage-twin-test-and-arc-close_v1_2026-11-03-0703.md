# The twin test render and the close of the OpenMontage avatar arc

Status doc closing the arc that began with "Install this repo" on 2026-10-30 and ran through the install, the review, the daily audit, the photo-look avatar test and the digital twin. Written 2026-11-03 after Tee asked at 2026-11-01T18:41:33Z to close the arc before his usage ran out, or hand over to his Grok bot. The session's weekly limit cut two verifiers off at about 18:40Z on 2026-11-01, so this record names what was measured and what was not. It supersedes the Open section of `SYS_OPS_openmontage-avatar-lane-test_v1_2026-11-01-0036.md`.

## The twin

Tee filmed and submitted his digital twin in HeyGen's own app on 2026-11-01. Read through the HeyGen connector at 18:15Z: group `f94efc2551ae403fa8d7c60c1aa5d1d5` "Terrance Veal", consent accepted, status completed, eight looks. One is the filmed twin, look `56da7b2dced54d1082eecd2a16b54335`, portrait 720 by 1280. Seven are photo looks HeyGen generated around his face, five of them landscape 1920 by 1080. Creating the twin spent no plan credits: the balance read 297 before and after. HeyGen's API exposes no field for the heart he set in the app, so the looks went to him as a numbered sheet.

## The rulings

| when | card | answer |
|---|---|---|
| 18:22:14Z | which look he hearted | "All those": looks 3 to 7, the five landscape generated looks |
| 18:22:14Z | route for the test render | "Connector on your pick (Recommended)": the HeyGen connector on plan credits, OpenMontage composing; OpenMontage's own tool refuses Avatar V on a photo look (`tools/avatar/heygen_avatar.py` line 205) |
| 18:34:37Z | the chin after watching | "Clean, no seam" |
| 18:34:37Z | lips, voice and motion | "Yes, reads as me" |
| 18:34:37Z | next for the lane | "Make look 4 the TQO look (Recommended)" |
| 18:40:49Z | the voice in the render | "Re-voice and re-render (Recommended)" in his professional clone |
| 18:40:49Z | the repo's `TEE_CLONE` | "I port the one-line fix (Recommended)" |

Look 4 is `c89667ba7c474e2694bf18ffc035c604`, "Podcaster in grey hoodie": bookshelves, a mic on an arm, no plaque or logo seen at sheet size. Looks 3 and 7 show what reads as a YouTube play-button plaque on the wall, which would suggest an award the channel has not earned, so neither is fit for anything published without that removed.

## The render

Submitted through the connector at about 18:22Z: look 4, engine Avatar V with `reference_look_id` set to the filmed twin so HeyGen took the motion from Tee's own footage and not a stock look, audio from the existing asset `fe7cddfa91064f5a8d0bc468b11028c9`, 1080p, 16:9, titled "not for publish". HeyGen video `d3d37745814d8ed49449921c35c81a89`, completed at 18:26:59Z, 19.5 s at 25 fps. Cost 17 plan credits, 297 to 280, under the 20 credit ceiling. OpenMontage's `remotion_caption_burn` at `195eab2` then burned the 56 captions in 112 s. Both files went to Tee in chat.

Tee reported no sound. Measured: both files carry his take at -20.6 dB mean and -4.1 dB peak, each channel the same, and the mono sum cancels nothing; the raw clip's audio matches the take at correlation 0.99997 with zero offset. The earlier black-polo video and HeyGen's own player were silent for him too, so the phone was muted, not the files. HeyGen's raw clip puts its audio track before the video track, which the earlier files did not; a copy with the usual order was sent as well, unchanged in content.

## What the verifiers found

Five independent verifiers were sent at about 18:30Z on 2026-11-01. Three finished. Two, the seam and the identity checks, were refused by the weekly usage limit and never ran, so the chin seam on the twin render was judged by Tee's eye and one half-size frame pair only, and nothing checked the set for logos or the face against the twin at full size.

- Voice, pass: raw clip against the take, correlation 0.99995 at lag 0 with no drift; the composed file 2048 samples (42.667 ms) later, the same offset `remotion_caption_burn` added on 2026-11-01 to both photo-look renders. Levels within 0.05 dB of the take. Nothing in the pauses but codec noise.
- Captions, pass: 14 pages read from 195 frames equal the 56-word script in order, with its punctuation. The caption box sits at y 898 to 1012 of 1080 and the chin never comes below 525, so the face is clear by at least 370 px. The box does cover the hands and the mic cable at about 3.4 s, 9.6 s and 17.7 s.
- Lips in the pauses, fail: six silences found at -35 dB (3.89 to 4.42, 8.22 to 8.68, 11.45 to 12.07, 15.55 to 16.29, 17.18 to 17.57, 18.82 to 19.52 s). The lips close for the whole of the last one and for 1 to 3 frames at the end of three others; at 17.18 to 17.57 s they never close, with tongue and teeth visible. The black-polo Avatar V render showed the same pattern, wider. Tee saw it as reading like him; the verifier's frame-by-frame read says the fault is milder, not gone.

## The voice

The take in every render, `AK73i51Ci41B4WfAQTrE` from 2026-10-31, is voice `ypnKDQtIhp4N3yn4UnqO`, which ElevenLabs lists as "T Veal 2.1", category generated: a voice designed from a written description, not a clone of Tee. His trained clone is `LLhnFOCTr3y3wrH59DtJ` "T Veal", category professional, read through the ElevenLabs connector at 18:35Z. The 2026-10-31 canon already recorded the move to the professional clone; this session's OpenMontage skill and `show_registry.py` still named the designed voice, so the test followed them. Tee ruled the re-voice at 18:40:49Z. A price check at 18:3xZ gave 268 credits, 4.9 cents, for one take; nothing was generated.

The one-line port is moot. PR #460 merged at 2026-11-01T19:00:17Z as `206c3fd`, and `services/devon/show_registry.py` line 99 on `main` now reads `TEE_CLONE = "LLhnFOCTr3y3wrH59DtJ"`, with the deploy copy matching.

## Deploy read-back for bbc8b05

PR #475 merged as `bbc8b05` at about 18:23Z. Railway `api` and `scheduler-cron` each took it (deployments `5cfc75fd` and `4127b13a`) and were superseded the same hour by `eb9a36a` (PR #322) and then `206c3fd` (PR #460); `presence` skipped it, correctly, since no watched path changed. At 2026-11-03T07:03Z all three services read SUCCESS on `206c3fd` and `/api/v1/health` answered 200.

## Open

- The re-voice and re-render: one take of the 56-word line in `LLhnFOCTr3y3wrH59DtJ` (about 268 ElevenLabs credits), uploaded to HeyGen as a WAV, then one Avatar V render on look 4 with the twin as reference (about 17 plan credits, ceiling 20), then captions, then Tee listens. Not run: the usage limit came first.
- The seam and identity checks on the twin render at full size, which never ran.
- The lips in pauses, which HeyGen leaves open on both photo looks and on the twin-referenced render. Untested: a render on the filmed twin itself (look 1) through OpenMontage's own tool, on API credits, with the $3 ceiling of 17:34:04Z and the wallet fix of 17:57:17Z still pending.
- Publishing anything with look 4 needs Tee watching end to end, the C4 disclosure line and YouTube's altered or synthetic content label, as the 2026-10-31 canon records.
- The HeyGen skills install is recorded in `SYS_OPS_heygen-skills-install_v1_2026-11-03-0703.md`.

## Handover for the Grok bot

If this continues on another platform, these are the facts it needs: the TQO face is HeyGen look `c89667ba7c474e2694bf18ffc035c604` rendered on Avatar V with `reference_look_id` `56da7b2dced54d1082eecd2a16b54335`; the voice is ElevenLabs `LLhnFOCTr3y3wrH59DtJ` and never `ypnKDQtIhp4N3yn4UnqO`; every paid call goes to Tee on a card with its cost and which balance pays, plan credits through the HeyGen connector or API dollars through his key; nothing publishes until he watches it; the test script is the 56 words above and the test audio asset is `fe7cddfa91064f5a8d0bc468b11028c9`, which carries the wrong voice and is replaced by the re-voice.

## Gauntlet verdict

VERDICT: PASS-WITH-CONDITIONS
Deliverable: the twin test render, Tee's rulings on it, and this close-out record
Scores: correctness 4, scope 4, verification 3, security 5, reversibility 5, failure handling 4, idempotency 5, traceability 5, observability 4, completeness 3, maintainability 4 | mean 4.2 | flagship bar: met as a test, missed for publish (wrong voice, lips open in pauses)
Conditions: the re-voice and re-render, and the two verifiers that never ran. Verification is 3 because two of five verifiers were refused by the usage limit and no fresh critic read this record.
Recommendation: next session runs the re-voice and re-render under the ceilings above, then a fresh critic on this record. The human owns SHIP.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_openmontage-twin-test-and-arc-close_v1_2026-11-03-0703.md
DATE: 2026-11-03
DECISIONS: On 2026-11-01 Tee hearted looks 3 to 7 of his twin's group, chose the connector route for the test render, judged the look 4 render clean on the chin and reading as him, made look 4 the TQO look, ruled the render re-voiced in his professional clone, and chose to port the TEE_CLONE fix, which PR #460 then landed.
FINDINGS: The look 4 render on Avatar V with the filmed twin as motion reference cost 17 plan credits and shows no chin seam at phone size. Verifiers confirmed the voice track and the captions; the lips still open in the pauses, milder than on the photo looks. Every render so far spoke in the designed voice T Veal 2.1, not Tee's clone. Two verifiers were refused by the usage limit.
OPEN: the re-voice and re-render; the seam and identity checks at full size; the open lips; publishing conditions.
STATUS: Arc closed at the records level with the re-render pending. Railway api, scheduler-cron and presence SUCCESS on 206c3fd, health 200 at 2026-11-03T07:03Z.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
