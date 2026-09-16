# TQO FINAL V5 Code node sources

`TQO FINAL V5` is `qEkGOUsNyVaRAmm6` on n8n.editforge.online, 240 nodes, and it
is the workflow that decides what publishes. Until 2026-09-16 none of it was in
this repository. The DEVON organs next door have been mirrored and diffed since
2026-09-06; the content gate had no copy anywhere, so a change to the rule that
holds or ships an episode left no diff and no review.

This directory starts closing that. It is not complete and does not pretend to
be: one node is here, the one that was changed.

| File | Node | What it decides |
|---|---|---|
| `build_qc_prompt.js` | `Build QC Prompt` | The whole QC rubric, both verdicts, and the hard blockers that hold an episode regardless of score |

The rest of the QC chain is live only and worth mirroring next: `Token Budget:
QC` converts the Anthropic shape this node emits into the Cerebras
`gpt-oss-120b` shape and appends the dash ban, `Run QC (Cerebras)` posts it,
and `Parse QC + Set Verdict` turns the reply into the verdict, the score and the
findings written onto the row.

Nothing here executes. n8n holds the graph, the credentials and the schedule.
A change made here has to be applied to the live node, and a change made live
has to be copied back, or this file is a lie about what gates the channel.
