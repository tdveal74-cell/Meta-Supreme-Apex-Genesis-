# Episode 1 generation cards, 2026-10-31

The paid runs the Episode 1 render readiness doc (`docs/devon/SYS_OPS_tsws-ep01-render-readiness_v1_2026-10-31-0515.md`) calls Lane A and Lane B, one card per run, written to the method in `SKILL.md`. Nothing here has run. Every card waits on the budget card and is quoted again with `get_price` before it fires; the quote and the prediction id go into the job record for the shot.

Shared facts. The five street shots share one locked camera (Ruling 1 of 2026-10-30), keep the Atlanta skyline and the lit lamp posts as a recorded exception to R26 and R27, and wear the Venetian half-masks of the 2026-10-25 ruling before the fall; from the fall on the same masks lie on the pavement and the crowd is unmasked, and nobody reacts or looks up. The grey-coat woman with the black handbag is G01 and the one who stops (Ruling 2); the maroon-scarf pedestrian has short coiled twists and her SH100 mask (Ruling 4); the grey-haired businessman keeps the briefcase in his right hand (Guardrail A, 2026-10-25). Masters are generated at 24 fps and conformed to the 30 fps timeline on placement. Audio off on every run; the street masters are silent and the episode mix is already placed.

Inputs on disk in the session scratchpad `plates/` and `deliver_v2/` folders, each hash checked against its record on 2026-10-31:

| file | size | sha256 | source |
|---|---|---|---|
| `TSWS_S01E01_SH020_START_f000_VENETIAN_v2_DRAFT.png` | 1920x1080 | `39f8a41ea8d0cfad4a42f3df3152119bd640755ecf2426017b3eb6266bb71d15` | accepted 2026-10-31 |
| `TSWS_S01E01_SH020_END_f191_VENETIAN_v2_DRAFT.png` | 1920x1080 | `3b862c163564edbf6d57b570c2258cd6db20fff21e370d43eb8ea3dc32ebd99b` | accepted 2026-10-31 |
| `SH100_START_VENETIAN_COMPOSITE.png` | 1920x1080 | `5627288448d5ec7ca54b11430c2ee0f03b44fd278d1b74657cc850e096611a7a` | Drive `1PjfRYFGwd0nwb1U3HB6Caye8cqvo1kr7`, matches `REPAIR_VERIFICATION.json` |
| `SH135_v11_VENETIAN_PROP_COMPOSITE.png` | 1392x784 | `b51d2c2a540cc2763f2a72c50947dacaccee36f5fad38dc051d4fff22ece7279` | Drive `18N6PaGw4RtXvRyVmDKBXisE1FHnMzLLU`, matches `REPAIR_VERIFICATION.json` |
| `SH150_VENETIAN_PROP_COMPOSITE_FINAL.png` | 2752x1536 | `3be3dce85e51e169354ecfe409c44ac899c79953789e92fcf96218eabb7c5d2d` | Drive `1HPwSQ-Agi_sxy5tyaQjIbWQCDPr7Fx41`, matches `REPAIR_VERIFICATION.json` |
| `PLATE_city_open.png` | 1672x941 | `acfcf80356c6dcd95f4f436a77c53f7fceb0a8f5fcc1824a457c3114238256ab` | Drive `1x9ZgrSWcUkGslx4pEvcQl95UJIssz8ML`; the episode's opening still per the SH160 addendum of 2026-10-14; measured on disk 2026-10-31, no record hash exists to compare it with; conformed before use |
| `PLATE_window_open.png` | 1672x941 | `2e5f22f35cc4dccbee3c06329604a9de7f58ec38d641b2976bac25809e8a59d3` | Drive `1-T-aGCx_80Mj7ENyhr2H8XjbINxP-piG`, 2026-10-11, pre-Venetian; measured on disk 2026-10-31, no record hash exists to compare it with; conformed before use |

Two inputs are not on disk and not on Drive: the room plates with the Venetian masks at 1920x1080 exist only in the ChatCut project (`705db59a16` the two-shot, `9159d4802f` the Auren single, `875a95a424` the Vespera single, `b2d18c59ad` the thread-concealed two-shot). The Drive copies of the room plates (`PLATE_masked_master.png`, `PLATE_master_closed.png`, 1672x941, 2026-10-11) carry the superseded full-face shells and are not inputs. Until the four ChatCut plates are filed to Drive, the SH160 pullback and every room card are blocked on that export, which needs a signed-in browser (`request_asset_download`).

Four inputs need a conform before they are keyframes: SH135 v11 (1392x784), the city plate and the window plate (both 1672x941) are each scaled to 1920x1081 and cropped by one row, and SH150 final (2752x1536, 1.792:1) is scaled to 1920x1071 and padded to 1080 with Void (`#050308`) rows top and bottom; every conform is checked with `align_still.py --regions` against the frame they must join before the run. A keyframe that does not register to its neighbour is a reset by construction, which is the fault this chain exists to remove.

## Lane A, the street

### A1. Beat 1 arrival, slot [168,540)

Kling 4.0, `kwaivgi/kling-v4.0/image-to-video`, 18 s, 1080p, 16:9. `image` the conformed city plate, `keyframes` [the SH020 v2 start still], `last_image` the conformed window plate. Quoted 2026-10-31 base $0.157 a second at 1080p, so about $2.83; re-quote before firing.

Prompt: "One continuous camera move with no cut. The camera starts on the rooftop view of the city at blue hour, descends slowly and steadily toward the wet street below, passes at eye level along the masked pedestrians who keep walking at an unhurried constant pace, then rises again to the lit third floor window across the gap and comes to rest on it, holding still on the final frame. Rain texture on the air and wet stone carries the eye from the skyline to the street to the glass. Every pedestrian keeps the same fitted Venetian half-mask for the whole move. The two seated figures in the window do not move. Steady, slow, eased motion; nothing abrupt. Photoreal, fine constant grain, the source palette and lighting."

Acceptance: the last 24 frames register to the window plate within 1 px on the skyline region (`align_still.py --regions`); the middle keyframe is reached with every pedestrian masked; no new or vanished people at the street level; Tee watches it end to end. The clip ends at 540, where the protected hold begins, and nothing of it crosses that frame.

### A2. SH020, slot [240,540) or the arrival above

Kling 4.0, 10 s, 1080p. `image` the v2 start, `last_image` the v2 end. About $1.57. Runs only if A1 is not accepted; A1 covers the same slot.

Prompt: "Locked-off camera, no pan, tilt, zoom or drift. Masked pedestrians walk along their existing paths at an unhurried constant pace with natural gait and weight transfer, arriving at their positions in the final frame. Every face keeps the same fitted Venetian half-mask, unchanged, on every frame; no mask slips, swaps or falls. Each coat, scarf, bag and briefcase stays with the same person, and the grey-haired businessman keeps his briefcase in his right hand. Nobody looks into the lens or reacts to anyone. The wet stone keeps its warm reflections; buildings, sky, lamp posts and string lights stay rigid. No text."

### A3. SH070, the stop, slot [12402,12492) and the frames the editor opens around it

Veo 3.1, `google/veo3.1/image-to-video`, 8 s, 1080p, 16:9, `generate_audio` false, `seed` 7070. `image` the SH020 v2 end, `last_image` the SH100 Venetian start composite. Quoted 2026-10-31 $3.20.

Prompt: "Locked-off camera, no camera movement. The woman in the grey coat carrying the black handbag walks naturally toward her position in the final frame, takes one last step, settles her weight and stops, facing the way she was walking. She does not turn, glance, gesture or look into the camera. Everyone else keeps walking at an unhurried constant pace on their existing paths and nobody reacts to her. Every face keeps its fitted Venetian half-mask, which never slips, changes or disappears. The grey-haired businessman keeps the briefcase in his right hand. Nobody appears or disappears. Photoreal, natural skin and fabric, coherent wet-pavement reflections and contact shadows, the source palette and lighting. No text."

Negative: "camera pan, zoom, head turn toward camera, eye contact with lens, face morphing, identity change, duplicate people, masks disappearing, full-face masks, melting architecture, text, watermark".

Acceptance: the composer gate measures walk, decelerate and stop on planar world speed for G01; the first frame registers to the SH020 end and the last to the SH100 start within 1 px; Tee watches it.

### A4. SH100, the fall, slot [13022,13262)

Veo 3.1, 8 s, 1080p, audio off, `seed` 1100. `image` the SH100 Venetian start composite, `last_image` the conformed SH135 v11. $3.20.

Prompt: "Locked-off camera. The pedestrians keep walking at the same unhurried pace while each Venetian half-mask loosens and falls on its own: the mask separates from the face intact, without stretching, dissolving, shattering or any hand touching it, falls with modest rotation under gravity, passes behind legs where bodies are in front of it, and lands intact on the wet pavement with a contact shadow. The faces underneath are ordinary and stay the same person throughout, heads and hair unchanged. Nobody reacts, looks down, looks up, reaches up or stops. The grey-coat woman with the black handbag stays standing where she stopped. The briefcase stays in the businessman's right hand. No new people, no green light, no particles. End exactly on the final frame."

Negative: "heads disappearing with masks, head regrowth, masks dissolving, people reacting, people stopping, camera movement, extra objects, text".

Acceptance: no head loss on any frame (the editor's f80, f96 and f120 failure); every mask that lands is one that was worn; the last frame registers to the conformed SH135 v11; Tee watches it.

### A5. SH150, the street full of faces, slot [17694,18837)

Kling 4.0, 20 s, 1080p. `image` the conformed SH135 v11, `last_image` the conformed SH150 final. About $3.14.

Prompt: "Locked-off camera, no pan, tilt, zoom or drift. Unmasked pedestrians walk along their existing paths at an unhurried constant pace, faces ordinary and uncovered, nobody looking at anyone and nobody looking up. The fallen Venetian masks stay exactly where they lie on the wet pavement and are stepped around, never kicked or picked up. The grey-coat woman with the black handbag stands still where she stopped. No new masks appear on any face. The street, lamps, skyline and string lights stay rigid. Photoreal, the source palette and lighting. No text."

Acceptance: the skyline region drifts under 0.5 px across the clip (this is the fault in the native master); no mask returns to a face; Tee watches it. The slot is 38 s; the editor decides between one 20 s clip with a hold and two chained clips.

### A6. SH160, the pullback, slot [18837,19767) and the two stills after it

Kling 4.0, 20 s, 1080p. `image` the thread-concealed two-shot at 1920x1080 (ChatCut `b2d18c59ad`; blocked until it is on disk), `keyframes` [the conformed window plate], `last_image` the conformed city plate. About $3.14.

Prompt: "One continuous camera move with no cut. The camera starts inside the room on the two seated masked figures, who do not move, and retreats slowly and steadily backward through the window glass, which turns from reflection to transparency as the lens passes it, out across the gap between the buildings, and keeps rising and pulling back until it rests on the rooftop view of the city where the episode began, holding still on the final frame. The window stays lit and the two figures stay seated and masked inside it as it shrinks. The street below is full of unmasked walkers who keep moving. No gold thread anywhere. Steady, slow, eased motion; nothing abrupt. Photoreal, fine constant grain, the source palette and lighting."

Acceptance: the first frame registers to the room plate and the last to the city plate within 1 px on their static regions; the window plate is reached with the two figures seated; no building morphs and no second glazing appears (the native master's f64 to 96 and f122 to 140 faults); Tee watches it. This card also supplies SH160a v02 if its first 12 s hold on the room before the retreat begins; whether that reads as a hold or as a frozen frame is Tee's call on the watch.

## Lane B, the room library

Blocked until the four ChatCut plates are on disk. Nine clips, Kling 4.0, 10 s, 1080p, about $1.57 each. Three takes from each of the two-shot, the Auren single and the Vespera single; the same prompt with the take number changed in the job record and no other change, so the takes differ by seed alone.

Prompt, two-shot: "Locked-off camera. The two seated masked figures hold their positions and their attention on each other. Slow breathing under the clothing, a small shift of weight, a slight settle of the shoulders, the eyes behind the mask apertures moving once. Mouths stay closed and at rest. Masks stay fitted and unchanged. Hands stay where they are. The lamp, the window and the room stay rigid. Nothing abrupt. Photoreal, natural skin and fabric, fine constant grain, the source lighting."

Prompt, single: the same, with "the seated masked figure holds position and keeps looking toward the other person, off frame" in place of the first sentence.

Speaking coverage is not in this file. It is a one line test on one route, judged by Tee, before any card is written for it.

## Order of operations when the budget card is answered

1. Quote every card again with `get_price`; a quote above the figure here is reported before the run.
2. Conform SH135 v11, SH150 final, the city plate and the window plate; check each with `align_still.py --regions`; record the conformed files' hashes.
3. Upload the inputs through `create_upload` and the curl PUT (both gated; the card answer opens the window).
4. Run A1, A3, A4 and A5 first, one take each, then A6 and Lane B when their plates are on disk.
5. Check every clip's first and last frame and every defect time listed in `SKILL.md`, then hand the clips to Tee with the slot each goes in. Placement in ChatCut and the four held swaps follow his watch.
