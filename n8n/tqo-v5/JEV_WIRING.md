# Wiring the Jev image lanes into TQO FINAL V5

Ruled by Tee 2026-10-16, "Do thumbnail & b roll". This directory holds the
code for three Jev side branches. None of it is wired, nothing is published,
and no TypeSafe request has been made from any of it. Every lane ships in
shadow: it works out what Jev would choose, records it on the item, and keeps
today's choice until a `JEV_APPLY` constant is flipped by a ruling.

What exists is offline proof: each node body runs in a harness against stubs
and against the unmodified export code, and those harnesses run in CI. They
prove the nodes keep today's output and read Jev's answers the way the
TypeSafe docs describe them. They prove nothing about what Jev answers.

## The files

| File | Node | New or mirrored |
|---|---|---|
| `jev_broll_stills.js` | `Jev: B-Roll Stills` | new |
| `jev_broll_bodies.js` | `Jev: B-Roll Bodies` | new |
| `build_movie.js` | `Build Movie` | the export code plus a Jev block |
| `jev_thumb_stills.js` | `Jev: Thumb Stills` | new |
| `jev_thumb_body.js` | `Jev: Thumb Body` | new |
| `thumb_pick_still.js` | `Thumb: Pick Still` | the export code plus a Jev block |
| `jev_thumb_check_body.js` | `Jev: Thumb Check Body` | new |
| `jev_thumb_check_verdict.js` | `Jev: Thumb Verdict` | new |
| `shim_thumbnail_to_binary.js` | `Shim: Thumbnail To Binary` | the export code plus a Jev block |

The three mirrored files start from export version `9320520f`, which was the
published version on 2026-10-16. Their tests read that export and fail if
anything outside the Jev block differs from it.

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

The mirrored files are `9320520f` plus a Jev block. If the live
`activeVersionId` has moved since, diff the live `Build Movie`, `Thumb: Pick
Still` and `Shim: Thumbnail To Binary` against the export first. Pasting a
mirror over a newer live node would silently undo whatever changed.

## Lane 1, b-roll

A side branch off `Pexels Search`, placed above `Plan Presenter Segments` on
the canvas. `settings.executionOrder` is `v1`, so sibling branches run one at
a time from top to bottom, and the side branch must finish before `Build
Movie` reads it.

| Node | Type | Settings |
|---|---|---|
| `Jev: B-Roll Stills` | Code, run once for all items | body `jev_broll_stills.js` |
| `Jev: Fetch B-Roll Still` | HTTP Request 4.2, GET `={{ $json.stillUrl }}` | response format File, timeout 10000, `onError: continueRegularOutput`, `alwaysOutputData: true` |
| `Jev: Still To Base64` | Extract From File, Move File to Base64 String | destination key `still_b64`, `onError: continueRegularOutput` |
| `Jev: B-Roll Bodies` | Code, run once for all items | body `jev_broll_bodies.js` |
| `Jev: Rank B-Roll` | HTTP Request 4.2, POST `https://api.typesafe.ai/v1/systemone` | Header Auth credential, header `TypeSafe-Danger-Zone-Images: true`, JSON body `={{ $json.body }}`, `onError: continueRegularOutput`, `alwaysOutputData: true` |

Then replace `Build Movie`'s code with `build_movie.js`.

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
`onError: continueRegularOutput` too, or the side branch fails the run. Then
replace the Shim's code with `shim_thumbnail_to_binary.js`.

## What the TypeSafe docs require, read 2026-10-16

From docs.typesafe.ai/images and /primitives/box. The images feature is
marked as not yet production ready, and its format and limits can change
between releases, so re-read those two pages before wiring.

- Every request that carries an image or a Box question sends
  `TypeSafe-Danger-Zone-Images: true`, or it is refused with 400.
- PNG or JPEG only, 280 to 1568 pixels on each side, 16 MiB per image, 32 MiB
  per request body. An image outside the limits is rejected, never resized,
  and one rejected image fails the whole request. Every lane then fails open.
- The b-roll stills are 1200 by 630, from the `w` and `h` in the Pexels still
  urls in the fixture. The thumbnail photo Jev sees is Pexels' landscape
  size, 1200 by 627 by Pexels' own documentation, which was not measured
  here. The composed thumbnail is 1280 by 720, from `Thumb: Compose` in the
  export.
- The docs ask for baseline JPEG and say a progressive JPEG should be re-saved.
  Whether Pexels serves progressive JPEGs at these sizes is unverified; if it
  does, the first live run shows it as a 400 on the rank node.
- Asset references are matched as plain text anywhere in the request. These
  lanes use `<s0c1>`, `<p1>` and `<thumb>`. A narration or headline that
  contained one of those strings literally would be read as an image.
- A Box answer is always a box, with no "not found", which is why the check
  asks `headline_present` first and ignores the box when it is low.
- A score answer is a float between the levels, such as 1.43, not a whole
  level. The lanes compare it against 1 and sort on it.

## Known risks the first wired run should read

- `One Row at a Time` is a Split In Batches loop around the thumbnail lane.
  If `$('Jev: ...')` returns an earlier row's run when a later row's branch
  stopped early, a row could read another row's scores. The nodes match by url
  where they can, so the damage is limited to the shadow report, and it is
  unverified either way. Read it on an execution that processes two rows.
- A failed still fetch must still yield one item, or `Jev: B-Roll Bodies`
  sees unequal lengths and drops the whole segment set. It fails open either
  way; read the item counts on the first run.
- The context limit is 64k tokens per request and 32k per question. Four
  b-roll stills in one request is assumed to fit and is unmeasured.

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
