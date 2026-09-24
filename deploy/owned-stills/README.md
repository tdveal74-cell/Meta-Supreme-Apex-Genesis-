# Owned b-roll stills: Tee at a desk, from his own character sheets

Ruled by Tee on 2026-09-24: the AI Avatar Academy method is used for b-roll
stills only. The presenter stays on the two routes in `deploy/lipsync/README.md`,
MuseTalk over owned footage and the HeyGen avatar, and no talking photo route
is built. This carries out the 2026-09-16 ruling that the b-roll becomes Tee's
own avatar at a computer rather than stock.

An earlier commit on this branch wrote the opposite, a talking photo presenter
as a third route, from a card answer Tee corrected the same day. That text is
gone and this file replaces it.

## Where the method comes from, and how much of it was read

Lanie, AI Avatar Academy, "How to Build an AI Avatar that Creates & Sells FOR
You", `aiavatar.substack.com/p/how-to-build-an-ai-avatar-for-your`. The session
that wrote this could not open it: the container's egress proxy blocks
substack.com. A search result summary gave the first three steps: a reference
photo in Higgsfield, a six angle character sheet from Nano Banana Pro, then
images generated against that sheet. Everything past that, including prices
and the article's prompts, is UNVERIFIED.

## The source is the character sheets Tee already has

Tee has his contact sheets made. The sheets are the reference for every still
and nothing else is: no generated face, no stock person. Where the sheets live
is not recorded in this repository; file their location here once it is read.

## Gates, none of which has an exception path

**The face is Tee's.** A still is generated against his own sheets and is
checked by eye against them before use. A still that drifts from his face is
thrown away, not corrected in the edit.

**Disclosure.** A generated image of a real person on a teaching channel falls
under Tee's own AI disclosure rule. YouTube's exact threshold for its altered
or synthetic content label is not verified here; label every upload that
carries these stills and check the current policy text before the first one.

**Read the wallet before the first spend.** HeyGen was found on 2026-09-16 with
auto reload on at $10 a top up. The image tool's billing and reload settings
are unchecked; read them, write them here with the date, and get Tee's word
before any paid generate call.

**A human watches the whole render.** Nothing ships without Tee watching it end
to end.

## What the render lane does with a still

`presenter_composite` in `deploy/render-worker/jobs.js` takes a still as a
cutaway. Added 2026-09-24, a still gets a slow 8 percent push in across its
window instead of holding dead:

```json
{ "path": "ep03/desk-01.png", "start": 42, "end": 48, "motion": "push_in" }
```

`motion` is `push_in` (the default), `pull_out` or `none`. A still takes no
`in`, and `motion` on a moving clip is refused at submit. A text card or end
card sent as a still should carry `"motion": "none"`.

## Open, and why each is open

- **The n8n side.** `Build Movie` in `TQO FINAL V5` emits `type: video` only,
  so no still reaches the render worker yet. That edit touches a live workflow
  and waits on Tee.
- **The stills themselves.** None has been generated from the sheets yet.

## A b-roll prompt to start from

Written for this repository, not taken from the article. Attach the character
sheet as the reference.

```
The man from the attached character sheet, seated at a desk, working at a
laptop, three quarter angle, a warm practical lamp and a cool monitor glow,
shallow depth of field, calm and focused. Same face exactly as the sheet.
16:9, photographic, no text, no logos on the screen.
```
