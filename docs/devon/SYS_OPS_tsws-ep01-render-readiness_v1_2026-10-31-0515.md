# TSWS Episode 1: what stands between the cut and a full motion render

Status doc written 2026-10-31 at 05:15Z on Tee's ask: "Check all of episode 1 and see what's needs to be done to render the episodes." It reads the cut as it stands, names every gap, and sets the plan to a full motion, photoreal Episode 1 with realm transitions. Tee gave an operator grant in the same message: act and decide on his behalf per the recommendations, merges, deploys and edits included. Every decision taken under it is listed in the section "Decided under the grant" and is his to overrule on a card. Spend is not in that list; it goes to him on one card at the end.

## What exists, measured

The episode is one ChatCut project, the 2026-10-29 handoff v05 of "TSWS S01E01 The Mask" (`5f8eb9e8-dfd2-40d2-a84c-c9214bf7f143`, timeline `362d64b3`), read on 2026-10-31. 20,877 frames at 30 fps, 695.9 s, 1920x1080, 165 assets (99 audio, 34 image, 12 motion graphic, 20 video), 31 markers, 19 snapshot and scratch timelines. The locked script is v10 (29 July 2026), seven beats, 1,303 spoken words, protected frames [540,900), [12902,13022) and [14918,14978), closed master cut at 14978.

Picture, counted from the V2 track of that timeline. Six motion clips play, 1,560 frames in all, 52.0 s, 7.5 percent of the runtime:

| span | frames | clip | QC state |
|---|---|---|---|
| [540,900) | 360 | SH030 window open, thread visible, v01 | v04 passed the 2026-10-30 playback QC at about 93; swap held |
| [12402,12492) | 90 | J8 SH070 conform v03 | three seconds of the failed master, no stop |
| [12902,13022) | 120 | SH090 Anahata v01 | v02 passed at about 91; swap held |
| [14918,14978) | 60 | J10 SH120 thread press, approved v7 | approved |
| [18837,19197) | 360 | SH160a master closed v01 | failed QC (gold strand baked into the source still, halo, soft upscale, frozen first 60 frames, grade jump); v02 owed by the Visual Producer |
| [19197,19767) | 570 | SH160b window close v01 | v03 passed at 90; swap held |

Everything else, 19,317 frames, 92.5 percent, is a still: the city plate, the masked street still, the masked two-shot plate, the Auren single, the Vespera single, the corrected and unmasked street plates, the thread-concealed two-shot, the SH150 Venetian composite and the closing window. Two motion graphics carry the VO_074 caption and the closing question. Tee's ruling of 2026-10-30 holds the four passing swaps until SH160a v02 lands, then swaps all four together.

Audio, read from tracks A1 to A5 on 2026-10-31: all 91 voice takes are placed (the 2026-10-13 census), VO_074 plays on both A1 and A2 at [12843,12902) as the simultaneous line, and the protected silence [12902,13022) carries only the silence file on A4, with A1 empty from 12899. The marker that calls the silence not silent describes v04 and is stale; so is the marker that places VO_074 Auren 728 frames early. Two audio items stay open: the export true peak measured at +0.1 dBTP against a working target of at or under -1.0 dBTP, with a uniform -1.5 dB trim proposed and applied only to a scratch project, and the 91 takes still unapproved as performances. Nobody has listened to the whole cut end to end.

## The seven parent shots

From the editor's ledger v03 (Drive `1HP58nQhUz13zzcX7hH2zXRoEr0QUBRIJIodWD5DmBEI`), the shot manifest (`1Bb9kIZ9tXpD4PGmA6-yx2F9RRjSe503fqfW5HXHNO34`), the 2026-10-16 and 2026-10-31 status docs, and the rulings of 2026-10-25 and 2026-10-30.

| shot | beat | what the cut plays now | what it needs |
|---|---|---|---|
| SH020 | 1, masked street | still, 10 s | motion between the accepted v2 Venetian stills (start f000, end f191, 2026-10-31). Not run |
| SH045 | 2, Auren turns to the window | still fallback | a ruling on which window, then a head and mask rig or a generated turn. The v03 candidate re-aims the eyeline 23.7 degrees up to the rear glazing |
| SH070 | 4, one person stops | 3 s of a master with no stop | new footage: G01, the grey-coat woman with the black handbag, walks to a settled stop (Ruling 2 of 2026-10-30); start frame is SH020's end, end frame is the SH100 Venetian start composite |
| SH100 | 5, masks fall | masked still fading to an unmasked still | new footage: the same worn Venetian masks detach intact and land, heads and faces retained, nobody reacts; ends on the SH135 v11 Venetian composite |
| SH135 | 5 to 6, fallen masks still | not placed; the overlay is the old unmasked plate | the v11 Venetian composite swapped in at P-1, the overlay span [13112,13262) |
| SH150 | 6, street full of faces | still, 38 s | motion: unmasked walkers past the fallen masks, locked camera, from the SH135 v11 composite; the native master pans and was never locked |
| SH160 | 7, pull back to the rooftop | 12 s room clip (failed) plus 19 s window close plus two stills | the realm transition: one continuous retreat from the room, through the glass, across the gap, to the rooftop plate the episode opened on; the v03 solve proves the geometry at 192 frames |

The room, Beats 2, 3, 4 and 6, is about 543 s of stills cut between three plates. That is the largest gap by far, and the one no earlier plan budgeted.

## What a full motion Episode 1 takes

Three lanes. They do not block each other.

Lane A is the street. Six generated shots on the locked street camera, chained first frame to last frame so every join is exact by construction (the 2026-10-16 proposal's design, carried over). The stills that bound them exist and are accepted or prepared: SH020 v2 start and end, the SH100 Venetian start composite, the SH135 v11 composite, the SH150 Venetian prop composite, the city plate and the master closed plate. Street light and skyline keep their recorded exception (Ruling 1 of 2026-10-30).

| shot | inputs | model | length |
|---|---|---|---|
| Beat 1 arrival | city plate, SH020 v2 start as a middle keyframe, SH030 first frame as the last | Kling 4.0 (keyframes) | 18 s |
| SH020 | v2 start, v2 end | Kling 4.0 | 10 s |
| SH070 | SH020 v2 end, SH100 Venetian start | Veo 3.1 | 8 s |
| SH100 | SH100 Venetian start, SH135 v11 | Veo 3.1 | 8 s |
| SH150 | SH135 v11 first, SH150 composite last | Kling 4.0 | 20 s |
| SH160 pullback | master closed first, window open plate as a middle keyframe, city plate last | Kling 4.0 (keyframes) | 20 s |

Veo 3.1 for the two shots whose value is a performance (a walk to a stop, a release and fall), Kling 4.0 where the shot is a camera or a crowd and its keyframe slots carry the geometry. Each shot gets a start and an end still check with `align_still.py` before it is placed, and the clip checks in `tsws-shot-prompt` after.

Lane B is the room. Two steps. First, a library of controlled motion clips from the three approved plates: the masked two-shot, the Auren single and the Vespera single, three takes each, 8 to 10 s, locked camera, breathing and listening and small head moves, masks fixed, mouths at rest. These replace the stills everywhere the cut holds on a listener, which is most of the room. SH160a v02 comes out of the same batch, from the thread-concealed master closed plate, which is the fix for the gold strand the failed v01 baked in. Second, speaking coverage. The Venetian half-mask leaves the mouth free, so a speaking single without lip movement reads as a defect. Three routes exist and none has rendered a TSWS frame: Runway Act-Two or Wan 2.2 Animate from a recorded performance by Tee and Karrie (ruled 2026-09-24, consent for performance capture unverified, Runway on the free plan with 202 credits); audio driven generation with the owned VO takes as the reference audio (Seedance 2.5 through ChatCut takes up to 10 audio references; ChatCut has 0 credits until 2026-11-08); or lip sync applied to a library clip (HeyGen Pro, 321 premium credits, `create_lipsync`). The first and third keep the voices and likenesses owned. Speaking coverage is a test before it is a plan: one line, one route, judged by Tee, with Karrie's veto on every Vespera close-up (R82).

Lane C is assembly. Everything lands in the ChatCut cut: each clip at its slot, the four held swaps when SH160a v02 passes, the SH135 v11 overlay, the -1.5 dB trim once Tee has heard the A and B, the stale markers replaced by current ones, then an export, the OS 28 gate and Tee's end to end watch. The timeline stays at 30 fps and the generated masters at 24 fps, conformed on placement (PIC-06).

## The realm transition

Tee asked for environmental realm transitions in the register of American Gods. Book 01 (Drive `1qpLdALL-fYIR6PGMIwjj2DXkFH-EMrdB`, 9 October 2026) already holds the rule for that and parks it: Tier 2, the subjective threshold, "currently on hold for EP01", with the transition law "establish a real surface, choose one visual bridge, transform one property, then arrive in a legible destination", and two hard limits, no transition inside the 12 second opening hold or the 4 second protected silence. Episode 1 has one realm, the Street of Unlooking, a district of the Shared Shadow (R26, R47), so the transitions are between tiers of the same realm, not between realms.

Under the grant the hold is lifted for two shots and no others. Beat 1's arrival, where the camera comes down from the rooftop plate, through the masked street, to the third floor window, with rain and wet stone as the bridge, and stops exactly on the first frame of the protected hold. And SH160, where the same camera retreats from the room, through the glass of the window, across the gap, to the rooftop plate, with the glass as the bridge: reflection becomes transparency becomes distance. The opening hold, the silence and the mask fall stay as they are; the mask fall is the episode's metaphysical event and needs no help.

## Decided under the grant

Each of these was a pending ruling. Each is recorded here with its reason and stands until Tee overrules it on a card.

1. SH160 window glass (Producer queue Decision 1): the camera passes through the closed pane. The pane is the realm bridge above, and an opened window adds a prop action the script does not have.
2. SH160 head spacing residual (Decision 2): accept the 72 px residual. A reframe of the room master costs a new approved plate and every room clip with it.
3. SH160 elevation canon (Decision 3): the opening hold plate wins over the script's "third floor". The plate is the locked opening image; Book 01 puts the locked timeline above its own methods, and R80 lets rulings override a script's visual notes where they conflict.
4. SH045 sightline (Decision 4): Auren turns toward the rear window. The front window is 1.3 degrees from his straight ahead, so a turn toward it is not a turn; the rear glazing is the only window that produces the cue "turns his head toward the window". The v03 candidate is built on that reading.
5. Book 01 Tier 2 hold: lifted for Beat 1's arrival and SH160 only.
6. SH135 placement: the v11 Venetian composite goes in at P-1, the overlay span [13112,13262), per the Visual Bible's repair status of 2026-10-25.
7. The 2026-10-16 street proposal (Decision 5, Veo through the Google runner at about $9.60 a pass) is superseded by Lane A above; its chained design is kept, its shells and its scarf-woman stopper are not (Rulings 2 and 4 of 2026-10-30).

Not decided here: spend, below; the mask on the distant face in the SH020 end still; the gold thread on the long form street plates.

## Money and routes, read on 2026-10-31

| route | balance | what it can run |
|---|---|---|
| WaveSpeed | $0.17 | every model in Lane A and the room library; now on the gate ledger (#448) |
| Google Gemini key, through the environment proxy | balance not visible | Veo 3.1 and Veo 3.1 Fast (both answer the models endpoint), Gemini 3 Pro Image; billed to Tee's Google account |
| Runway | free plan, 202 purchased credits | too little for Act-Two work |
| ChatCut | 0 credits, 100 a month, resets 2026-11-08 | Seedance 2.5 with audio references, when credits return |
| HeyGen | Pro, 321 premium credits | lip sync on a clip, the speaking test |
| Higgsfield | 0.38 credits | nothing |

Prices, WaveSpeed estimates at 1080p on 2026-10-31: Veo 3.1 8 s $3.20, Veo 3.1 Fast 8 s $1.20, Kling 4.0 8 s $1.50. Google's own Veo price page was fetched and does not list Veo at all, so the Google figure is unverified; the WaveSpeed price is the one quoted. Lane A at one take each comes to about $19; the room library of nine clips on Kling 4.0 about $17; both with a second take on every shot about $75. The recommended ceiling is $120 for the first pass, every run quoted again before it fires and recorded in the skill's job record.

## Open

- Spend: on Tee's card.
- Speaking coverage for the room: a one line test on one route, then a ruling.
- The distant unmasked face at about (1750, 530) in the SH020 v2 end still.
- Whether QC gate 2's gold thread applies to the long form street plates.
- The three v2 PNGs into the Drive folder, by Tee's hand.
- Tee's end to end listen of the cut, and the -1.5 dB trim decision.

## DEVON RECEIPT

AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-ep01-render-readiness_v1_2026-10-31-0515.md
DATE: 2026-10-31
DECISIONS: Tee gave an operator grant on 2026-10-31 to act and decide per the recommendations, merges and edits included. Under it: SH160 passes through the closed pane, the 72 px residual is accepted, the opening plate wins on elevation, SH045 turns to the rear window, Book 01's Tier 2 hold is lifted for the arrival and the pullback only, SH135 v11 goes in at P-1, and the 2026-10-16 street proposal is superseded by Lane A.
FINDINGS: The v05 cut is 7.5 percent motion by frame count; 543 s of the room are three stills. The protected silence is clean in v05 and two markers that say otherwise are stale. WaveSpeed holds $0.17; the Google key answers for Veo 3.1 and Veo 3.1 Fast; Runway, ChatCut and Higgsfield hold too little to run a lane. Google's pricing page does not list Veo.
OPEN: Spend; the speaking route test; the distant face; the gold thread on street plates; the three PNGs on Drive; Tee's listen and the trim.
STATUS: Audit complete; nothing generated, nothing billed; Lane C edits not yet made.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
