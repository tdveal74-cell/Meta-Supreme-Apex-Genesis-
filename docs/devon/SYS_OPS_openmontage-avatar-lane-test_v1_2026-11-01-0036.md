# OpenMontage avatar lane test: Tee's clone voice and photo look, through the connectors

Status doc for the first test of OpenMontage as an avatar lane, ruled by Tee at 2026-10-31T23:41:12Z ("Test it") and shaped on a card at 23:49:23Z. Written 2026-11-01. Two renders were made and neither is for publishing. The skill's own record lists OpenMontage's speech and keyed provider tools as unverified, and they still are: in this test speech and the avatar ran through the claude.ai connectors, and OpenMontage only composed.

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

| account | before | after | cost | what the card said |
|---|---|---|---|---|
| ElevenLabs | not read | not read | 268 credits, 4.9 cents, from the generation record | ceiling 600 credits |
| HeyGen render 1 | 321 | 314 | 7 credits | about 7; ceiling 20 credits for the whole test |
| HeyGen render 2 | 314 | 297 | 17 credits | an estimate of about 16, on its own card |

HeyGen's balances were read with `get_current_user` at 23:41:54Z, 23:54:39Z and 00:12:16Z. HeyGen's help centre lists Avatar IV photo looks at 16 credits a minute and Avatar V at 48, read on 2026-10-31. The two renders together spent 24 HeyGen credits, which is over the 20 credit ceiling the first card set for the test. The extra came from render 2, which Tee approved on a second card that gave its cost as an estimate and set no new ceiling; it then cost one credit more than that estimate.

## What the verifiers found

Two workflows sent three independent verifiers each, told to refute claims and given none of the reasoning behind them: `wf_cf23e692-38c` on render 1 and `wf_0d129e81-6c3` on render 2 against render 1.

The voice is Tee's take and nothing else. The final audio of render 1 correlates with the ElevenLabs take at 0.99994. The two renders' audio tracks decode to identical samples. ElevenLabs' stored copy of the take has the same sha256 as the local file, `71e449ccf4872f20ad2cb80ec4460641239e0665a8024c27f5ebe8f885a260e1`.

The captions match the script word for word in both finals, read page by page from the frames, and they never cover the eyes, nose or mouth.

Both renders carry a defect from HeyGen. A lighter rectangle with a hard vertical edge sits over the lower lip and chin, plainest at 4.4 s and 16.2 s. It is in HeyGen's raw clip before OpenMontage touches it. On render 2 the three verifiers did not agree, and every one of them sampled moments; each tried an automatic seam score across the whole clip and none could separate the two renders with it, one saying its score could not tell the goatee's own edges from the patch. One measured a luminance step at 4.4 s and 16.2 s, the only measurement, and found render 2's edge at 90 to 95 percent of render 1's, and saw it by eye, at least faintly, at 14 of 18 moments in render 2 against 9 in render 1. A second counted it by eye at about 6 of 14 moments in render 2 against 2 or 3 in render 1. A third looked at six moments, 4.4 s and 16.2 s among them, and saw render 2's lip and chin continuous. The records verifier's own full size crops of render 2 at 4.4 s and 16.2 s show the lighter area and its vertical edge. On that, this doc treats the patch as present in both renders, with the caveat that nobody has measured it across the whole clip.

In neither render do the lips close in the speech pauses. Render 2 closes them only in the last 0.6 s. It also moves the head more than render 1, and its face reads slightly paler.

OpenMontage's compose step adds three faults of its own, the same in both renders:
- It puts the audio 2048 samples, 42.7 ms, later against the picture than the vendor clip had it, measured by cross-correlation at 48 kHz in both renders. The vendor clip's audio edit list skips 943 samples and the final's skips none, but 943 samples is 19.6 ms, so that alone does not account for 2048. The cause is not settled.
- It converts 25 fps to 30 fps by repeating one frame in six: all 488 vendor frames appear and 98 of the 586 are repeats, a slight steady hitch.
- It tags the picture as full range, `yuvj420p`, where the vendor clip carries no range tag. Across the whole clip the final reads 0.8 to 1.6 levels brighter per channel on average, at most 1.7, too little to see. How a phone player treats the tag was not checked.

## What this says about the lane

In this lane OpenMontage added word captions and three small faults, and the face quality is HeyGen's. On this photo look HeyGen's mouth region shows a seam that a viewer can see at full size, and the sampled frames of both engines show it. A video avatar, a digital twin trained on footage of Tee, is the likeliest fix, but nobody has tested that.

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
Receipts: six verifiers on the renders across two workflows, and two over this record, `wf_6c99097b-c4b` on the first draft and `wf_1b245d4c-0a2` on its corrections; HeyGen balances read before and after; the ElevenLabs generation record; the hash and ids above.
Recommendation: watch both renders on the phone. The human owns SHIP.

## Tee's watch, 2026-11-01

Both finals were sent to Tee in chat on 2026-11-01. He wrote "I watched" at 17:09:01Z and answered one card at 17:11:28Z. That watch was the first item under Not verified above and the one condition on the verdict, so the condition is met.

| question on the card | answer | what the card said follows |
|---|---|---|
| how the chin and lower-lip patch looked on his phone, at 4.4 s and 16.2 s | "Plain on both" | the black polo photo look is out for publish on either engine |
| which engine moved more like him | "Avatar V" | "three times what Avatar IV does: 17 credits for this 19.5 s clip, against 7" |
| the next avatar test | "Digital twin (Recommended)" | he films himself talking and approves HeyGen's consent link; the footage spec and the credit cost are checked against HeyGen's pages and put on a card before anything is spent |

His answer settles the question the verifiers split on: the patch is plain on both engines at phone size, whatever the sampled counts said about Avatar V. The black polo photo look is not used in anything published. The other two answers on the first question were "Plain on Avatar IV only" and "Faint, would pass".

The engine option on the card put two ratios in one sentence. Three times is HeyGen's listed rate, 48 credits a minute for Avatar V against 16 for Avatar IV. What this clip cost was 17 credits against 7, which is about 2.4 times.

The HeyGen account was read at 17:09:25Z: 297 premium credits on the Pro plan, resetting on 2026-11-26, and every private look on it is a photo look, so there is no digital twin to test yet. A twin trained on footage of Tee is the likeliest fix for both photo faults, the seam and the lips held open in pauses. That is untested.

## Open

- The digital twin test, on Tee's ruling of 17:11:28Z. He films the footage and approves the consent link. Nothing is created or rendered until the footage spec and the credit cost, read from HeyGen's own pages, have been on a card and he has answered it.
- The two test renders stay in his HeyGen library under the video ids above, titled "not for publish". The scratchpad copies go when the container is reclaimed.
- The three compose faults belong to upstream OpenMontage, AGPL code this repository does not edit.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_openmontage-avatar-lane-test_v1_2026-11-01-0036.md
DATE: 2026-11-01
DECISIONS: Tee ruled "Test it" at 2026-10-31T23:41:12Z. On a card at 23:49:23Z he chose the connectors path, the drafted script and the black polo look. On a card at 2026-11-01T00:09:28Z he chose a second render on Avatar V and this write-up. After watching both renders on his phone, on a card at 17:11:28Z he judged the seam plain on both engines, said Avatar V moved more like him, and chose a digital twin as the next test.
FINDINGS: The clone voice and the photo look both ran through the connectors and the voice in the finals is Tee's take (correlation 0.99994). Captions match the script word for word. HeyGen leaves a light seam over the lower lip and chin on this look, seen in sampled frames of both the Avatar IV and the Avatar V render (one of three verifiers did not see it on Avatar V), and the lips stay open in pauses. OpenMontage's compose adds about 43 ms of audio delay of unsettled cause, a 25 to 30 fps repeat-frame hitch and a full range colour tag. Spend: 268 ElevenLabs credits and 24 HeyGen credits, 4 over the first card's 20 credit ceiling after the second card approved render 2.
OPEN: the digital twin test, filmed by Tee, with the footage spec and credit cost on a card before any spend; the compose faults are upstream's.
STATUS: Two test renders made, checked by six independent verifiers, with this record checked by two more; delivered to Tee in chat. He watched both on his phone on 2026-11-01 and judged the seam plain on both engines. Not for publish.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
