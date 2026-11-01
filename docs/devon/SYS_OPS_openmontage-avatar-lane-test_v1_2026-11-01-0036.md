# OpenMontage avatar lane test: Tee's clone voice and photo look, through the connectors

Status doc for the first test of OpenMontage as an avatar lane, ruled by Tee at 2026-10-31T23:41:12Z ("Test it") and shaped on a card at 23:49:23Z. Written 2026-11-01. Two renders were made and neither is for publishing. The skill's own record said speech output and any keyed provider were unverified; this test is the first time either ran.

## The ruling

OpenMontage's own `heygen_avatar` and `elevenlabs_tts` tools read `HEYGEN_API_KEY` and an ElevenLabs key from the environment, and this cloud environment holds neither. On the 23:49:23Z card Tee chose to run the test through the claude.ai connectors he already has: the ElevenLabs connector for speech, HeyGen's for the lip sync, and OpenMontage for the compose step only. The card set ceilings of 600 ElevenLabs credits and 20 HeyGen credits. He also chose the script as drafted and the look "TQO landscape 4 black polo". After the first render, a second card at 2026-11-01T00:09:28Z chose a second render on the same look with HeyGen's Avatar V engine, with its cost written into the option: HeyGen may borrow a public studio look as the motion reference, because his photo group holds no digital twin. The same card chose this write-up.

So the test proves OpenMontage's compose step on Tee's own voice and face. It does not prove OpenMontage's provider tools, which never ran.

## What ran

| step | tool | id | result |
|---|---|---|---|
| voice | ElevenLabs connector, `eleven_multilingual_v2` | flow `fkflWP4Ol0Kgw8lnavD8`, generation `AK73i51Ci41B4WfAQTrE` | one take, 19.5 s, voice `ypnKDQtIhp4N3yn4UnqO` "T Veal 2.1", which is `TEE_CLONE` in `services/devon/show_registry.py` |
| audio upload | HeyGen asset upload | asset `fe7cddfa91064f5a8d0bc468b11028c9` | the MP3 was refused at finalization as `application/octet-stream`; the same audio decoded to a 16-bit WAV with its metadata stripped was accepted |
| render 1 | HeyGen Avatar IV, look `a27abba9da0539374ced44d6e36f970c` | video `867780359d613624811208deab0b04b1` | 19.5 s at 1920x1080, 25 fps, in 2 min 40 s |
| render 2 | HeyGen Avatar V, same look and audio | video `f314a35bf8df411a4424a08d0fddd4db` | 19.5 s at 1920x1080, 25 fps, in about 1 min 33 s |
| compose | OpenMontage `remotion_caption_burn` at `195eab2` | none | 586 frames each, 94 s and 84 s, 56 caption words against a 56 word script |

HeyGen's caption file wrote the show name as "the quiet operator". That one line was corrected to match the script before the compose step, and nothing else was changed.

## Spend

| account | before | after | cost | ceiling |
|---|---|---|---|---|
| ElevenLabs | not read | not read | 268 credits, 4.9 cents, from the generation record | 600 credits |
| HeyGen render 1 | 321 | 314 | 7 credits | 20 credits for the test |
| HeyGen render 2 | 314 | 297 | 17 credits | about 16, on the second card |

HeyGen's balances were read with `get_current_user` before and after each render. HeyGen's help centre lists Avatar IV photo looks at 16 credits a minute and Avatar V at 48, read on 2026-10-31. Render 1 stayed inside its ceiling. Render 2 cost one credit more than its card said and was approved on its own card, so the two renders together spent 24 HeyGen credits.

## What the verifiers found

Two workflows sent three independent verifiers each, told to refute claims and given none of the reasoning behind them: `wf_cf23e692-38c` on render 1 and `wf_0d129e81-6c3` on render 2 against render 1.

The voice is Tee's take and nothing else. The final audio of render 1 correlates with the ElevenLabs take at 0.99994. The two renders' audio tracks decode to identical samples. ElevenLabs' stored copy of the take has the same sha256 as the local file.

The captions match the script word for word in both finals, read page by page from the frames, and they never cover the eyes, nose or mouth.

Both renders carry a defect from HeyGen. A lighter rectangle with a hard vertical edge sits over the lower lip and chin, plainest at 4.4 s and 16.2 s. It is in HeyGen's raw clip before OpenMontage touches it. Avatar V did not remove it. One verifier measured the edge in render 2 at 90 to 95 percent of render 1's step, and another counted it at more sampled moments in render 2 than in render 1. A third saw it absent in render 2 at six sampled moments. The two measured readings outweigh the six samples, so this doc treats the patch as present in both.

In neither render do the lips close in the speech pauses. Render 2 closes them only in the last 0.6 s. It also moves the head more than render 1, and its face reads slightly paler.

OpenMontage's compose step adds three faults of its own, the same in both renders:
- It moves the audio about 43 ms later against the picture, because the encoder's start-up samples are not skipped: the vendor clip's audio edit list skips 943 samples and the final's skips none.
- It converts 25 fps to 30 fps by repeating one frame in six, 97 duplicated frames in 586, a slight steady hitch.
- It tags the picture as full range, `yuvj420p`, where the vendor clip is limited range. The colour measured the same, and how a phone player treats the tag was not checked.

## What this says about the lane

In this lane OpenMontage added word captions and three small faults, and the face quality is HeyGen's. On this photo look HeyGen's mouth region shows a seam that a viewer can see at full size, and two engines both show it. A video avatar, a digital twin trained on footage of Tee, is the likeliest fix, but nobody has tested that.

## Not verified

- Tee watching either render on his phone, which is the only judgement of the seam that counts.
- Which look, if any, HeyGen used as the motion reference for render 2. No HeyGen read names it.
- OpenMontage's own `heygen_avatar` and `elevenlabs_tts` tools, which need keys this environment does not hold.
- Whether the full range tag shifts contrast on a phone player.
- ElevenLabs' balance before and after. The cost comes from the generation record, not from a balance read.

## Gauntlet verdict

VERDICT: PASS-WITH-CONDITIONS
Deliverable: two 19.5 s test renders for Tee to watch, not to publish, and this record
Scores: correctness 4, scope 5, verification 4, security 5, reversibility 5, failure handling 4, idempotency 5, traceability 5, observability 4, completeness 4, maintainability 4 | mean 4.5 | flagship bar: met as a test, missed for publish because of the chin seam
Conditions: Tee watches both renders before anything else is decided about the lane.
Receipts: six verifiers across two workflows; HeyGen balances read before and after; the ElevenLabs generation record; the hashes and ids above.
Recommendation: watch both renders on the phone. The human owns SHIP.

## Open

- Tee to watch both renders. They are in the session's scratchpad, which goes when the container is reclaimed. The HeyGen copies stay in his HeyGen library under the two video ids above, titled "not for publish".
- The seam: test a digital twin, or another look, on Tee's ruling.
- The three compose faults belong to upstream OpenMontage, AGPL code this repository does not edit.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_openmontage-avatar-lane-test_v1_2026-11-01-0036.md
DATE: 2026-11-01
DECISIONS: Tee ruled "Test it" at 2026-10-31T23:41:12Z. On a card at 23:49:23Z he chose the connectors path, the drafted script and the black polo look. On a card at 2026-11-01T00:09:28Z he chose a second render on Avatar V and this write-up.
FINDINGS: The clone voice and the photo look both ran through the connectors and the voice in the finals is Tee's take (correlation 0.99994). Captions match the script word for word. HeyGen leaves a light seam over the lower lip and chin on this look with both Avatar IV and Avatar V, and the lips stay open in pauses. OpenMontage's compose adds about 43 ms of audio delay, a 25 to 30 fps repeat-frame hitch and a full range colour tag. Spend: 268 ElevenLabs credits and 24 HeyGen credits.
OPEN: Tee watches both renders; a digital twin or another look for the seam, on his ruling; the compose faults are upstream's.
STATUS: Two test renders made, verified by six independent verifiers, delivered to Tee in chat. Not for publish.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
