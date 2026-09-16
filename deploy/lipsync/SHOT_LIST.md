# The cutaway shot list: one session, both halves

Written 2026-09-16 on Tee's ruling. The recording session in `README.md` gives
the presenter bank, takes A, B and C in landscape and portrait. It gives no
cutaways, so every episode still fills its visual track from Pexels. This list
is the other half of the same twenty minutes.

Why it matters more than better stock keywords: episode 2 rendered as 45 stock
clips with zero from the owned pool, and the b-roll was rejected on sight. The
keywords were part of it, six of ten were abstract or unsearchable, but the
source was the real problem. No amount of phrasing makes Pexels return Tee.

## What the render lane will do with these

`Plan B-Roll Segments` cuts the script on sentence boundaries into scenes of
5 to 12 seconds, target 8, capped at 45. `Build Movie` emits each one as
`{ type: "video", src, start, duration, muted: true }`. With the presenter as
the base track the cutaway count per episode drops to roughly 8 to 12, each one
covering a beat that needs an illustration.

So nine scenes shot twice, wide and tight, is 18 clips, and an 8 to 12 cutaway
episode never repeats one. That is the target.

## Hard requirements, each one learned the expensive way

- **At least 15 seconds per clip.** The lane trims from an `in` point for
  `end - start`. A clip shorter than its window holds its last frame, which
  reads as a freeze. 15 seconds covers the 12 second ceiling with headroom.
- **Locked off. No camera movement, no zoom, no rack focus.** The cut into and
  out of a moving shot jars against a static presenter base.
- **No talking.** Cutaways are muted. A visible mouth forming words the viewer
  cannot hear looks like a sync fault.
- **Shoot 4K at 25 fps** if the app offers it. The presenter base is 25 fps
  because HeyGen renders at 25, and a cutaway at another rate judders on every
  held frame.
- **Landscape for long form. Repeat the desk scenes in portrait** for the
  stacked Short's payload zone.
- **Under 25 MB per delivered file.** Google Drive serves a virus scan
  interstitial above roughly that size, the worker writes the HTML to `.mp4`,
  and ffmpeg refuses it with `moov atom not found`. That exact failure killed
  render `uYn0b5SzQwGflxwh`.
- **Share permission set to anyone with the link.** Owner only files produce
  the identical symptom, an HTML sign in page saved as video. Both the
  permission and the size have to be right, and `Build Movie` says so in its
  own comment.
- **Register every clip in the B-Roll Library, `tbl2pr5GLeeUJK1rr`,** and only
  set Verified once share permission AND file size are both checked. Verified
  is not a formality. It is the flag that says the two things which have
  actually broken a render were checked.

## The nine scenes

Numbered to match the reference frames. Shoot each wide and tight.

1. **Laptop work.** Seated, typing, eyes down on the screen. Wide from the
   front left with the room falling off dark. Tight over the right shoulder
   showing hands and screen edge.
2. **Handwriting.** Pen moving in an open notebook, laptop closed or pushed
   back. Tight enough to read the movement, not the words.
3. **Window, thinking.** Standing, in profile, city behind glass. This is the
   only scene with a bright background and it earns it by being a deliberate
   beat, not filler.
4. **Car.** Seated, checking a watch, daylight through the windscreen. Reads as
   the commute and the time pressure the audience lives in.
5. **Single monitor, workflow canvas.** Seated side on, monitor showing a real
   n8n canvas or Airtable view. Real screens, never a mockup.
6. **Glass diagram.** Standing, drawing boxes and arrows on glass with a marker.
   Shoot from behind the glass so the hand leads.
7. **Dual monitors.** Seated, reading across two screens, pen in hand.
8. **Tablet.** Tablet on a stand, finger moving on it, keyboard in frame.
9. **Desk, no face.** Mug, notebook, pens, lamp. No person in frame at all.

Scene 9 is not optional and it is not spare. The writer prompt published on
2026-09-16 now ends with "If a beat needs no illustration, name a neutral
object rather than a person", so the library has to hold frames that answer
that instruction. Without them the lane falls back to Pexels on exactly the
beats where restraint was the point.

## Wardrobe and room, so the library stays one library

Every reference frame Tee sent is the same black quarter zip in the same near
black room with warm practical lamps and deliberate negative space on one side.
That consistency is what lets clips shot months apart cut together. Keep it:
same top, same room, same lamps, and leave one side of the frame empty for
callouts and text.

## What this does not answer

Whether stills can substitute for any of these. `Build Movie` emits
`type: "video"` only, so an image asset needs that line changed to emit
`type: "image"` with a pan and zoom. That change is scoped and not yet made,
and it is the fallback if shooting motion turns out to be the blocker rather
than the footage itself.

## DEVON RECEIPT

```
AREA: Studio
TYPE: SHOT_LIST
ARTIFACT: deploy/lipsync/SHOT_LIST.md
DATE: 2026-09-16
DECISIONS: Tee ruled on 2026-09-16 that the b-roll becomes his own avatar at a computer rather than stock, that the presenter is the base layer with stock as cutaway, and that one recording session should serve both the MuseTalk presenter bank and the cutaway library. Nine scenes shot wide and tight gives 18 clips, which covers an 8 to 12 cutaway episode with no repeats.
FINDINGS: Episode 2 rendered 45 stock clips with zero from the owned pool and was rejected on the b-roll. Six of its ten keywords were abstract or unsearchable, but the source was the real fault: no phrasing makes Pexels return Tee. The owned pool machinery already exists and is deliberately off, POOL_SHARED false in Build Movie, retired 10 Aug 2026 because all 21 pool clips were abstract texture containing no person, desk, screen or office. Two delivery faults have already killed a render and both produce the identical moov atom error: a Drive file above roughly 25 MB serving a scan interstitial, and an owner only file serving an HTML sign in page. Scene 9, desk with no face, exists because the writer prompt published today asks for a neutral object rather than a person when a beat needs no illustration.
OPEN: Nothing has been shot. Build Movie emits type video only, so stills would need that line changed to emit type image with a pan and zoom, which is scoped and not made. Whether the HeyGen account has credit is unverified and the two HeyGen credentials on the n8n instance have not been told apart.
STATUS: Written, not shot. This is a plan for Tee to execute with a camera, and nothing in the render lane changes until footage exists and is registered Verified in tbl2pr5GLeeUJK1rr.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
