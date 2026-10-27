# Jev image lanes: the standalone harness

Ruled by Tee on 2026-10-27 on a card, "Standalone harness", over a full copy of
TQO FINAL V5. A copy could not be isolated by disabling nodes: both manual
triggers run the Script and Brief branches too, lane 1 needs a Queued row with
registered presenter clips and pays for TTS first, and lanes 2 and 3 need a
human approved Ready row. None of the 66 executions saved between 2026-10-14 and
2026-10-27 had reached Pexels Search or Thumb: Find Still, so there was no live
input to replay either.

The harness is a separate inactive workflow holding only the three lanes, the
three consumer nodes, Thumb: Download Still and Thumb: Compose. The nodes the
lane code reads by name (Plan B-Roll Segments, Pexels Search, Presenter: Attach
Clips, Thumb: Plan, Thumb: Find Still) are Code stubs with those exact names,
fed from `../fixtures/pexels_video_search_2221.json`. Thumb: Find Still stands in
for a photo search with three Pexels video posters from that fixture. It touched
no live row, table, Drive folder, TTS, Cerebras call or YouTube node.

## The run

Workflow `yNr8lXrSbdNUqHba`, created inactive, run once as execution 4737 at
2026-10-27T21:47:22Z, then archived. `harness_as_run_4737.json` is the exact body
that was posted, and the read back of it matched node for node.

All 25 nodes ran with no node error in 5.07 seconds.

| lane | calls | images | input tokens | answer |
|---|---|---|---|---|
| b-roll | 2 | 8 | 8,657 each | jev-1.14.0. Build Movie `jevRanked` 2, `jevWouldChange` 1, `jevApplied` false |
| thumbnail photo | 1 | 3 | 6,659 | jev-1.14.0. Jev's pick equals today's pick |
| composed check | 1 | 1 | 2,822 | jev-1.14.0. Headline present 0.99, readable 0.85, box right edge 0.68 |

26,795 input tokens in all, about $0.001 at $0.042 per million. The five b-roll
nodes took 1,255 ms of node time and 1,505 ms of wall time for 2 segments, of
which the two TypeSafe calls were 678 ms. At the 45 segments `Plan B-Roll
Segments` allows, that scales to about 390,000 tokens, about $0.02, and 28 to 34
seconds a render, plus about 1.3 seconds for the two thumbnail lanes. That is a
scaling of two segments, not a measurement of a full episode. The worst case,
every call running to its timeout, is about 54 minutes; `../JEV_WIRING.md` works
it out under Lane 1.

The check's note, "the headline runs off the dark panel onto the photograph",
came from a box right edge of 0.68 against the designed 0.603. The composed frame
is saved in the execution as the `<thumb>` asset of `Jev: Thumb Check Body`, and
reading it settles the note: the second headline line, "DASHBOARD FIRST", ends at
x 866 of 1280 (0.677), while the dark panel ends at x 760. Jev was right on this
frame. `Thumb: Pick Still` wraps an 84 px headline at
floor(700 / (84 * 0.52)) = 16 characters, and on this frame 15 capitals at 84 px
drew 787 px wide.

The same frame showed a second defect: the navy panel was drawn about 15
percent opaque, not 85, because GraphicsMagick reads the last pair of an 8 digit
colour as transparency. Both were fixed in the live workflow on 2026-10-27 on
Tee's cards and published as `de4ac645`, after four more harness runs on the
instance's own Compose node. `../live-thumb-layout/` holds the change and its
proof.

## Rebuilding it

    python3 n8n/tqo-v5/jev-harness/build_harness.py OUT.json

The builder reads the lane files as they are now. Since the run they pin
`jev-1.14.0`, where the run sent `jev-latest` and `jev-preview`, both of which
answered as jev-1.14.0. A rebuild differs from `harness_as_run_4737.json` in those
three model lines and in eight lines of the header comment of `Jev: Thumb Check
Body`, rewritten in the same commit, and in nothing else.

Posting the body creates a workflow and running it spends TypeSafe credit. Both
are outward writes and both are Tee's call on a card.
