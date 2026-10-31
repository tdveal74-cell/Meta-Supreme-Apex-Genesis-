# TSWS Episode 1: what stands between the cut and a full motion render

Status doc written 2026-10-31 at 05:15Z on Tee's ask: "Check all of episode 1 and see what's needs to be done to render the episodes." It reads the cut as it stands, names every gap, and sets the plan to a full motion, photoreal Episode 1 with realm transitions. Tee gave an operator grant in the same message: act and decide on his behalf per the recommendations, merges, deploys and edits included. Every decision taken under it is listed in the section "Decided under the grant" and is his to overrule on a card. Spend is not in that list; it goes to him on one card at the end.

## What exists, measured

The episode is one ChatCut project, the 2026-10-29 handoff v05 of "TSWS S01E01 The Mask" (`5f8eb9e8-dfd2-40d2-a84c-c9214bf7f143`, timeline `362d64b3`), read on 2026-10-31. 20,877 frames at 30 fps, 695.9 s, 1920x1080, 165 assets (99 audio, 34 image, 12 motion graphic, 20 video), 31 markers, 19 timelines (the cut plus 18 snapshots and scratches). The locked script is v10 (29 July 2026), seven beats, 1,303 spoken words, protected frames [540,900), [12902,13022) and [14918,14978), closed master cut at 14978.

Picture, counted from the V2 track of that timeline. Six motion clips play, 1,560 frames in all, 52.0 s, 7.5 percent of the runtime:

| span | frames | clip | QC state |
|---|---|---|---|
| [540,900) | 360 | SH030 window open, thread visible, v01 | v04 passed the 2026-10-30 playback QC at about 93; swap held |
| [12402,12492) | 90 | J8 SH070 conform v03 | three seconds of the failed master, no stop |
| [12902,13022) | 120 | SH090 Anahata v01 | v02 passed at about 91; swap held |
| [14918,14978) | 60 | J10 SH120 thread press, approved v7 | approved |
| [18837,19197) | 360 | SH160a master closed v01 | failed QC (gold strand baked into the source still, halo, soft upscale, frozen first 60 frames, grade jump); v02 owed by the Visual Producer |
| [19197,19767) | 570 | SH160b window close v01 | v03 passed at 90; swap held |

Everything else, 19,317 frames, 92.5 percent, is a still: the city plate, the masked street still, the masked two-shot plate, the Auren single, the Vespera single, the corrected and unmasked street plates, the thread-concealed two-shot, the SH150 Venetian composite (a fill scale, up to 7 px off the locked camera, measured 2026-10-31), the closing window, and for 240 frames at [13262,13502) the superseded full-face-shell room plate `PLATE_masked_master.png` (asset `f4a1ef014a`, 1672x941), which Lane C replaces with the approved v211 two-shot at no cost. Three motion graphics are placed: the VO_074 caption on V3, the Anahata green reflection point on V4 inside the protected silence, and the closing question on V3. Tee's ruling of 2026-10-30 holds the four passing swaps until SH160a v02 lands, then swaps all four together.

Audio, read from tracks A1 to A5 on 2026-10-31: all 91 voice takes are placed (the 2026-10-13 census), VO_074 plays on both A1 and A2 at [12843,12902) as the simultaneous line, and the protected silence [12902,13022) carries only the silence file on A4, with A1 empty from 12899. The marker that calls the silence not silent describes v04 and is stale; so is the marker that places VO_074 Auren 728 frames early. Two audio items stay open: the export true peak measured at +0.1 dBTP against a working target of at or under -1.0 dBTP, with a uniform -1.5 dB trim proposed and applied only to a scratch project, and the 91 takes still unapproved as performances. Nobody has listened to the whole cut end to end.

## The seven parent shots

From the editor's ledger v03 (Drive `1HP58nQhUz13zzcX7hH2zXRoEr0QUBRIJIodWD5DmBEI`), the shot manifest (`1Bb9kIZ9tXpD4PGmA6-yx2F9RRjSe503fqfW5HXHNO34`), the 2026-10-16 and 2026-10-31 status docs, and the rulings of 2026-10-25 and 2026-10-30.

| shot | beat | what the cut plays now | what it needs |
|---|---|---|---|
| SH020 | 1, masked street | still, 10 s | motion between the accepted v2 Venetian stills (start f000, end f191, 2026-10-31). Not run |
| SH045 | 2, Auren turns to the window | still fallback | a ruling on which window, then a head and mask rig or a generated turn. The v03 candidate re-aims the eyeline 23.7 degrees up to the rear glazing |
| SH070 | 4, one person stops | 3 s of a master with no stop | new footage: G01, the grey-coat woman with the black handbag, walks to a settled stop (Ruling 2 of 2026-10-30); start frame is SH020's end, end frame is the SH100 Venetian start composite |
| SH100 | 5, masks fall | masked still fading to an unmasked still | new footage: the same worn Venetian masks detach intact and land, heads and faces retained, nobody reacts; ends on the SH135 v11 Venetian composite |
| SH135 | 5 to 6, fallen masks still | not placed; the overlay is the old unmasked plate | the v11 Venetian composite swapped in at P-1 (the editor's name for swapping the overlay item over the same 150 frames, [13112,13262), against P-2, the whole stand-in span, and P-3, the SH135 beat only) |
| SH150 | 6, street full of faces | still, 38 s | motion: unmasked walkers past the fallen masks, locked camera, from the SH135 v11 composite; the native master pans and was never locked |
| SH160 | 7, pull back to the rooftop | 12 s room clip (failed) plus 19 s window close plus two stills | the realm transition: one continuous retreat from the room, through the glass, across the gap, to the rooftop plate the episode opened on; the v03 solve proves the geometry at 192 frames |

The room, Beats 2, 3, 4 and 6, is about 543 s of stills cut between three plates. That is the largest gap by far, and the one no earlier plan budgeted.

## What a full motion Episode 1 takes

Three lanes. They do not block each other.

Lane A is the street. Six generated shots, four on the locked street camera and two that carry the camera between the rooftop, the street and the room, chained first frame to last frame so every join is a measured registration between two stills rather than a cut (the 2026-10-16 proposal's design, carried over). The stills that bound them: SH020 v2 start and end, the SH100 Venetian start composite, the SH135 v11 composite and the SH150 Venetian prop composite are on disk, conformed and measured within 0.5 px of the locked framing; the city plate, the SH030 first frame and the master closed plate exist only inside ChatCut until Tee's browser exports them. The cards, one per run, are `.claude/skills/tsws-shot-prompt/references/EP01_generation_cards_2026-10-31.md`. Street light and skyline keep their recorded exception (Ruling 1 of 2026-10-30).

| shot | inputs | model | length |
|---|---|---|---|
| Beat 1 arrival | city plate, SH020 v2 start as a middle keyframe, SH030 first frame as the last | Kling 4.0 (keyframes) | 13 s, trimmed to the 372 frame slot |
| SH020 | v2 start, v2 end | Kling 4.0 | 10 s |
| SH070 | SH020 v2 end, SH100 Venetian start | Veo 3.1 | 6 s, opened into the plate hold that follows |
| SH100 | SH100 Venetian start, SH135 v11 | Veo 3.1 | 8 s |
| SH150 | SH135 v11 first, SH150 composite last | Kling 4.0 | 30 s, the registered still holding the last 8.1 s |
| SH160 pullback | master closed first, SH030 first frame (the window from outside) as a middle keyframe, city plate last | Kling 4.0 (keyframes) | 30 s, on Tee's ruling |

Veo 3.1 for the two shots whose value is a performance (a walk to a stop, a release and fall), Kling 4.0 where the shot is a camera or a crowd and its keyframe slots carry the geometry. Each shot gets a start and an end still check with `align_still.py` before it is placed, and the clip checks in `tsws-shot-prompt` after.

Lane B is the room. Two steps. First, a library of controlled motion clips from the three approved plates: the masked two-shot, the Auren single and the Vespera single, three takes each, 10 s, locked camera, each take starting and ending on its plate so it loops, breathing and listening and small head moves, masks fixed, mouths at rest; and SH045's turn toward the rear glazing from the Auren single. These replace the stills everywhere the cut holds on a listener, which is most of the room. SH160a v02 stays the Visual Producer's; if Tee rules that the pullback replaces SH160a and SH160b, it is no longer needed. Second, speaking coverage, which this first pass does not budget beyond its test: until a route passes, every speaking shot stays a still or a closed-mouth take, so the first pass is picture motion and not yet a full motion episode. The Venetian half-mask leaves the mouth free, so a speaking single without lip movement reads as a defect. Three routes exist and none has rendered a TSWS frame: Runway Act-Two or Wan 2.2 Animate from a recorded performance by Tee and Karrie (ruled 2026-09-24, consent for performance capture unverified, Runway on the free plan with 202 credits); audio driven generation with the owned VO takes as the reference audio (Seedance 2.5 through ChatCut takes up to 10 audio references per ChatCut's `submit_video` schema, read 2026-10-31; ChatCut has 0 credits until 2026-11-08); or lip sync applied to a library clip (HeyGen Pro, 321 premium credits, `create_lipsync`). The first and third keep the voices and likenesses owned. Speaking coverage is a test before it is a plan: one line, one route, judged by Tee, with Karrie's veto on every Vespera close-up (R82).

Lane C is assembly. Everything lands in the ChatCut cut: each clip at its slot, the four held swaps when SH160a v02 passes, the SH135 v11 overlay, the -1.5 dB trim once Tee has heard the A and B, the stale markers replaced by current ones, then an export, the OS 28 gate and Tee's end to end watch. The timeline stays at 30 fps; the native street masters came at 24 fps and the models' output rate is not pinned by their schemas, so each take's rate is read from the file and conformed on placement (PIC-06). Lane C also replaces the 240 frame hold on the superseded room plate at [13262,13502) with the approved v211 two-shot, and the SH150 fill still with the registered conform.

## The realm transition

Tee asked for environmental realm transitions in the register of American Gods. Book 01 (Drive `1qpLdALL-fYIR6PGMIwjj2DXkFH-EMrdB`, 9 October 2026) already holds the rule for that and parks it: Tier 2, the subjective threshold, "currently on hold for EP01", with the transition law "establish a real surface, choose one visual bridge, transform one property, then arrive in a legible destination", and two hard limits, no transition inside the 12 second opening hold or the 4 second protected silence. Episode 1 has one realm, the Street of Unlooking, a district of the Shared Shadow (R26, R47), so the transitions are between tiers of the same realm, not between realms.

Under the grant the hold is lifted for two shots and no others. Beat 1's arrival, where the camera comes down from the rooftop plate, through the masked street, to the lit window at the height the opening plate shows it, with rain and wet stone as the bridge, and stops exactly on the first frame of the protected hold. And SH160, where the same camera retreats from the room, through the glass of the window, across the gap, to the rooftop plate, with the glass as the bridge: reflection becomes transparency becomes distance. The opening hold, the silence and the mask fall stay as they are; the mask fall is the episode's metaphysical event and needs no help.

## Decided under the grant

Each of these was a pending ruling. Each is recorded here with its reason and stands until Tee overrules it on a card.

1. SH160 window glass (Producer queue Decision 1): the camera passes through the closed pane. The pane is the realm bridge above, and an opened window adds a prop action the script does not have.
2. SH160 head spacing residual (Decision 2): accept the 72 px residual. A reframe of the room master costs a new approved plate and every room clip with it.
3. SH160 elevation canon (Decision 3): the opening hold plate wins over the script's "third floor". The plate is the locked opening image; Book 01 puts the locked timeline above its own methods, and R80 lets rulings override a script's visual notes where they conflict.
4. SH045 sightline (Decision 4): Auren turns toward the rear window. The front window is 1.3 degrees from his straight ahead, so a turn toward it is not a turn; the rear glazing is the only window that produces the cue "turns his head toward the window". The v03 candidate is built on that reading.
5. Book 01 Tier 2 hold: lifted for Beat 1's arrival and SH160 only.
6. SH135 placement: the v11 Venetian composite goes in at P-1, the overlay span [13112,13262), per the Visual Bible's repair status of 2026-10-25, until the SH100 fall clip lands; that clip's last three seconds are the masks at rest, so the overlay comes off with it.
7. The 2026-10-16 street proposal (Decision 5, Veo through the Google runner at about $9.60 a pass) is superseded by Lane A above; its chained design is kept; its shells went with the 2026-10-25 ruling and its scarf-woman stopper with Ruling 2 of 2026-10-30, which made the grey-coat woman the stopper.
8. Model and route: Veo 3.1 for the two performance shots (SH070, SH100) and Kling 4.0 for the four camera and crowd shots and the room library, all through WaveSpeed; Seedance 2.5 ($6.48 a shot on 2026-10-30) is not used. The skill said this choice goes to Tee on a card with the quotes; under the grant it is taken here with the quotes in the cards, and it reverses at the cost of the runs already made.
9. Slot lengths, read from the timeline on 2026-10-31: the arrival at 13 s trimmed by 18 frames to the 372 frame slot; SH070 opened from 3 s to 6 s into the two-shot hold that follows it; SH150 as one 30 s clip with the registered still holding the last 243 frames in place of the fill still, which sits up to 7 px off the locked camera. Each reverses by a trim or a second run.
10. The arrival ends on the first frame of the clip that plays at frame 540 (SH030), not on the pre-Venetian window plate, and that plate is out of every card.
11. Scope of the first pass: picture motion in Lanes A and B first; speaking coverage after its one line route test, which is a separate budget. The ask is a full motion episode and this pass does not reach it on its own; it is the half that can run today.

Ruled by Tee on cards later the same day, after this doc was first written: spend, "I have a GPU with runpod and the vps have a LTX and comfyUI on it", then the route, "All on your GPU, LTX 2.3, 80 GB tier", which retires decision 8 above; SH160, "Hold SH160 until v02 lands"; the creator workspace, "Vela (apps/vela on EditForge)"; and at 07:41Z, keep the pod, run the end-anchored SH150 chain, the SH150 still as that shot's end state, and three ArtCraft skills vendored on their own PR. The run on that route is the dated `SYS_OPS_tsws-ep01-ltx-pod-run` doc beside this one and the skill's `references/LTX23_pod_jobs_2026-10-31.md`. Still not decided here: the mask on the distant face in the SH020 end still; which pedestrian in that still is G01; the gold thread on the long form street plates.

## Money and routes, read on 2026-10-31

| route | balance, and the read it came from | what it can run |
|---|---|---|
| WaveSpeed | $0.17 (`get_balance`), which funds nothing until topped up | every model in Lane A and the room library, once topped up; now on the gate ledger (#448) |
| Google Gemini key, through the environment proxy | balance not visible; the models endpoint was read through the proxy on 2026-10-31 | Veo 3.1 and Veo 3.1 Fast (both answer the models endpoint), Gemini 3 Pro Image; billed to Tee's Google account |
| Runway | free plan, 202 purchased credits (`show_plans_and_credits`) | too little for Act-Two work |
| ChatCut | 0 credits, 100 a month, resets 2026-11-08 (`read_billing`) | Seedance 2.5 with audio references, when credits return |
| HeyGen | Pro, 321 premium credits (`get_current_user`) | lip sync on a clip, the speaking test |
| Higgsfield | 0.38 credits (`balance`) | nothing |
| Runpod, Tee's account | pay as you go; an A100 80 GB Secure Cloud pod at $1.79 an hour (`list-pods`, 2026-10-31) | every card, on LTX 2.3 through ComfyUI; the ruled route, see the run doc |

Prices, WaveSpeed estimates at 1080p on 2026-10-31, read with `get_price`: Veo 3.1 8 s with audio off $1.60 (with audio $3.20, which is the figure the first draft of this doc carried), Veo 3.1 Fast 8 s $1.20, Kling 4.0 $0.188 a second at the 80 percent discounted rate the account is quoted (list $0.235; $1.88 at 10 s, $2.444 at 13 s, $5.64 at 30 s). Google's own Veo price page was fetched and does not list Veo at all, so the Google figure is unverified; the WaveSpeed price is the one quoted. Lane A at one take each comes to $16.52 (the arrival $2.44, SH070 $1.20, SH100 $1.60, SH150 $5.64, SH160 $5.64), and $18.40 if SH020 runs on its own because the arrival is not accepted; the room library of nine takes $16.92 and the SH045 turn about $1.50; both lanes with a second take on every shot about $74. Full room coverage at one take per hold is a separate figure, about 55 clips and about $103, and the lip sync test is unpriced until HeyGen's rate is read. The recommended ceiling is $120 for the first pass, every run quoted again before it fires and recorded in the skill's job record.

## The tools in hand, read 2026-10-31

Tee pointed at the prompt guides on his Drive, the software on his VPS, Vela and a creator workspace. Read, not recalled:

Two Hostinger boxes, both KVM 2 (2 vCPU, 8 GB, 100 GB, Ubuntu 24.04, no GPU), from the Hostinger API. `srv1936193` at 2.25.140.44 is `n8n.editforge.online`: n8n in Docker and, on the host's loopback behind the `n8n_backend` bridge, the TSWS render worker (Node 18.19.1, ffmpeg 6.1.1), which is what TSWS 00 to 05 call for assembly. `srv1936199` at 2.24.109.87 is `editforge.online`: the EditForge compose stack (`web`, `worker`, `provider`, `edge` on Caddy), firewall 22, 80 and 443 only, health 200 on 2026-10-31. Neither box can run a generative video model, and the VPS ComfyUI at `comfy.2-24-109-87.sslip.io` is CPU only with its n8n draft refusing a CPU render; every generated frame is made off the boxes, on the Runpod pod since the route ruling, and only assembled on them.

Vela is `apps/vela` on the `vela-src` branch of `tdveal74-cell/EditForge` (`b728eda`, 2026-10-20), a Vite app with Cut, Still, Enhance, Stage, Floor, Booth, Script and MCP rooms, deployed by a manual `workflow_dispatch` only, to a container on `127.0.0.1:8090` of `srv1936199`, not a public hostname. Whether that container is up today is unverified from here. Its EP01 media foundation imports real sources with their hashes, holds a 24, 25, 30, 50 or 60 fps timeline, steps the 20,877 frames, locks the SH135 hash and packs a ZIP backup; the open gaps register of 2026-10-25 (Drive `1_4-HdOJHF-689wJzoYctMUsrGeKk4qARuFoMQ3PcbTA`) still lists no tracking, rotoscoping, paint, clone, keyframes, export grade or burned-in titles. Vela is where a repair could be inspected, not where a frame gets generated or composited today. The EditForge worker's own local job types are trim, reframe, derive-short, speed, audio-mix, grade, captions, render-preview and render-master; its generate-full-motion, lip-sync and synthesize-voice types go to adapters by URL. The EditForge MCP endpoint answered 503 to this session on 2026-10-31.

The guides are the Book 02 production package folder on Drive (`123VXtNt-4jEpgLDpXpP0T1Bf536rnucy`): Books 01 to 03 as PDF and editable Markdown, the prompt bank, the websites and realism note, the season one environmental themes, the Metaphysical Transition Realms Guide and the VFX Sequence Blueprint as infographics, three AI realism infographics, the Codex realism capture the skill already cites, the master shot prompt, the comparison prompt, the Grok prompts and the S01E01 prompt package v03 with its shot manifest and continuity record. A sweep that reads every one of them and holds the cards against them is running as this doc is written; its confirmed changes land in the cards as a second round.

"Creator workspace" is not a name any file in the repository or on Drive resolves to a product: this repository carries a Creator Workspace delegated reader for DEVON metadata (`docs/creator-workspace/`), default disabled, and Vela's package is named `app-builder-workspace`. Which one Tee means was asked on a card, and he answered Vela (`apps/vela` on EditForge).

## Open

- Spend: ruled, his own GPU; the pod's hourly rate is the only spend and the stop rule is in the skill.
- Six ChatCut exports by Tee's signed-in browser: the four Venetian room plates (`705db59a16`, `9159d4802f`, `875a95a424`, `b2d18c59ad`), the opening plate `12862ef053` and the first frame of SH030 (`b46bf0bcad`). The arrival, the pullback and every room take wait on them.
- Whether the SH160 pullback replaces SH160a and SH160b: held until v02 lands, by his card.
- Which pedestrian in the SH020 end still is G01.
- The 240 frame hold on the superseded full-face-shell room plate at [13262,13502), replaced in Lane C by the approved v211 two-shot.
- Speaking coverage for the room: a one line test on one route, then a ruling.
- The distant unmasked face at about (1750, 530) in the SH020 v2 end still.
- The five street stills measured on 2026-10-31 all sit within 0.5 px of the locked camera; the still the cut holds for SH150 (`ee434a5871`, a fill scale) sits up to 7 px off it and is replaced by the registered conform when the SH150 clip lands.
- Whether QC gate 2's gold thread applies to the long form street plates.
- The three v2 PNGs into the Drive folder, by Tee's hand.
- Tee's end to end listen of the cut, and the -1.5 dB trim decision.
- Tee's end to end watch of the SH020 pilot, the SH100 take and the SH150 chain from the pod, and their placement in ChatCut, which follows it.

## DEVON RECEIPT

AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-ep01-render-readiness_v1_2026-10-31-0515.md
DATE: 2026-10-31
DECISIONS: Tee's grant of 2026-10-31 (act and decide on his behalf per the recommendations, merges, deploys and edits included). Under it: the SH160 glass is passed through closed, the 72 px residual is accepted, the opening plate wins on elevation, Auren turns to the rear glazing, Book 01's Tier 2 hold is lifted for the arrival and the pullback only, SH135 v11 at P-1 until the fall clip lands, the 2026-10-16 proposal is superseded, Veo and Kling through WaveSpeed with Seedance dropped, the slot lengths read from the timeline, and the arrival ends on SH030's first frame. Spend, the SH160 replacement and the creator workspace question went to him on cards, and he ruled all three later the same day: his own GPU on LTX 2.3 at the 80 GB tier, SH160 held until v02 lands, and Vela.
FINDINGS: The v05 cut is 7.5 percent motion by frame count, and about 543 s of the room are stills on three plates plus 240 frames on a superseded shell plate. The protected silence is clean in v05 and two markers that say otherwise are stale. All five registered street stills sit within 0.5 px of the locked camera; the SH150 fill still in the cut sits up to 7 px off it. Kling 4.0 at 1080p is $0.188 a second discounted and Veo 3.1 with audio off is $1.60 for 8 s, half the first draft's figure. The first critic round found the arrival card 5.6 s too long for its slot and the Kling prices taken from the 720p rate; both are fixed in this version. WaveSpeed holds $0.17; the Google key answers for Veo 3.1 and Veo 3.1 Fast; Runway, ChatCut and Higgsfield hold too little to run a lane. Google's pricing page does not list Veo. Neither VPS has a GPU; Vela inspects, it does not generate.
OPEN: The spend ceiling; six ChatCut exports by Tee's browser; whether the pullback replaces SH160a and SH160b; G01's identity and the distant unmasked face in the SH020 end still; speaking coverage and its HeyGen price; the gold thread on the street plates; the three SH020 v2 PNGs into Drive; Tee's end to end listen and the -1.5 dB trim; the guide sweep's second round.
STATUS: Audit written and corrected after the first critic round; WaveSpeed at $0.17 and nothing spent there; the route was then ruled to Tee's own GPU and the SH020 pilot, SH100 and the first segment of the SH150 chain rendered there the same day, recorded in the run doc; PR #448 merged as 06bd3ff; this doc, the cards and the run doc are PR #450.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
