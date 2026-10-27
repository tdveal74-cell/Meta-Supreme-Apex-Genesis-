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

26,795 input tokens in all, about $0.001 at $0.042 per million. The b-roll calls
took 678 ms together. At the 45 segments `Plan B-Roll Segments` allows, that scales
to about 390,000 tokens and about 15 seconds a render. That is a scaling of two
calls, not a measurement of a full episode.

The check's note, "the headline runs off the dark panel onto the photograph",
came from a box right edge of 0.68 against the designed 0.603. It is Jev's
reading of one composed frame. The composed image stays on the instance and was
not looked at, so whether the live thumbnail design overflows on a long line is
unverified.

## Rebuilding it

    python3 n8n/tqo-v5/jev-harness/build_harness.py OUT.json

The builder reads the lane files as they are now. Since the run they pin
`jev-1.14.0`, where the run sent `jev-latest` and `jev-preview`, both of which
answered as jev-1.14.0. Those three model lines are the only difference between a
rebuild and `harness_as_run_4737.json`.

Posting the body creates a workflow and running it spends TypeSafe credit. Both
are outward writes and both are Tee's call on a card.
