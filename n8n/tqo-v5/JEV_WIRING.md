# Wiring the Jev image lanes into TQO FINAL V5

Ruled by Tee 2026-10-16, "Do thumbnail & b roll". This directory holds the
code for three Jev side branches. None of it is wired, nothing is published,
and no TypeSafe request has been made from any of it. Every lane ships in
shadow, behind a `JEV_APPLY` constant that only a ruling flips. While it is
false, today's choices stand and the lanes only report: Build Movie counts the
segments Jev ranked and the segments where Jev would pick another clip, Pick
Still records the photo Jev would pick, and the Shim records Jev's note on the
finished thumbnail.

What exists is offline proof: each node body runs in a harness against stubs
and against the unmodified export code, and those harnesses run in CI. They
prove the nodes keep today's output and read Jev's answers the way the
TypeSafe docs describe them. They prove nothing about what Jev answers.

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

| Node | Type | Settings |
|---|---|---|
| `Jev: B-Roll Stills` | Code, run once for all items | body `jev_broll_stills.js` |
| `Jev: Fetch B-Roll Still` | HTTP Request 4.2, GET `={{ $json.stillUrl }}` | response format File, timeout 10000, `onError: continueRegularOutput`, `alwaysOutputData: true` |
| `Jev: Still To Base64` | Extract From File, Move File to Base64 String | destination key `still_b64`, `onError: continueRegularOutput` |
| `Jev: B-Roll Bodies` | Code, run once for all items | body `jev_broll_bodies.js` |
| `Jev: Rank B-Roll` | HTTP Request 4.2, POST `https://api.typesafe.ai/v1/systemone` | Header Auth credential, header `TypeSafe-Danger-Zone-Images: true`, JSON body `={{ $json.body }}`, timeout 30000, `onError: continueRegularOutput`, `alwaysOutputData: true` |

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
| `Jev: Check Thumb` | HTTP Request 4.2, POST | as `Jev: Rank B-Roll`; the body names `jev-preview`, because a Box question needs Jev 1.14 |
| `Jev: Thumb Verdict` | Code, run once for all items | body `jev_thumb_check_verdict.js` |

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
  720, from `Thumb: Compose`. None was measured from a live download.
- The docs call baseline JPEG the safest and say to re-save a progressive one.
  Whether Pexels serves progressive JPEGs here, and what the API does with
  one, is unverified until the first live run.
- The API strips EXIF and does not apply its orientation. Whether every
  Pexels still at these sizes has upright pixels is unverified here.
- Asset references are matched as plain text anywhere in the request. These
  lanes use `<s0c1>`, `<p1>` and `<thumb>`. A narration or headline that
  contained one of those strings literally would be read as an image.
- The models page lists the input of both Jev versions as text, while the
  images page says both accept images. The images page is the one these
  lanes follow; the first live call settles it.

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
