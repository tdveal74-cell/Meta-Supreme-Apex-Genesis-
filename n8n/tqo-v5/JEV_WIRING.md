# Wiring the Jev image lanes into TQO FINAL V5

Ruled by Tee 2026-10-16, "Do thumbnail & b roll". This directory holds the
code for three Jev side branches. Every lane ships in shadow, behind a
`JEV_APPLY` constant that only a ruling flips. While it is false, today's
choices stand and the lanes only report: Build Movie counts the segments Jev
ranked and the segments where Jev would pick another clip, Pick Still records
the photo Jev would pick, and the Shim records Jev's note on the finished
thumbnail.

**Live since 2026-10-27T21:58:51Z, in shadow.** Tee ruled three cards that day:
"Standalone harness", "Draft now, publish card next" and "Publish now". The
lanes were proven first in a separate inactive workflow against the real
TypeSafe API (`jev-harness/`, execution 4737), then drafted into TQO FINAL V5
and published as version `3db61aef`, read back equal to the draft.
`live-jev-lanes/` holds the published nodes and the test that holds the repo
to them. Rollback was one publish of `fc75f7a6`. It is not now: a read of
`fc75f7a6` on 2026-10-28 returned 404, and n8n keeps only recent versions, so
undoing the lanes means editing the live version, as
`live-jev-lanes/manifest.json` says. Every `JEV_APPLY` is still
false, and flipping one is still a separate ruling.

The offline proof still stands beside that: each node body runs in a harness
against stubs and against the unmodified export code, and those harnesses run in
CI. They prove the nodes keep today's output and read Jev's answers the way the
TypeSafe docs describe them. What Jev answers on a real episode is read from the
first real render, and as of the publish no render had run through the lanes.

## The files

| File | Node | New or mirrored |
|---|---|---|
| `jev_broll_stills.js` | `Jev: B-Roll Stills` | new |
| `jev_broll_bodies.js` | `Jev: B-Roll Bodies` | new |
| `build_movie.js` | `Build Movie` | the export code plus Jev code |
| `jev_thumb_stills.js` | `Jev: Thumb Stills` | new |
| `jev_thumb_body.js` | `Jev: Thumb Body` | new |
| `thumb_pick_still.js` | `Thumb: Pick Still` | the export code plus a Jev block |
| `jev_thumb_check_body.js` | `Jev: Thumb Check Body` | new |
| `jev_thumb_check_verdict.js` | `Jev: Thumb Verdict` | new |
| `shim_thumbnail_to_binary.js` | `Shim: Thumbnail To Binary` | the export code plus a Jev block |

The three mirrored files start from export version `9320520f`, the version in
the export read on 2026-10-10. Whether it was still the published version on
2026-10-16 was not read. Each mirror test reads that export and fails if
anything outside the Jev code differs from it.

## Before anything is wired, Tee's on a card

All three were done by 2026-10-27. Tee funded the account, made the Header Auth
credential "Jev" (`AJM16uvmcW88bSL4`) on the instance, and ruled the wiring on
the three cards above. One approved authenticated call answered as jev-1.14.0
before the harness ran.

1. Fund the TypeSafe account. Jev bills per input token, $0.042 per million
   on both Jev 1.13 and 1.14 (docs.typesafe.ai/models, read 2026-10-16), and
   output tokens are free. Images are billed as input tokens, and the docs say
   guidance on how many tokens an image costs is still to come, so the cost of
   one episode is unmeasured until the first live run.
2. Create one n8n credential of type Header Auth, header `Authorization`,
   value `Bearer <key>`. The key never goes in a node, a file or a chat.
3. Rule the wiring itself. Editing the live workflow makes a draft; publishing
   it is a separate ruling, and the read back after publishing is the proof.

## Read the live workflow before pasting

The mirrored files are `9320520f` plus Jev code. If the live
`activeVersionId` has moved since, diff the live `Build Movie`, `Thumb: Pick
Still` and `Shim: Thumbnail To Binary` against the export first. Pasting a
mirror over a newer live node would silently undo whatever changed.

## Lane 1, b-roll

A side branch off `Pexels Search`, placed above `Plan Presenter Segments` on
the canvas. `settings.executionOrder` is `v1`, so sibling branches run one at
a time from top to bottom, and the side branch must finish before `Build
Movie` reads it. That puts every b-roll request inside the render path: with
`MAX_SEGMENTS` at 45 in `Plan B-Roll Segments` and four stills a segment, one
episode can make up to 180 still fetches and 45 TypeSafe calls, one after
another.

What that costs a render, from execution 4737 scaled to 45 segments. The five
b-roll nodes took 1,255 ms of node time for 2 segments, and the branch 1,505 ms
of wall time, so about 28 to 34 seconds a render, plus about 1.3 seconds for the
two thumbnail lanes. That is a scaling of two segments, not a measured episode.
The worst case is every call running to its timeout: 45 calls at 30 seconds and
180 fetches at 10 seconds is 52.5 minutes, and with the thumbnail lanes about 54
minutes. If only TypeSafe hangs it is about 23.5 minutes. No Jev node retries,
so the timeouts are the bound, and both figures sit under the 3 hour stale
claim window the Reaper uses. The cards Tee ruled on on 2026-10-27 said about
15 seconds, which counted the TypeSafe calls alone.

| Node | Type | Settings |
|---|---|---|
| `Jev: B-Roll Stills` | Code, run once for all items | body `jev_broll_stills.js` |
| `Jev: Fetch B-Roll Still` | HTTP Request 4.2, GET `={{ $json.stillUrl }}` | response format File, timeout 10000, `onError: continueRegularOutput`, `alwaysOutputData: true` |
| `Jev: Still To Base64` | Extract From File, Move File to Base64 String | destination key `still_b64`, `onError: continueRegularOutput` |
| `Jev: B-Roll Bodies` | Code, run once for all items | body `jev_broll_bodies.js` |
| `Jev: Rank B-Roll` | HTTP Request 4.2, POST `https://api.typesafe.ai/v1/systemone` | Header Auth credential, header `TypeSafe-Danger-Zone-Images: true`, JSON body `={{ JSON.stringify($json.body) }}`, timeout 30000, `onError: continueRegularOutput`, `alwaysOutputData: true` |

The JSON body is the form the live Cerebras nodes already use on this instance.
This table said `={{ $json.body }}` until 2026-10-27; the stringify form is the
one the harness ran and the one published.

Then replace `Build Movie`'s code with `build_movie.js`.

The 30 second timeout is a starting value, not a measurement; 43 of the 44
HTTP nodes in the export set one, and a call with none could hold the render.

## Lane 2, the thumbnail photo

A side branch off `Thumb: Find Still`, placed above `Thumb: Pick Still`.

| Node | Type | Settings |
|---|---|---|
| `Jev: Thumb Stills` | Code, run once for all items | body `jev_thumb_stills.js` |
| `Jev: Fetch Thumb Still` | HTTP Request 4.2, GET `={{ $json.fetchUrl }}` | as the b-roll fetch |
| `Jev: Thumb To Base64` | Extract From File | destination key `still_b64`, `onError: continueRegularOutput` |
| `Jev: Thumb Body` | Code, run once for all items | body `jev_thumb_body.js` |
| `Jev: Rank Stills` | HTTP Request 4.2, POST | as `Jev: Rank B-Roll` |

The fetch reads `fetchUrl`, not `url`. `url` is the size `Thumb: Pick Still`
draws and the key its scores are matched on; `fetchUrl` is a size Jev accepts.
Then replace `Thumb: Pick Still`'s code with `thumb_pick_still.js`.

## Lane 3, the check after compose

A side branch off `Thumb: Compose`, placed above `Shim: Thumbnail To Binary`.

| Node | Type | Settings |
|---|---|---|
| `Jev: Thumb To Base64 (Composed)` | Extract From File on binary property `thumbData` | destination key `still_b64`, `onError: continueRegularOutput` |
| `Jev: Thumb Check Body` | Code, run once for all items | body `jev_thumb_check_body.js` |
| `Jev: Check Thumb` | HTTP Request 4.2, POST | as `Jev: Rank B-Roll`; a Box question needs Jev 1.14 |
| `Jev: Thumb Verdict` | Code, run once for all items | body `jev_thumb_check_verdict.js` |

All three request bodies send the pinned `jev-1.14.0`, ruled by Tee 2026-10-27
on the draft card, so the floors cannot move under the shadow numbers if
TypeSafe moves an alias. Until then the two rank bodies sent `jev-latest` and
this one `jev-preview`; in execution 4737 all three answered as jev-1.14.0.

`Thumb: Compose` sets `onError: continueRegularOutput`, so a failed compose
reaches the Extract From File node with no binary. That node must carry
`onError: continueRegularOutput` too, or the side branch fails the run. The
verdict reads `Jev: Thumb Check Body` by that exact name to learn which
headline it checked; renamed, the Shim quietly records nothing. Then replace
the Shim's code with `shim_thumbnail_to_binary.js`.

## How Jev's answers are read

Both score rubrics have four distinct levels: 0 is an unusable picture, 1 is a
usable one about something else, and 2 and 3 fit. A score answer is a
probability weighted mean of the level numbers, such as 1.43, not a whole
level, so a certain level 1 picture scores exactly 1. Both consumers use
`JEV_FLOOR = 2`: Build Movie puts clips at the floor or above first, best
first, then the clips Jev did not score in Pexels order, then the clips under
the floor, best first, and never drops one; Pick Still picks Jev's photo only
at the floor or above. The docs warn that one mean can hide different
distributions, and the consumers read only the mean; the rank nodes' saved
executions keep the probabilities for the ruling.

`jevWouldChange` counts segments where Jev's pick differs from today's,
worked out against today's memory of used clips. After a flip the memory
follows Jev's picks, so the clips that actually change can be more or fewer.
It is an estimate for the ruling, not a forecast.

The thumbnail check sends the composed frame once, in state, and asks three
questions about it: whether the headline is there, where it sits, and whether
it reads at phone size. A Box answer is always a box, with no "not found",
which is why the headline is asked about first and the box and the reading
answer are ignored when it is low. The "runs off the dark panel" note fires
past `(72 + 700) / 1280`, the designed right edge of the text in `Thumb:
Compose` and `Thumb: Pick Still`, and a test ties that number to the export.

## What the TypeSafe docs require, read 2026-10-16

From docs.typesafe.ai/images, /primitives/box, /primitives/score and
/models. The images feature is marked as not yet production ready, and its
format and limits can change between releases, so re-read those pages before
wiring.

- Every request that carries an image or a Box question sends
  `TypeSafe-Danger-Zone-Images: true`, or it is refused with 400.
- PNG or JPEG only, 280 to 1568 pixels on each side, 78,400 to 2,458,624
  pixels in all, 16 MiB per image, 32 MiB per request body. Every use of an
  image's reference adds the image again toward a 32 MiB limit on the
  expanded request. An image outside the limits is rejected, never resized,
  and one rejected image fails the whole request.
- The two body nodes read each still's width and height from its first bytes
  and skip one that is out of limits, so one bad still costs that still and
  not its segment. A still whose size cannot be read is sent, as today.
- The b-roll stills are asked for at 1200 by 630, the `w` and `h` in the Pexels
  still urls of the fixture; the photo Jev sees is Pexels' landscape size,
  1200 by 627 by Pexels' own documentation; the composed thumbnail is 1280 by
  720, from `Thumb: Compose`. Execution 4737 fetched the fixture stills live:
  every one was a 1200 by 630 baseline JPEG, and the composed frame a 1280 by
  720 baseline JPEG. The 1200 by 627 photo search size is still unmeasured,
  because the harness stood video posters in for photos.
- The docs call baseline JPEG the safest and say to re-save a progressive one.
  Whether Pexels serves a progressive JPEG for a real photo search is still
  unverified.
- The API strips EXIF and does not apply its orientation. Whether every
  Pexels still at these sizes has upright pixels is unverified here.
- Asset references are matched as plain text anywhere in the request. These
  lanes use `<s0c1>`, `<p1>` and `<thumb>`. A narration or headline that
  contained one of those strings literally would be read as an image.
- The models page lists the input of both Jev versions as text, while the
  images page says both accept images. The images page is the one these
  lanes follow; the first live call settles it.

Re-read on 2026-10-27T21:28Z, before the harness ran, and compared with the
copies of the same pages read on 2026-10-16. Every number above still matches.
One thing changed: the alias table. On 2026-10-16 `jev-latest` named
`jev-1.13.0` and only `jev-preview` named `jev-1.14.0`. On 2026-10-27 both name
`jev-1.14.0`, with a new note that there is no preview build, and `jev-preview`
moves ahead of `jev-latest` when one exists. So an alias moved under these lanes
once already, which is why the bodies now pin `jev-1.14.0`.

The rest of this list was on the 2026-10-16 pages too and was not copied in
then:
- A third 32 MiB limit applies to all images in a request after the API
  processes them, and processing can make an image larger than the file sent.
- Animated PNGs are rejected. An image over a size limit returns 413, one under
  the minimum or damaged returns 400.
- Each asset reference is at most 1,024 bytes and all of them at most 65,536,
  and an asset that no question or state references returns 400.
- Multipart upload is now the recommended way to send images. Base64 in JSON,
  which these lanes use, is still allowed and costs about a third more size.
- A `TypeSafe-Danger-Zone-Long-Context: true` header raises the context limits
  to 262k tokens. These lanes do not send it.
- How many input tokens an image costs is still not published. Measured in
  execution 4737: 8,657 for four 1200 by 630 stills with one sentence, 6,659 for
  three with a subject and headline, 2,822 for one 1280 by 720 frame.
- The images feature is still marked as not production ready.

## Known risks the first wired run should read

- Two Split In Batches loops hold these lanes: `One Row at a Time` around the
  thumbnail lane and `Process Each Video` around the b-roll lane. When a later
  row's side branch stops early, `$('Jev: ...')` may return an earlier row's
  run; whether n8n does is unverified. Build Movie keys every score by its
  segment and clip link, so another episode's scores match nothing. Pick Still
  matches by photo url. The Shim takes a verdict only when it names the same
  headline as the row in hand, so two rows with the same headline are the one
  case left. Read it on an execution that processes two rows.
- A failed still fetch must still yield one item, or `Jev: B-Roll Bodies`
  sees unequal lengths and drops the whole segment set. It fails open either
  way; read the item counts on the first run.
- The context limit is 64k tokens per request and 32k per question. Four
  b-roll stills in one request is assumed to fit and is unmeasured.
- The workflow saves successful executions with their data, so every still
  and request body is kept in n8n's database. The size of that is unmeasured.

## Proving it after wiring

What was done on 2026-10-27, in order. Tee ruled a standalone harness over an
inactive copy of the whole workflow, because the copy could not be isolated (see
`jev-harness/README.md`). The harness ran once as execution 4737. On fixture
input the model, `jevRanked` and `jevApplied` checks in step 1 held; there was no
earlier run of the same row to compare the picks with, so that half of step 1
still rests on the offline mirror tests. The lanes were then drafted into the
live workflow in seven updates, read back equal to the repo bodies byte for
byte, and published as `3db61aef`, activated at 21:58:51Z. The read back at
21:59:02Z found `activeVersionId` equal to `versionId` and the published nodes
and connections equal to the read back draft. The public API returned no
`sameAsDraft` flag, so that node and connection comparison stands in for it. Step 3 is
`live-jev-lanes/`, which pins the published nodes to the repo files rather than
regenerating the exports, because nine test files and
`services/devon/show_registry.py` read the exports at `9320520f`, counted with
grep on 2026-10-27. Step 4 has not been asked.

The harness frame also exposed two defects in the live thumbnail design that
predate Jev: the navy panel drawn about 15 percent opaque, and full headline
lines running past it. Jev's check reported the second one correctly. Both were
fixed on Tee's cards and published as `de4ac645` the same evening; see
`live-thumb-layout/`. `live-jev-lanes/published.json` is read from that version,
and the Jev nodes in it are as `3db61aef` published them.

A fresh critic on `de4ac645` confirmed the live node equals the repo, the four
proof frames, and the layout on every Plan-shaped headline it tried; a later
verifier found the one exception in the last bullet below. It also showed
the first layout test let a budget of 760, a looser height rule and drifted widths
through once every pinned copy was moved together. The test now pins the layout
constants, the 1.2 em line pitch and the search floor, checks the width table
against Liberation Sans read from the font file, compares the node's wrap with
n8n's line for line, wraps the headline the node returns rather than the one it
was given, and adds nine crafted headlines. Each of these edits to the node, made
in every pinned copy at once, now fails it: a budget of 760 or 682, a budget
check loosened by 2 px, widths scaled by 1000/1005, W at 700, M at 600, E at 500,
an unlisted glyph at 400, a pitch of 0.5 or 1.1, a floor of 900, a search bound
of 1, the search floor raised by one to four, the lines judged at one more than
the wrap returned, the wrap without its plus one, a wrap one short of the
search's answer, and the headline left untrimmed. Three rounds of review each
found edits the previous test let through, so this is not a complete
specification of the node, and a deliberate change to it still needs its own
review.

Five things were left as they are, because changing any of them is a publish.
Each says why it was left:

- A double space or a newline in a headline can still make Compose draw an empty
  line. Plan collapses every run of whitespace to one space, and Pick Still trims
  the ends, so neither reaches Compose.
- The height rule assumes a 1.2 em line pitch. The four proof frames, executions
  4764 to 4767, measure 1.12 to 1.135 em, and GraphicsMagick drawing Liberation
  Sans at 84 px gives 1.131 em. The rule can only reject a size that would fit,
  never let one overflow.
- The comment above the width table says an unlisted glyph can only make the
  wrap tighter. That is wrong for the few glyphs wider than 1 em, such as
  Cyrillic Ю at 1010. Plan does not filter characters, so such a glyph could
  reach Pick Still; every English capital is in the table.
- The 24 px kicker draws at about 3 px when the thumbnail is shown 168 px wide.
  That predates this fix and was outside the ruling.
- A 20 letter word makes every size fail, and the 54 px fallback then joins the
  next two words on one line: `INTERNATIONALIZATION MOMENTUM MANAGEMENT` draws
  `MOMENTUM MANAGEMENT` out to x 796, past the panel edge at x 760. Plan caps the
  word count but not the word length. A verifier's search of 400,000 combinations
  of real English words found it only with a 20 letter word.

Still open after the publish, and readable only on the first real render:
whether n8n's two Split In Batches loops hand the side branches the right row,
whether Compose behaves the same inside the full graph, the item counts after a
failed still fetch, and Jev's answers on a real episode's narration and photos.

The house pattern for this workflow: wire an inactive copy, run it, read the
execution, archive the copy, then change the live workflow.

1. On the copy's execution, each rank node's output carries a `model` that
   starts with `jev-`, `Build Movie` reports `jevRanked` above zero and
   `jevApplied: false`, and the chosen clips, the thumbnail photo and
   `thumb_warning` are what the same row produced before.
2. After the live change, read the workflow back: `activeVersionId` equals
   `versionId` and `activeVersion.sameAsDraft` is true.
3. Regenerate the exports and add the three mirrored nodes to the export
   mirror tests, so a later live edit that is not copied back turns CI red.
4. Flipping any `JEV_APPLY` is a separate ruling, made from the shadow numbers
   of real runs.
