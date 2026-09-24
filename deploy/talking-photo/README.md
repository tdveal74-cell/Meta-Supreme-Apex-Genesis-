# The third presenter route: a talking photo of Tee, plus owned b-roll stills

Ruled by Tee on 2026-09-24, on an inline card, against a recommendation to use
the method for b-roll stills only. The objection is logged once here: a talking
photo animates one still, so it is lower fidelity than MuseTalk over recorded
footage, and it adds a paid vendor. The ruling stands and this route runs
beside the two in `deploy/lipsync/README.md`, replacing neither.

## Where the method comes from, and how much of it was read

Lanie, AI Avatar Academy, "How to Build an AI Avatar that Creates & Sells FOR
You", `aiavatar.substack.com/p/how-to-build-an-ai-avatar-for-your`. The session
that wrote this could not open it: the container's egress proxy blocks
substack.com. What is below comes from a search result summary and covers the
first three steps only.

1. Upload a reference photo to Higgsfield.
2. Generate a character reference sheet with Nano Banana Pro, the face from six
   angles, so every later image stays consistent.
3. Generate a talking head still from that sheet, the frame the avatar speaks
   from.

Every step after the third, every price, and the article's own prompts are
UNVERIFIED. Paste the article into a session before trusting anything here
about them.

## Gates, none of which has an exception path

**The face is Tee's.** The article allows a reference photo of "a face you've
generated". That is a rented persona and is refused. The reference is a real
photograph of Tee, and the character sheet is generated from it and from
nothing else.

**The voice is Tee's clone.** The talking photo is driven by the ElevenLabs
narration already produced by the episode, never by a vendor stock voice.

**Disclosure.** An animated still of a real person is altered or synthetic
content under YouTube's disclosure rule. Every upload carrying this route's
presenter, or a generated still of Tee, ticks the disclosure. This is a
compliance item and no episode ships without it.

**Read the wallet before the first spend.** HeyGen was found on 2026-09-16 with
auto reload on at $10 a top up, which turns a generate call into a card charge
with no confirmation. Higgsfield's billing model, its reload setting and its
plan are unchecked. Read them, write them into this file with the date, and get
Tee's word before any generate call runs against the account.

**A human watches the whole render.** Nothing from this route ships without Tee
watching it end to end.

## What the render lane already does with it

`presenter_composite` in `deploy/render-worker/jobs.js` takes `avatar` as any
video file, so a talking photo render drops in exactly where a HeyGen or
MuseTalk base track does. The base track is resampled to `fps`, 25 by default.

Stills of Tee generated from the character sheet go in as `cutaways` with a
`.png` or `.jpg` path. Added 2026-09-24, a still gets a slow 8 percent push in
across its window instead of holding dead:

```json
{ "path": "ep03/desk-01.png", "start": 42, "end": 48, "motion": "push_in" }
```

`motion` is `push_in` (the default), `pull_out` or `none`. A still takes no
`in`, and `motion` on a moving clip is refused at submit.

## Open, and why each is open

- **Length limit per render.** Talking photo tools often cap a single render
  well under an episode's eight minutes. Higgsfield's cap is unverified. If it
  is short, the episode needs its segments joined before `presenter_composite`,
  and that join does not exist yet.
- **The n8n side.** `Build Movie` in `TQO FINAL V5` emits `type: video` only.
  Stills reach the render worker only once that line emits them as cutaways.
  That edit touches a live workflow and waits on Tee.
- **Lip sync quality on a still.** Unmeasured. The first render is judged by
  Tee against a MuseTalk or HeyGen render of the same narration, side by side.

## A character sheet prompt to start from

Written for this repository, not taken from the article, which could not be
read. Attach two to four real photos of Tee as references.

```
Character reference sheet of the man in the attached photos. Keep his face,
skin tone, hairline, beard and build exactly as photographed; do not beautify,
de-age or restyle him. Six views on a plain mid grey background, evenly lit,
in a 3 by 2 grid: front, three quarter left, profile left, three quarter
right, profile right, and front with a slight smile. Same clothing in every
view: a plain dark crew neck. Chest up, neutral expression except the last
panel. Photographic, 85mm lens look, no text, no labels, no watermark.
```

The b-roll still, with the sheet attached as the reference:

```
The man from the attached character sheet, seated at a desk, working at a
laptop, three quarter angle, a warm practical lamp and a cool monitor glow,
shallow depth of field, calm and focused. Same face exactly as the sheet.
16:9, photographic, no text, no logos on the screen.
```
